"""
SQLAlchemy 声明式 ORM 模型定义 (SQLAlchemy Declarative Models)
适配 PostgreSQL 关系型数据库，完整定义 5 大核心业务实体：
1. 客户模型 (CustomerEntity -> customers)
2. 客服坐席模型 (AgentEntity -> agents)
3. 订单模型 (OrderEntity -> orders)
4. 会话与上下文模型 (SessionEntity -> sessions)
5. 转人工审计工单模型 (TransferLogEntity -> transfer_logs)
"""

from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Index
from core.database import Base


class CustomerEntity(Base):
    """客户档案与画像表 (customers)"""
    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_customers_name", "name"),
        Index("idx_customers_vip", "vip_level"),
        {"extend_existing": True}
    )

    id = Column(String(64), primary_key=True, index=True, doc="客户ID，如 user_001")
    name = Column(String(64), nullable=False, doc="客户姓名，如 王女士")
    phone = Column(String(32), default="", doc="手机号")
    vip_level = Column(String(32), default="普通会员", doc="会员等级")
    sentiment = Column(String(32), default="neutral", doc="情绪状态")
    urgency = Column(String(16), default="中", doc="紧急度")
    intent = Column(String(128), default="常规售后咨询", doc="咨询意图")
    tags_json = Column(Text, default="[]", doc="用户标签 JSON 数组")
    order_id = Column(String(64), nullable=True, doc="关联订单编号")
    avatar = Column(Text, nullable=True, doc="头像 URL")
    registered_date = Column(String(32), default="2024-05-12", doc="注册入会日期")
    total_orders_count = Column(Integer, default=1, doc="累计下单数")
    total_spent = Column(Float, default=0.0, doc="累计消费金额")
    shipping_address = Column(Text, default="", doc="默认配送地址")
    updated_at = Column(String(32), nullable=False, doc="最后更新时间")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone or "",
            "vipLevel": self.vip_level or "普通会员",
            "sentiment": self.sentiment or "neutral",
            "urgency": self.urgency or "中",
            "intent": self.intent or "常规售后咨询",
            "tags": json.loads(self.tags_json) if self.tags_json else [],
            "orderId": self.order_id,
            "avatar": self.avatar,
            "registeredDate": self.registered_date or "2024-05-12",
            "totalOrdersCount": self.total_orders_count or 1,
            "totalSpent": self.total_spent or 0.0,
            "shippingAddress": self.shipping_address or "",
            "updatedAt": self.updated_at
        }


class AgentEntity(Base):
    """客服坐席表 (agents)"""
    __tablename__ = "agents"
    __table_args__ = (
        Index("idx_agents_status", "status"),
        Index("idx_agents_rating", "rating"),
        {"extend_existing": True}
    )

    id = Column(String(64), primary_key=True, index=True, doc="坐席工号，如 agent_101")
    name = Column(String(64), nullable=False, doc="坐席姓名")
    title = Column(String(64), nullable=False, doc="岗位职称")
    department = Column(String(128), nullable=False, doc="所属部门")
    status = Column(String(32), default="IDLE", doc="当前服务状态")
    current_workload = Column(Integer, default=0, doc="当前承接会话数")
    max_workload = Column(Integer, default=5, doc="最大并发负荷")
    rating = Column(Float, default=4.95, doc="综合评分 (5分制)")
    specialties_json = Column(Text, default="[]", doc="擅长专业领域 JSON 数组")
    recommended_for_json = Column(Text, default="[]", doc="调度推荐关键词 JSON 数组")
    avatar = Column(Text, nullable=True, doc="坐席头像")
    phone = Column(String(32), default="", doc="分机号")
    email = Column(String(64), default="", doc="企业邮箱")
    updated_at = Column(String(32), nullable=False, doc="最后更新时间")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "department": self.department,
            "status": self.status or "IDLE",
            "currentWorkload": self.current_workload or 0,
            "maxWorkload": self.max_workload or 5,
            "rating": self.rating or 4.95,
            "specialties": json.loads(self.specialties_json) if self.specialties_json else [],
            "recommendedFor": json.loads(self.recommended_for_json) if self.recommended_for_json else [],
            "avatar": self.avatar,
            "phone": self.phone or "",
            "email": self.email or "",
            "updatedAt": self.updated_at
        }


