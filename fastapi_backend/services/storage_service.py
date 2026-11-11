"""
基于 SQLAlchemy ORM 与 PostgreSQL 关系型数据库的持久化固化存储中台 (SQLAlchemy + PostgreSQL Storage Service)
使用 SQLAlchemy 2.0 声明式 ORM 模型（CustomerEntity, AgentEntity, OrderEntity, SessionEntity, TransferLogEntity）
全面替代 JSON 文件与原生字符串拼接，所有业务交互（订单过滤/客户画像/坐席分派/会话流转/审计留痕）
均通过类型安全的 SQLAlchemy ORM Session 会话操作，具备自动连接池维护、事务 ACID 保障与本地高可用热备兼容。
"""

import os
import json
import threading
import datetime
from typing import Dict, Any, List, Optional
from core.logger import log, cprint, LogColor
from config import settings

# 引入 SQLAlchemy 核心组件与 ORM 实体模型
from core.database import (
    get_engine,
    get_session_factory,
    get_active_dialect,
    db_session_scope,
    Base,
    POSTGRES_URL,
    SQLITE_FALLBACK_URL
)
from models.sql_models import (
    CustomerEntity,
    AgentEntity,
    OrderEntity,
    SessionEntity,
    TransferLogEntity
)


class StorageService:
    """基于 SQLAlchemy ORM 与 PostgreSQL 的持久化中台服务"""

    def __init__(self):
        self._lock = threading.RLock()
        self._init_database()

    def _init_database(self):
        """初始化数据表结构与初始种子数据"""
        engine = get_engine()
        if engine is None:
            log.warning("SQLAlchemy 引擎未就绪")
            return

        with self._lock:
            try:
                # 1. 自动执行 DDL 创建表结构 (若不存在)
                Base.metadata.create_all(bind=engine)
                dialect = get_active_dialect()
                cprint(f"[StorageService] SQLAlchemy ORM 架构初始化完毕，当前方言引擎: {dialect}", LogColor.GREEN)

                # 2. 检查并注入初始种子数据
                self._seed_initial_data()
            except Exception as e:
                log.error(f"[StorageService] 数据库表结构初始化失败: {e}")

    def _seed_initial_data(self):
        """若数据表为空，初始化标准测试数据"""
        with db_session_scope() as session:
            if session is None:
                return

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. 初始化客户画像表
            if session.query(CustomerEntity).count() == 0:
                c1 = CustomerEntity(
                    id="user_001",
                    name="王女士",
                    phone="138****6699",
                    vip_level="黄金会员",
                    sentiment="frustrated",
                    urgency="高",
                    intent="7天无理由退货运费与到账时间",
                    tags_json=json.dumps(["黄金会员", "免运费特权", "急躁", "签收第3天"], ensure_ascii=False),
                    order_id="ORD-2026-88992",
                    avatar="https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=120&q=80",
                    registered_date="2023-08-15",
                    total_orders_count=18,
                    total_spent=14580.0,
                    shipping_address="北京市朝阳区亮马桥路88号XX花园3号楼1202室",
                    updated_at=now
                )
                c2 = CustomerEntity(
                    id="user_002",
                    name="张先生",
                    phone="139****1122",
                    vip_level="普通会员",
                    sentiment="neutral",
                    urgency="中",
                    intent="个人定制刻字紫砂壶退货咨询",
                    tags_json=json.dumps(["普通会员", "定制工艺品", "运输中"], ensure_ascii=False),
                    order_id="ORD-2026-90412",
                    avatar="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80",
                    registered_date="2024-01-20",
                    total_orders_count=3,
                    total_spent=1260.0,
                    shipping_address="浙江省杭州市西湖区文三路398号创新大厦A座8楼",
                    updated_at=now
                )
                c3 = CustomerEntity(
                    id="user_003",
                    name="刘总",
                    phone="186****9988",
                    vip_level="钻石会员",
                    sentiment="positive",
                    urgency="低",
                    intent="极速退款到账时效确认",
                    tags_json=json.dumps(["钻石会员", "大额客户", "已寄回质检"], ensure_ascii=False),
                    order_id="ORD-2026-77310",
                    avatar="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
                    registered_date="2022-04-10",
                    total_orders_count=52,
                    total_spent=98600.0,
                    shipping_address="上海市浦东新区陆家嘴环路1000号恒生银行大厦28楼",
                    updated_at=now
                )
                session.add_all([c1, c2, c3])
                cprint("[StorageService] 成功播种初始化客户画像数据 (CustomerEntity)", LogColor.CYAN)

            # 2. 初始化坐席表
            if session.query(AgentEntity).count() == 0:
                a1 = AgentEntity(
                    id="agent_101",
                    name="陈浩",
                    title="高级售后督导",
                    department="XX商城 客户关怀中心",
                    status="IDLE",
                    current_workload=1,
                    max_workload=5,
                    rating=4.98,
                    specialties_json=json.dumps(["7天无理由退货", "黄金会员运费补贴", "客诉安抚"], ensure_ascii=False),
                    recommended_for_json=json.dumps(["退运费", "到账时间", "情绪安抚", "会员特权"], ensure_ascii=False),
                    avatar="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80",
                    phone="分机 8011",
                    email="chenhao@xx-mall.com",
                    updated_at=now
                )
                a2 = AgentEntity(
                    id="agent_102",
                    name="林雅",
                    title="退换货与物流主管",
                    department="售后争议调解组",
                    status="IDLE",
                    current_workload=0,
                    max_workload=5,
                    rating=4.95,
                    specialties_json=json.dumps(["特殊商品退货政策", "定制品纠纷", "物流丢件理赔"], ensure_ascii=False),
                    recommended_for_json=json.dumps(["定制商品", "刻字不退", "物流延误", "顺丰拦截"], ensure_ascii=False),
                    avatar="https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=120&q=80",
                    phone="分机 8012",
                    email="linya@xx-mall.com",
                    updated_at=now
                )
                a3 = AgentEntity(
                    id="agent_103",
                    name="张建国",
                    title="资深技术支持专员",
                    department="智能硬件售后组",
                    status="IDLE",
                    current_workload=0,
                    max_workload=4,
                    rating=4.91,
                    specialties_json=json.dumps(["扫地机器人故障", "激光雷达标定", "固件OTA升级"], ensure_ascii=False),
                    recommended_for_json=json.dumps(["机器异响", "无法充电", "质量检测"], ensure_ascii=False),
                    avatar="https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=120&q=80",
                    phone="分机 8015",
                    email="zhangjg@xx-mall.com",
                    updated_at=now
                )
                a4 = AgentEntity(
                    id="agent_104",
                    name="李晓静",
                    title="VIP专属客户管家",
                    department="钻石会员专属服务组",
                    status="IDLE",
                    current_workload=0,
                    max_workload=3,
                    rating=4.99,
                    specialties_json=json.dumps(["大客户极速冲正", "专属绿色通道", "高管关怀"], ensure_ascii=False),
                    recommended_for_json=json.dumps(["钻石会员", "极速退款", "大额退换"], ensure_ascii=False),
                    avatar="https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=120&q=80",
                    phone="专线 8000",
                    email="lixiaojing@xx-mall.com",
                    updated_at=now
                )
                session.add_all([a1, a2, a3, a4])
                cprint("[StorageService] 成功播种初始化坐席数据 (AgentEntity)", LogColor.CYAN)

            # 3. 初始化订单表
            if session.query(OrderEntity).count() == 0:
                o1_items = [{
                    "skuId": "SKU-ROBOT-001",
                    "title": "XX智能全自动扫地机器人 Pro (双向避障激光导航版)",
                    "category": "生活电器",
                    "spec": "曜石黑 / 双盘旋转擦地 / 自动集尘基站",
                    "price": 2999.0,
                    "quantity": 1,
                    "imageUrl": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=160&q=80",
                    "isSpecialProduct": False,
                    "isCustomized": False
                }]
                o1_express = {
                    "company": "顺丰速运",
                    "companyCode": "SF",
                    "trackingNumber": "SF1882049281",
                    "status": "DELIVERED",
                    "statusDescription": "买家已在菜鸟驿站/自提柜签收",
                    "timeline": [
                        {"time": "2026-03-25 11:24:36", "status": "已签收", "context": "【已签收】您的快件已由本人在 [北京市朝阳区亮马桥路XX花园菜鸟驿站] 签收。"},
                        {"time": "2026-03-25 08:15:20", "status": "派送中", "context": "【派送中】顺丰速运 派件员 张师傅正在派送。"}
                    ]
                }
                o1_receiver = {"name": "王女士", "phone": "138****6699", "address": "北京市朝阳区亮马桥路88号XX花园3号楼1202室"}
                o1_after_sales = {
                    "canReturn7Days": True,
                    "returnDaysRemaining": 4,
                    "signedDays": 3,
                    "returnPolicy": "支持7天无理由退货（商品完好、配件齐全、未影响二次销售）",
                    "shippingSubsidy": "黄金会员享有平台免运费退货补贴",
                    "warrantyStatus": "生效中",
                    "warrantyExpiredDate": "2027-03-25",
                    "warrantyPolicy": "1年全国联保，15天内非人为故障可免费换新机"
                }
                o1 = OrderEntity(
                    order_id="ORD-2026-88992",
                    order_sn="202603258899201",
                    user_id="user_001",
                    user_name="王女士",
                    user_phone="138****6699",
                    vip_level="黄金会员",
                    status="DELIVERED",
                    status_text="已签收",
                    status_code=4,
                    create_time="2026-03-22 14:20:10",
                    pay_time="2026-03-22 14:21:05",
                    ship_time="2026-03-23 09:30:00",
                    delivery_time="2026-03-25 11:24:36",
                    items_json=json.dumps(o1_items, ensure_ascii=False),
                    total_amount=2999.0,
                    paid_amount=2999.0,
                    shipping_fee=0.0,
                    express_json=json.dumps(o1_express, ensure_ascii=False),
                    receiver_json=json.dumps(o1_receiver, ensure_ascii=False),
                    after_sales_json=json.dumps(o1_after_sales, ensure_ascii=False),
                    updated_at=now
                )

                o2_items = [{
                    "skuId": "SKU-TEA-002",
                    "title": "纯手工定制刻字紫砂壶 (大师编号收藏版)",
                    "category": "工艺礼品",
                    "spec": "底款刻字：『宁静致远』 / 280ml 原矿紫泥",
                    "price": 880.0,
                    "quantity": 1,
                    "imageUrl": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=160&q=80",
                    "isSpecialProduct": True,
                    "isCustomized": True
                }]
                o2_express = {
                    "company": "京东快递",
                    "companyCode": "JD",
                    "trackingNumber": "JD0092817263",
                    "status": "IN_TRANSIT",
                    "statusDescription": "快件正在高速运输中，预计次日送达",
                    "timeline": [{"time": "2026-03-27 16:30:00", "status": "运输中", "context": "【运输中】快件已到达杭州萧山转运中心。"}]
                }
                o2_receiver = {"name": "张先生", "phone": "139****1122", "address": "浙江省杭州市西湖区文三路398号创新大厦A座8楼"}
                o2_after_sales = {
                    "canReturn7Days": False,
                    "returnDaysRemaining": 0,
                    "signedDays": 0,
                    "returnPolicy": "此商品为个人定制专属刻字工艺品，非质量问题不支持7天无理由退货",
                    "shippingSubsidy": "普通会员个人退货需自行承担运费",
                    "warrantyStatus": "破损包赔",
                    "warrantyExpiredDate": "2026-04-26",
                    "warrantyPolicy": "若签收时发现运输碎裂破损，支持极速拍照补发或先行赔付"
                }
                o2 = OrderEntity(
                    order_id="ORD-2026-90412",
                    order_sn="202603279041202",
                    user_id="user_002",
                    user_name="张先生",
                    user_phone="139****1122",
                    vip_level="普通会员",
                    status="IN_TRANSIT",
                    status_text="运输中",
                    status_code=3,
                    create_time="2026-03-26 10:15:00",
                    pay_time="2026-03-26 10:16:30",
                    ship_time="2026-03-27 08:45:00",
                    delivery_time=None,
                    items_json=json.dumps(o2_items, ensure_ascii=False),
                    total_amount=880.0,
                    paid_amount=880.0,
                    shipping_fee=0.0,
                    express_json=json.dumps(o2_express, ensure_ascii=False),
                    receiver_json=json.dumps(o2_receiver, ensure_ascii=False),
                    after_sales_json=json.dumps(o2_after_sales, ensure_ascii=False),
                    updated_at=now
                )

                session.add_all([o1, o2])
                cprint("[StorageService] 成功播种初始化订单数据 (OrderEntity)", LogColor.CYAN)

            # 4. 初始化会话表
            if session.query(SessionEntity).count() == 0:
                s1_profile = {
                    "name": "王女士",
                    "phone": "138****6699",
                    "vipLevel": "黄金会员",
                    "sentiment": "frustrated",
                    "urgency": "高",
                    "intent": "7天无理由退货运费与到账时间",
                    "tags": ["黄金会员", "免运费特权", "急躁", "签收第3天"],
                    "orderId": "ORD-2026-88992"
                }
                s1_msgs = [
                    {"id": "m1", "role": "user", "content": "我3天前买的扫地机器人，包装完好没拆过封，想退货的话运费谁承担？", "timestamp": "10:14:20"},
                    {"id": "m2", "role": "assistant", "content": "王女士您好！根据XX商城政策：签收7天内商品完好支持7天无理由退换。虽然个人原因退换通常由买家承担运费，但检测到您是【黄金会员】，享有平台全额补贴的『退货免运费』专属权益，您无需承担任何寄回运费！", "confidenceScore": 0.96, "timestamp": "10:14:24"},
                    {"id": "m3", "role": "user", "content": "那我退回去之后，钱大概几天能退回我的支付宝？", "timestamp": "10:15:02"}
                ]
                s1 = SessionEntity(
                    id="session_user_001",
                    user_name="王女士",
                    status="AI_HANDLING",
                    assigned_agent=None,
                    assigned_agent_id=None,
                    customer_profile_json=json.dumps(s1_profile, ensure_ascii=False),
                    summary_memory="客户王女士（黄金会员，订单 ORD-2026-88992）签收扫地机器人3天，因尺寸不合适想申请7天无理由退货，咨询退货运费是否需要自己出以及退款多久到账。系统已确认黄金会员享免运费补贴。",
                    messages_json=json.dumps(s1_msgs, ensure_ascii=False),
                    metrics_json=json.dumps({"totalTurns": 3, "avgLatencyMs": 320, "avgConfidence": 0.96, "escalatedAt": None}, ensure_ascii=False),
                    context_snapshot_json=None,
                    latest_transfer_json=None,
                    unread_for_agent=0,
                    created_at=now,
                    updated_at=now
                )
                session.add(s1)
                cprint("[StorageService] 成功播种初始化会话数据 (SessionEntity)", LogColor.CYAN)

    # ==================== 1. 客户模型 CRUD (SQLAlchemy ORM) ====================
    def list_customers(self) -> List[Dict[str, Any]]:
        """查询全量客户画像"""
        with db_session_scope() as session:
            if session is None:
                return []
            entities = session.query(CustomerEntity).order_by(CustomerEntity.updated_at.desc()).all()
            return [e.to_dict() for e in entities]

    def get_customer(self, customer_id_or_name: str) -> Optional[Dict[str, Any]]:
        """按 ID 或 姓名单条精准查询客户画像"""
        with db_session_scope() as session:
            if session is None:
                return None
            entity = session.query(CustomerEntity).filter(
                (CustomerEntity.id == customer_id_or_name) | (CustomerEntity.name == customer_id_or_name)
            ).first()
            return entity.to_dict() if entity else None

    def save_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """新增或更新客户画像 (SQLAlchemy ORM merge)"""
        cid = customer_data.get("id") or f"user_{int(datetime.datetime.now().timestamp())}"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_session_scope() as session:
            if session is None:
                return customer_data

            entity = session.query(CustomerEntity).filter(CustomerEntity.id == cid).first()
            if not entity:
                entity = CustomerEntity(id=cid)
                session.add(entity)

            entity.name = customer_data.get("name", entity.name if entity.name else "客户")
            entity.phone = customer_data.get("phone", entity.phone or "")
            entity.vip_level = customer_data.get("vipLevel", entity.vip_level or "普通会员")
            entity.sentiment = customer_data.get("sentiment", entity.sentiment or "neutral")
            entity.urgency = customer_data.get("urgency", entity.urgency or "中")
            entity.intent = customer_data.get("intent", entity.intent or "常规售后咨询")
            if "tags" in customer_data:
                entity.tags_json = json.dumps(customer_data["tags"], ensure_ascii=False)
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
            if session is None:
                return []
            entities = session.query(AgentEntity).order_by(
                AgentEntity.rating.desc(),
                AgentEntity.current_workload.asc()
            ).all()
            return [e.to_dict() for e in entities]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询坐席详情"""
        with db_session_scope() as session:
            if session is None:
                return None
            entity = session.query(AgentEntity).filter(AgentEntity.id == agent_id).first()
            return entity.to_dict() if entity else None

    def update_agent_workload(self, agent_id: str, delta: int = 1) -> Optional[Dict[str, Any]]:
        """动态更新坐席当前承接负荷"""
        with db_session_scope() as session:
            if session is None:
                return None
            entity = session.query(AgentEntity).filter(AgentEntity.id == agent_id).first()
            if entity:
                new_workload = max(0, min(entity.max_workload, (entity.current_workload or 0) + delta))
                entity.current_workload = new_workload
                entity.status = "BUSY" if new_workload >= entity.max_workload else "IDLE"
                entity.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                session.flush()
                return entity.to_dict()
            return None

    # ==================== 3. 订单中台 CRUD (SQLAlchemy ORM) ====================
    def list_orders(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """多维度条件过滤订单 (SQLAlchemy Query)"""
        with db_session_scope() as session:
            if session is None:
                return []
            query = session.query(OrderEntity)

            if user_name:
                query = query.filter(OrderEntity.user_name == user_name)
            if status:
                query = query.filter(OrderEntity.status == status)
            if keyword:
                kw = f"%{keyword}%"
                query = query.filter(
                    (OrderEntity.order_id.like(kw)) | 
                    (OrderEntity.order_sn.like(kw)) |
                    (OrderEntity.items_json.like(kw))
                )

            entities = query.order_by(OrderEntity.create_time.desc()).all()
            return [e.to_dict() for e in entities]

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """按订单号精准查询"""
        with db_session_scope() as session:
            if session is None:
                return None
            entity = session.query(OrderEntity).filter(
                (OrderEntity.order_id == order_id) | (OrderEntity.order_sn == order_id)
            ).first()
            return entity.to_dict() if entity else None

    def save_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """新增或更新订单信息"""
        oid = order_data.get("orderId")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_session_scope() as session:
            if session is None:
                return order_data

            entity = session.query(OrderEntity).filter(OrderEntity.order_id == oid).first()
            if not entity:
                entity = OrderEntity(order_id=oid)
                session.add(entity)

            entity.order_sn = order_data.get("orderSn", entity.order_sn or f"2026{int(datetime.datetime.now().timestamp())}")
            entity.user_id = order_data.get("userId", entity.user_id or "user_001")
            entity.user_name = order_data.get("userName", entity.user_name or "客户")
            entity.user_phone = order_data.get("userPhone", entity.user_phone or "")
            entity.vip_level = order_data.get("vipLevel", entity.vip_level or "普通会员")
            entity.status = order_data.get("status", entity.status or "DELIVERED")
            entity.status_text = order_data.get("statusText", entity.status_text or "已签收")
            entity.status_code = int(order_data.get("statusCode", entity.status_code or 4))
            entity.create_time = order_data.get("createTime", entity.create_time or now)
            entity.pay_time = order_data.get("payTime", entity.pay_time)
            entity.ship_time = order_data.get("shipTime", entity.ship_time)
            entity.delivery_time = order_data.get("deliveryTime", entity.delivery_time)
            entity.total_amount = float(order_data.get("totalAmount", entity.total_amount or 0.0))
            entity.paid_amount = float(order_data.get("paidAmount", entity.paid_amount or 0.0))
            entity.shipping_fee = float(order_data.get("shippingFee", entity.shipping_fee or 0.0))

            if "items" in order_data:
                entity.items_json = json.dumps(order_data["items"], ensure_ascii=False)
            if "express" in order_data:
                entity.express_json = json.dumps(order_data["express"], ensure_ascii=False)
            if "receiver" in order_data:
                entity.receiver_json = json.dumps(order_data["receiver"], ensure_ascii=False)
            if "afterSales" in order_data:
                entity.after_sales_json = json.dumps(order_data["afterSales"], ensure_ascii=False)
            entity.updated_at = now

            session.flush()
            return entity.to_dict()

    # ==================== 4. 会话与上下文 CRUD (SQLAlchemy ORM) ====================
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有对话会话映射字典"""
        with db_session_scope() as session:
            if session is None:
                return {}
            entities = session.query(SessionEntity).order_by(SessionEntity.updated_at.desc()).all()
            return {e.id: e.to_dict() for e in entities}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询会话详情，若不存在则懒加载创建"""
        with db_session_scope() as session:
            if session is None:
                return None
            entity = session.query(SessionEntity).filter(SessionEntity.id == session_id).first()
            if entity:
                return entity.to_dict()

            # 默认新建会话并写入
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            default_profile = {
                "name": "体验访客",
                "vipLevel": "黄金会员",
                "sentiment": "neutral",
                "urgency": "中",
                "intent": "业务咨询",
                "tags": ["黄金会员"]
            }
            new_entity = SessionEntity(
                id=session_id,
                user_name="体验访客",
                status="AI_HANDLING",
                assigned_agent=None,
                assigned_agent_id=None,
                customer_profile_json=json.dumps(default_profile, ensure_ascii=False),
                summary_memory="新建立的对话会话",
                messages_json="[]",
                metrics_json=json.dumps({"totalTurns": 0, "avgLatencyMs": 300, "avgConfidence": 0.95}),
                context_snapshot_json=None,
                latest_transfer_json=None,
                unread_for_agent=0,
                created_at=now,
                updated_at=now
            )
            session.add(new_entity)
            session.flush()
            return new_entity.to_dict()

    def save_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """原子保存或更新会话状态及消息列表"""
        sid = session_data.get("id") or "session_default"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_session_scope() as session:
            if session is None:
                return session_data

            entity = session.query(SessionEntity).filter(SessionEntity.id == sid).first()
            if not entity:
                entity = SessionEntity(id=sid, created_at=session_data.get("createdAt", now))
                session.add(entity)

            entity.user_name = session_data.get("userName", entity.user_name or "客户")
            entity.status = session_data.get("status", entity.status or "AI_HANDLING")
            entity.assigned_agent = session_data.get("assignedAgent", entity.assigned_agent)
            entity.assigned_agent_id = session_data.get("assignedAgentId", entity.assigned_agent_id)
            entity.summary_memory = session_data.get("summaryMemory", entity.summary_memory or "")
            entity.unread_for_agent = 1 if session_data.get("unreadForAgent") else 0

            if "customerProfile" in session_data:
                entity.customer_profile_json = json.dumps(session_data["customerProfile"], ensure_ascii=False)
            if "messages" in session_data:
                entity.messages_json = json.dumps(session_data["messages"], ensure_ascii=False)
            if "metrics" in session_data:
                entity.metrics_json = json.dumps(session_data["metrics"], ensure_ascii=False)
            if "contextSnapshot" in session_data:
                entity.context_snapshot_json = json.dumps(session_data["contextSnapshot"], ensure_ascii=False)
            if "latestTransfer" in session_data:
                entity.latest_transfer_json = json.dumps(session_data["latestTransfer"], ensure_ascii=False)

            entity.updated_at = now
            session.flush()
            return entity.to_dict()

    # ==================== 5. 工单移交审计 CRUD (SQLAlchemy ORM) ====================
    def list_transfer_logs(self) -> List[Dict[str, Any]]:
        """获取所有转接审计日志"""
        with db_session_scope() as session:
            if session is None:
                return []
            entities = session.query(TransferLogEntity).order_by(TransferLogEntity.transferred_at.desc()).all()
            return [e.to_dict() for e in entities]

    def add_transfer_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录一笔不可篡改的人工转接审计流水"""
        log_id = log_data.get("id") or f"TRF-{int(datetime.datetime.now().timestamp())}"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_session_scope() as session:
            if session is None:
                return log_data

            entity = TransferLogEntity(
                id=log_id,
                session_id=log_data.get("sessionId", "session_unknown"),
                customer_name=log_data.get("customerName", "客户"),
                vip_level=log_data.get("vipLevel", "普通会员"),
                reason=log_data.get("reason", "用户请求转人工"),
                trigger_type=log_data.get("triggerType", "user_requested"),
                assigned_agent_id=log_data.get("assignedAgentId", "agent_101"),
                assigned_agent_name=log_data.get("assignedAgentName", "陈浩"),
                assigned_department=log_data.get("assignedDepartment", "XX商城 客户服务中心"),
                status=log_data.get("status", "SUCCESS"),
                transferred_at=log_data.get("transferredAt", now),
                operator_note=log_data.get("operatorNote", ""),
                dialogue_rounds=int(log_data.get("dialogueRounds", 0)),
                context_snapshot_json=json.dumps(log_data.get("contextSnapshot", {}), ensure_ascii=False)
            )
            session.add(entity)
            session.flush()
            return entity.to_dict()

    # ==================== 6. 存储引擎状态探测 ====================
    def get_storage_status(self) -> Dict[str, Any]:
        """返回当前关系型数据库与 SQLAlchemy ORM 运行状态指标"""
        with db_session_scope() as session:
            dialect = get_active_dialect()
            target_pg = POSTGRES_URL.split("@")[-1] if "@" in POSTGRES_URL else POSTGRES_URL

            cust_cnt = session.query(CustomerEntity).count() if session else 0
            agent_cnt = session.query(AgentEntity).count() if session else 0
            order_cnt = session.query(OrderEntity).count() if session else 0
            session_cnt = session.query(SessionEntity).count() if session else 0
            transfer_cnt = session.query(TransferLogEntity).count() if session else 0

            return {
                "storageType": "PostgreSQL 关系型数据库 (SQLAlchemy ORM 架构)",
                "orm": "SQLAlchemy 2.0 (DeclarativeBase & Session)",
                "databaseDialect": dialect,
                "databaseUrlTarget": target_pg,
                "poolConfig": {
                    "poolSize": getattr(settings, "DB_POOL_SIZE", 10),
                    "maxOverflow": getattr(settings, "DB_MAX_OVERFLOW", 20),
                    "prePing": True
                },
                "tables": {
                    "orders": {"tableName": "orders", "count": order_cnt, "primaryKey": "order_id", "model": "OrderEntity"},
                    "customers": {"tableName": "customers", "count": cust_cnt, "primaryKey": "id", "model": "CustomerEntity"},
                    "agents": {"tableName": "agents", "count": agent_cnt, "primaryKey": "id", "model": "AgentEntity"},
                    "sessions": {"tableName": "sessions", "count": session_cnt, "primaryKey": "id", "model": "SessionEntity"},
                    "transferLogs": {"tableName": "transfer_logs", "count": transfer_cnt, "primaryKey": "id", "model": "TransferLogEntity"}
                },
                "lastQueryAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


storage_service = StorageService()
