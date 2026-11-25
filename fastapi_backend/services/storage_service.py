"""
基于 SQLAlchemy ORM 与 PostgreSQL 关系型数据库的持久化中台服务 (SQLAlchemy + PostgreSQL Storage Service)
使用 SQLAlchemy 2.0 声明式 ORM 模型（CustomerEntity, AgentEntity, OrderEntity, SessionEntity, TransferLogEntity），
支持行级锁并发防护、空值安全映射、大小写不敏感检索与多进程幂等种子数据初始化。
"""

import json
import threading
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from core.logger import log, cprint, LogColor
from config import settings
from data.seed_data import (
    build_seed_customers,
    build_seed_agents,
    build_seed_orders,
    build_seed_sessions,
)
from core.database import (
    get_engine,
    db_session_scope,
    Base,
    POSTGRES_URL,
)
from models.sql_models import (
    CustomerEntity,
    AgentEntity,
    OrderEntity,
    SessionEntity,
    TransferLogEntity,
)


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _non_null(data: Dict[str, Any], key: str, fallback: Any) -> Any:
    """安全取值：当键不存在或值为 None 时回退至 fallback，防止写入 nullable=False 列触发完整性错误"""
    val = data.get(key)
    return val if val is not None else fallback


def _escape_like(text: str) -> str:
    """转义 SQL LIKE/ILIKE 通配符，防止用户输入 % 或 _ 触发非预期全表匹配"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class StorageService:
    """基于 SQLAlchemy ORM 与 PostgreSQL 的持久化中台服务"""

    def __init__(self):
        self._lock = threading.RLock()
        self._initialized = False

    def init_database(self) -> None:
        """幂等初始化数据表结构与初始种子数据（在 FastAPI lifespan 启动阶段显式触发）"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            cprint("[StorageService] SQLAlchemy ORM 架构初始化完毕，当前方言引擎: postgresql", LogColor.GREEN)
            self._seed_initial_data()
            self._initialized = True

    def _seed_initial_data(self) -> None:
        """空表时使用 PostgreSQL ON CONFLICT DO NOTHING 幂等写入初始演示数据（多 worker 启动安全）"""
        now = _now_str()
        seed_specs = (
            (CustomerEntity, CustomerEntity.id, build_seed_customers, "客户画像数据 (CustomerEntity)"),
            (AgentEntity, AgentEntity.id, build_seed_agents, "坐席数据 (AgentEntity)"),
            (OrderEntity, OrderEntity.order_id, build_seed_orders, "订单数据 (OrderEntity)"),
            (SessionEntity, SessionEntity.id, build_seed_sessions, "会话数据 (SessionEntity)"),
        )
        with db_session_scope() as session:
            for model_cls, pk_col, builder_fn, label in seed_specs:
                count = session.query(func.count(pk_col)).scalar() or 0
                if count == 0:
                    rows = builder_fn(now)
                    if rows:
                        stmt = pg_insert(model_cls.__table__).values(rows).on_conflict_do_nothing()
                        session.execute(stmt)
                        cprint(f"[StorageService] 成功播种初始化{label}", LogColor.CYAN)

    # ==================== 1. 客户模型 CRUD (SQLAlchemy ORM) ====================
    def list_customers(self) -> List[Dict[str, Any]]:
        """查询全量客户画像"""
        with db_session_scope() as session:
            entities = session.query(CustomerEntity).order_by(CustomerEntity.updated_at.desc()).all()
            return [e.to_dict() for e in entities]

    def get_customer(self, customer_id_or_name: str) -> Optional[Dict[str, Any]]:
        """按 ID 或姓名单条精准查询客户画像"""
        with db_session_scope() as session:
            entity = session.query(CustomerEntity).filter(
                (CustomerEntity.id == customer_id_or_name) | (CustomerEntity.name == customer_id_or_name)
            ).first()
            return entity.to_dict() if entity else None

    def save_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """新增或更新客户画像（行锁保护 + 非空列安全映射）"""
        cid = customer_data.get("id") or f"user_{int(datetime.datetime.now().timestamp())}"
        now = _now_str()

        with db_session_scope() as session:
            entity = (
                session.query(CustomerEntity)
                .filter(CustomerEntity.id == cid)
                .with_for_update()
                .first()
            )
            if not entity:
                entity = CustomerEntity(id=cid)
                session.add(entity)

            entity.name = _non_null(customer_data, "name", entity.name or "客户")
            entity.phone = _non_null(customer_data, "phone", entity.phone or "")
            entity.vip_level = _non_null(customer_data, "vipLevel", entity.vip_level or "普通会员")
            entity.sentiment = _non_null(customer_data, "sentiment", entity.sentiment or "neutral")
            entity.urgency = _non_null(customer_data, "urgency", entity.urgency or "中")
            entity.intent = _non_null(customer_data, "intent", entity.intent or "常规售后咨询")
            if "tags" in customer_data:
                entity.tags_json = json.dumps(customer_data["tags"] or [], ensure_ascii=False)
            if "orderId" in customer_data:
                entity.order_id = customer_data["orderId"]
            if "avatar" in customer_data:
                entity.avatar = customer_data["avatar"]
            entity.updated_at = now

            session.flush()
            return entity.to_dict()

    # ==================== 2. 客服坐席 CRUD (SQLAlchemy ORM) ====================
    def list_agents(self) -> List[Dict[str, Any]]:
        """获取所有坐席，按评分与负载排序"""
        with db_session_scope() as session:
            entities = session.query(AgentEntity).order_by(
                AgentEntity.rating.desc(),
                AgentEntity.current_workload.asc(),
            ).all()
            return [e.to_dict() for e in entities]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询坐席详情"""
        with db_session_scope() as session:
            entity = session.query(AgentEntity).filter(AgentEntity.id == agent_id).first()
            return entity.to_dict() if entity else None

    def update_agent_workload(self, agent_id: str, delta: int = 1) -> Optional[Dict[str, Any]]:
        """基于数据库行锁动态更新坐席当前承接负荷，防止并发丢失更新"""
        with db_session_scope() as session:
            entity = (
                session.query(AgentEntity)
                .filter(AgentEntity.id == agent_id)
                .with_for_update()
                .first()
            )
            if not entity:
                return None

            new_workload = max(0, min(entity.max_workload, (entity.current_workload or 0) + delta))
            entity.current_workload = new_workload
            entity.status = "BUSY" if new_workload >= entity.max_workload else "IDLE"
            entity.updated_at = _now_str()
            session.flush()
            return entity.to_dict()

    # ==================== 3. 订单中台 CRUD (SQLAlchemy ORM) ====================
    def list_orders(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """多维度条件过滤订单（PostgreSQL 大小写不敏感 ilike + 通配符转义）"""
        with db_session_scope() as session:
            query = session.query(OrderEntity)

            if user_name:
                query = query.filter(OrderEntity.user_name == user_name)
            if status:
                query = query.filter(OrderEntity.status == status)
            if keyword:
                kw = f"%{_escape_like(keyword)}%"
                query = query.filter(
                    OrderEntity.order_id.ilike(kw, escape="\\")
                    | OrderEntity.order_sn.ilike(kw, escape="\\")
                    | OrderEntity.user_name.ilike(kw, escape="\\")
                    | OrderEntity.items_json.ilike(kw, escape="\\")
                    | OrderEntity.express_json.ilike(kw, escape="\\")
                )

            entities = query.order_by(OrderEntity.create_time.desc()).all()
            return [e.to_dict() for e in entities]

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """按订单号精准查询"""
        with db_session_scope() as session:
            entity = session.query(OrderEntity).filter(
                (OrderEntity.order_id == order_id) | (OrderEntity.order_sn == order_id)
            ).first()
            return entity.to_dict() if entity else None

    def save_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """新增或更新订单信息（行锁保护 + 非空列安全映射）"""
        oid = (order_data.get("orderId") or "").strip()
        if not oid:
            raise ValueError("orderId 不能为空")
        now = _now_str()

        with db_session_scope() as session:
            entity = (
                session.query(OrderEntity)
                .filter(OrderEntity.order_id == oid)
                .with_for_update()
                .first()
            )
            if not entity:
                entity = OrderEntity(order_id=oid)
                session.add(entity)

            entity.order_sn = _non_null(
                order_data, "orderSn", entity.order_sn or f"2026{int(datetime.datetime.now().timestamp())}"
            )
            entity.user_id = _non_null(order_data, "userId", entity.user_id or "user_001")
            entity.user_name = _non_null(order_data, "userName", entity.user_name or "客户")
            entity.user_phone = _non_null(order_data, "userPhone", entity.user_phone or "")
            entity.vip_level = _non_null(order_data, "vipLevel", entity.vip_level or "普通会员")
            entity.status = _non_null(order_data, "status", entity.status or "DELIVERED")
            entity.status_text = _non_null(order_data, "statusText", entity.status_text or "已签收")
            entity.status_code = int(_non_null(order_data, "statusCode", entity.status_code or 4))
            entity.create_time = _non_null(order_data, "createTime", entity.create_time or now)
            entity.pay_time = order_data.get("payTime", entity.pay_time)
            entity.ship_time = order_data.get("shipTime", entity.ship_time)
            entity.delivery_time = order_data.get("deliveryTime", entity.delivery_time)
            entity.total_amount = float(_non_null(order_data, "totalAmount", entity.total_amount or 0.0))
            entity.paid_amount = float(_non_null(order_data, "paidAmount", entity.paid_amount or 0.0))
            entity.shipping_fee = float(_non_null(order_data, "shippingFee", entity.shipping_fee or 0.0))

            entity.items_json = (
                json.dumps(order_data["items"] or [], ensure_ascii=False)
                if "items" in order_data
                else (entity.items_json or "[]")
            )
            entity.express_json = (
                json.dumps(order_data["express"] or {}, ensure_ascii=False)
                if "express" in order_data
                else (entity.express_json or "{}")
            )
            entity.receiver_json = (
                json.dumps(order_data["receiver"] or {}, ensure_ascii=False)
                if "receiver" in order_data
                else (entity.receiver_json or "{}")
            )
            entity.after_sales_json = (
                json.dumps(order_data["afterSales"] or {}, ensure_ascii=False)
                if "afterSales" in order_data
                else (entity.after_sales_json or "{}")
            )
            entity.updated_at = now

            session.flush()
            return entity.to_dict()

    # ==================== 4. 会话与上下文 CRUD (SQLAlchemy ORM) ====================
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有对话会话映射字典"""
        with db_session_scope() as session:
            entities = session.query(SessionEntity).order_by(SessionEntity.updated_at.desc()).all()
            return {e.id: e.to_dict() for e in entities}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询会话详情，不存在时返回 None（由 MemoryService 负责按画像初始化创建）"""
        with db_session_scope() as session:
            entity = session.query(SessionEntity).filter(SessionEntity.id == session_id).first()
            return entity.to_dict() if entity else None

    def save_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """原子保存或更新会话状态及消息列表（行锁保护 + 非空列安全映射）"""
        sid = session_data.get("id") or "session_default"
        now = _now_str()

        with db_session_scope() as session:
            entity = (
                session.query(SessionEntity)
                .filter(SessionEntity.id == sid)
                .with_for_update()
                .first()
            )
            if not entity:
                entity = SessionEntity(id=sid, created_at=_non_null(session_data, "createdAt", now))
                session.add(entity)

            entity.user_name = _non_null(session_data, "userName", entity.user_name or "客户")
            entity.status = _non_null(session_data, "status", entity.status or "AI_HANDLING")
            entity.assigned_agent = session_data.get("assignedAgent", entity.assigned_agent)
            entity.assigned_agent_id = session_data.get("assignedAgentId", entity.assigned_agent_id)
            entity.summary_memory = _non_null(session_data, "summaryMemory", entity.summary_memory or "")

            entity.customer_profile_json = (
                json.dumps(session_data["customerProfile"] or {}, ensure_ascii=False)
                if "customerProfile" in session_data
                else (entity.customer_profile_json or "{}")
            )
            entity.messages_json = (
                json.dumps(session_data["messages"] or [], ensure_ascii=False)
                if "messages" in session_data
                else (entity.messages_json or "[]")
            )
            entity.metrics_json = (
                json.dumps(session_data["metrics"] or {}, ensure_ascii=False)
                if "metrics" in session_data
                else (entity.metrics_json or "{}")
            )
            if "latestTransfer" in session_data:
                entity.latest_transfer_json = (
                    json.dumps(session_data["latestTransfer"], ensure_ascii=False)
                    if session_data["latestTransfer"] is not None
                    else None
                )

            entity.updated_at = now
            session.flush()
            return entity.to_dict()

    # ==================== 5. 工单移交审计 CRUD (SQLAlchemy ORM) ====================
    def list_transfer_logs(self) -> List[Dict[str, Any]]:
        """获取所有转接审计日志"""
        with db_session_scope() as session:
            entities = session.query(TransferLogEntity).order_by(TransferLogEntity.transferred_at.desc()).all()
            return [e.to_dict() for e in entities]

    def add_transfer_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录一笔人工转接审计流水"""
        log_id = log_data.get("id") or f"TRF-{int(datetime.datetime.now().timestamp())}"
        now = _now_str()

        with db_session_scope() as session:
            snapshot = log_data.get("contextSnapshot")
            entity = TransferLogEntity(
                id=log_id,
                session_id=_non_null(log_data, "sessionId", "session_unknown"),
                customer_name=_non_null(log_data, "customerName", "客户"),
                vip_level=_non_null(log_data, "vipLevel", "普通会员"),
                reason=_non_null(log_data, "reason", "用户请求转人工"),
                trigger_type=_non_null(log_data, "triggerType", "user_requested"),
                assigned_agent_id=_non_null(log_data, "assignedAgentId", "agent_101"),
                assigned_agent_name=_non_null(log_data, "assignedAgentName", "陈浩"),
                assigned_department=_non_null(log_data, "assignedDepartment", "XX商城 客户服务中心"),
                status=_non_null(log_data, "status", "SUCCESS"),
                transferred_at=_non_null(log_data, "transferredAt", now),
                operator_note=_non_null(log_data, "operatorNote", ""),
                dialogue_rounds=int(_non_null(log_data, "dialogueRounds", 0)),
                context_snapshot_json=(
                    json.dumps(snapshot, ensure_ascii=False) if snapshot is not None else None
                ),
            )
            session.add(entity)
            session.flush()
            return entity.to_dict()

    def clear_sessions_and_transfers(self) -> None:
        """清空会话与转接日志表（专供测试夹具在用例前后重置持久化状态）"""
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        with db_session_scope() as session:
            session.query(TransferLogEntity).delete()
            session.query(SessionEntity).delete()

    # ==================== 6. 存储引擎状态探测 ====================
    def get_storage_status(self) -> Dict[str, Any]:
        """返回当前关系型数据库与 SQLAlchemy ORM 运行状态指标（单次聚合统计 5 张表）"""
        with db_session_scope() as session:
            target_pg = POSTGRES_URL.split("@")[-1] if "@" in POSTGRES_URL else POSTGRES_URL

            counts_row = session.execute(
                select(
                    select(func.count(CustomerEntity.id)).scalar_subquery().label("customers"),
                    select(func.count(AgentEntity.id)).scalar_subquery().label("agents"),
                    select(func.count(OrderEntity.order_id)).scalar_subquery().label("orders"),
                    select(func.count(SessionEntity.id)).scalar_subquery().label("sessions"),
                    select(func.count(TransferLogEntity.id)).scalar_subquery().label("transfer_logs"),
                )
            ).one()

            return {
                "storageType": "PostgreSQL 关系型数据库 (SQLAlchemy ORM 架构)",
                "orm": "SQLAlchemy 2.0 (DeclarativeBase & Session)",
                "databaseDialect": "postgresql",
                "databaseUrlTarget": target_pg,
                "poolConfig": {
                    "poolSize": settings.DB_POOL_SIZE,
                    "maxOverflow": settings.DB_MAX_OVERFLOW,
                    "prePing": True,
                },
                "tables": {
                    "orders": {"tableName": "orders", "count": counts_row.orders, "primaryKey": "order_id", "model": "OrderEntity"},
                    "customers": {"tableName": "customers", "count": counts_row.customers, "primaryKey": "id", "model": "CustomerEntity"},
                    "agents": {"tableName": "agents", "count": counts_row.agents, "primaryKey": "id", "model": "AgentEntity"},
                    "sessions": {"tableName": "sessions", "count": counts_row.sessions, "primaryKey": "id", "model": "SessionEntity"},
                    "transferLogs": {"tableName": "transfer_logs", "count": counts_row.transfer_logs, "primaryKey": "id", "model": "TransferLogEntity"},
                },
                "lastQueryAt": _now_str(),
            }


storage_service = StorageService()