class OrderEntity(Base):
    """订单中台表 (orders)"""
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_user_name", "user_name"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_sn", "order_sn"),
        {"extend_existing": True}
    )

    order_id = Column(String(64), primary_key=True, index=True, doc="业务订单号，如 ORD-2026-88992")
    order_sn = Column(String(64), nullable=False, doc="全数字支付流水号")
    user_id = Column(String(64), nullable=False, doc="购买客户ID")
    user_name = Column(String(64), nullable=False, doc="客户姓名")
    user_phone = Column(String(32), default="", doc="联系手机")
    vip_level = Column(String(32), default="普通会员", doc="下单时客户会员级别")
    status = Column(String(32), nullable=False, doc="状态码：DELIVERED / IN_TRANSIT 等")
    status_text = Column(String(64), nullable=False, doc="展示状态名")
    status_code = Column(Integer, default=1, doc="状态排序码")
    create_time = Column(String(32), nullable=False, doc="下单时间")
    pay_time = Column(String(32), nullable=True, doc="支付成功时间")
    ship_time = Column(String(32), nullable=True, doc="发货时间")
    delivery_time = Column(String(32), nullable=True, doc="签收时间")
    items_json = Column(Text, nullable=False, doc="订单商品行项目明细 JSON")
    total_amount = Column(Float, nullable=False, doc="订单总额")
    paid_amount = Column(Float, nullable=False, doc="实付金额")
    shipping_fee = Column(Float, default=0.0, doc="运费")
    express_json = Column(Text, nullable=False, doc="物流轨迹与承运商 JSON")
    receiver_json = Column(Text, nullable=False, doc="收件人与详细配送地址 JSON")
    after_sales_json = Column(Text, nullable=False, doc="7天无理由退货与质保售后规则判定快照 JSON")
    updated_at = Column(String(32), nullable=False, doc="最后更新时间")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "orderId": self.order_id,
            "orderSn": self.order_sn,
            "userId": self.user_id,
            "userName": self.user_name,
            "userPhone": self.user_phone or "",
            "vipLevel": self.vip_level or "普通会员",
            "status": self.status,
            "statusText": self.status_text,
            "statusCode": self.status_code,
            "createTime": self.create_time,
            "payTime": self.pay_time,
            "shipTime": self.ship_time,
            "deliveryTime": self.delivery_time,
            "items": json.loads(self.items_json) if self.items_json else [],
            "totalAmount": self.total_amount,
            "paidAmount": self.paid_amount,
            "shippingFee": self.shipping_fee,
            "express": json.loads(self.express_json) if self.express_json else {},
            "receiver": json.loads(self.receiver_json) if self.receiver_json else {},
            "afterSales": json.loads(self.after_sales_json) if self.after_sales_json else {},
            "updatedAt": self.updated_at
        }


class SessionEntity(Base):
    """会话与消息流表 (sessions)"""
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_updated", "updated_at"),
        Index("idx_sessions_status", "status"),
        {"extend_existing": True}
    )

    id = Column(String(64), primary_key=True, index=True, doc="会话唯一ID，如 session_user_001")
    user_name = Column(String(64), nullable=False, doc="客户昵称")
    status = Column(String(32), default="AI_HANDLING", doc="服务状态")
    assigned_agent = Column(String(64), nullable=True, doc="人工坐席姓名")
    assigned_agent_id = Column(String(64), nullable=True, doc="人工坐席工号")
    customer_profile_json = Column(Text, nullable=False, doc="挂载客户画像 JSON")
    summary_memory = Column(Text, default="", doc="对话长期记忆摘要")
    messages_json = Column(Text, nullable=False, doc="对话时序消息流 JSON")
    metrics_json = Column(Text, nullable=False, doc="会话性能指标快照 JSON")
    context_snapshot_json = Column(Text, nullable=True, doc="转接上下文快照 JSON")
    latest_transfer_json = Column(Text, nullable=True, doc="最新转接流水信息 JSON")
    unread_for_agent = Column(Integer, default=0, doc="人工坐席未读标识 (0/1)")
    created_at = Column(String(32), nullable=False, doc="会话创建时间")
    updated_at = Column(String(32), nullable=False, doc="最后更新时间")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "userName": self.user_name or "客户",
            "status": self.status or "AI_HANDLING",
            "assignedAgent": self.assigned_agent,
            "assignedAgentId": self.assigned_agent_id,
            "customerProfile": json.loads(self.customer_profile_json) if self.customer_profile_json else {},
            "summaryMemory": self.summary_memory or "",
            "messages": json.loads(self.messages_json) if self.messages_json else [],
            "metrics": json.loads(self.metrics_json) if self.metrics_json else {},
            "contextSnapshot": json.loads(self.context_snapshot_json) if self.context_snapshot_json else None,
            "latestTransfer": json.loads(self.latest_transfer_json) if self.latest_transfer_json else None,
            "unreadForAgent": bool(self.unread_for_agent),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }


class TransferLogEntity(Base):
    """工单移交审计流水表 (transfer_logs)"""
    __tablename__ = "transfer_logs"
    __table_args__ = (
        Index("idx_transfer_session", "session_id"),
        Index("idx_transfer_agent", "assigned_agent_id"),
        {"extend_existing": True}
    )

    id = Column(String(64), primary_key=True, index=True, doc="工单编号，如 TRF-1710000000-A1B2")
    session_id = Column(String(64), nullable=False, doc="关联会话ID")
    customer_name = Column(String(64), nullable=False, doc="客户姓名")
    vip_level = Column(String(32), default="普通会员", doc="客户等级")
    reason = Column(Text, nullable=False, doc="转交原因")
    trigger_type = Column(String(32), default="user_requested", doc="触发方式")
    assigned_agent_id = Column(String(64), nullable=False, doc="指派坐席工号")
    assigned_agent_name = Column(String(64), nullable=False, doc="指派坐席姓名")
    assigned_department = Column(String(128), nullable=False, doc="指派部门")
    status = Column(String(32), default="SUCCESS", doc="移交状态")
    transferred_at = Column(String(32), nullable=False, doc="转交时间戳")
    operator_note = Column(Text, default="", doc="坐席或系统交接附注")
    dialogue_rounds = Column(Integer, default=0, doc="移交前对话轮次")
    context_snapshot_json = Column(Text, nullable=True, doc="冻结上下文数据包 JSON")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "customerName": self.customer_name,
            "vipLevel": self.vip_level or "普通会员",
            "reason": self.reason,
            "triggerType": self.trigger_type or "user_requested",
            "assignedAgentId": self.assigned_agent_id,
            "assignedAgentName": self.assigned_agent_name,
            "assignedDepartment": self.assigned_department,
            "status": self.status or "SUCCESS",
            "transferredAt": self.transferred_at,
            "operatorNote": self.operator_note or "",
            "dialogueRounds": self.dialogue_rounds or 0,
            "contextSnapshot": json.loads(self.context_snapshot_json) if self.context_snapshot_json else None
        }
