"""
实体数据模型定义 (Entity Models)
包含：客户 (Customer)、客服坐席 (Agent)、订单 (Order)、会话 (Session)、移交记录 (TransferLog)
提供严格的字段类型约束、默认值以及与持久化存储（JSON/DB）之间的转换与验证
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
import time
import datetime


# ==================== 1. 客户模型 (Customer Entity) ====================
class CustomerModel(BaseModel):
    id: str = Field(..., description="客户唯一账号标识，如 user_001")
    name: str = Field(..., description="客户姓名或昵称，如 王女士")
    phone: str = Field(default="", description="脱敏或真实手机号，如 138****6699")
    vipLevel: str = Field(default="普通会员", description="会员等级：普通会员 / 黄金会员 / 钻石会员")
    sentiment: str = Field(default="neutral", description="客户当前情绪倾向：positive / neutral / negative / frustrated")
    urgency: str = Field(default="中", description="诉求紧急度：低 / 中 / 高")
    intent: str = Field(default="常规售后咨询", description="主意图定位")
    tags: List[str] = Field(default_factory=list, description="用户画像标签，如 ['黄金会员', '免运费特权']")
    orderId: Optional[str] = Field(default=None, description="当前重点关联的订单号")
    avatar: Optional[str] = Field(default=None, description="客户头像 URL")
    registeredDate: Optional[str] = Field(default="2024-05-12", description="注册入会日期")
    totalOrdersCount: int = Field(default=1, description="累计下单数")
    totalSpent: float = Field(default=0.0, description="历史累计消费金额")
    shippingAddress: Optional[str] = Field(default="", description="默认收件地址")
    updatedAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ==================== 2. 客服坐席模型 (Agent Entity) ====================
class AgentModel(BaseModel):
    id: str = Field(..., description="坐席工号，如 agent_101")
    name: str = Field(..., description="坐席姓名，如 陈浩")
    title: str = Field(default="售后客服专员", description="岗位职称，如 高级售后督导")
    department: str = Field(default="XX商城 客户服务中心", description="所属部门")
    status: str = Field(default="IDLE", description="当前状态：IDLE (空闲在线) / BUSY (忙碌服务中) / OFFLINE (离线)")
    currentWorkload: int = Field(default=0, description="当前承接的实时会话数")
    maxWorkload: int = Field(default=5, description="最大会话容量阈值")
    rating: float = Field(default=4.95, description="历史综合评分 (5分制)")
    specialties: List[str] = Field(default_factory=list, description="擅长专业领域，如 ['7天无理由退货', '黄金会员免运费']")
    recommendedFor: List[str] = Field(default_factory=list, description="智能调度推荐匹配关键词")
    avatar: Optional[str] = Field(default=None, description="坐席头像")
    phone: Optional[str] = Field(default="", description="坐席内线分机")
    email: Optional[str] = Field(default="", description="坐席企业邮箱")
    updatedAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ==================== 3. 订单中台模型 (Order Entity) ====================
class OrderItemModel(BaseModel):
    skuId: str = Field(..., description="商品 SKU 编号")
    title: str = Field(..., description="商品名称")
    category: str = Field(default="生活数码", description="类目")
    spec: str = Field(default="标准款", description="规格属性")
    price: float = Field(..., description="销售单价")
    quantity: int = Field(default=1, description="购买数量")
    imageUrl: Optional[str] = Field(default=None, description="商品首图")
    isSpecialProduct: bool = Field(default=False, description="是否属于特殊不支持退换商品")
    isCustomized: bool = Field(default=False, description="是否属于个人定制商品")


class ExpressTimelineItem(BaseModel):
    time: str = Field(..., description="物流节点时间戳")
    status: str = Field(..., description="节点简述，如 运输中 / 已签收")
    context: str = Field(..., description="详细物流描述与流转记录")


class ExpressModel(BaseModel):
    company: str = Field(default="顺丰速运", description="快递承运公司")
    companyCode: Optional[str] = Field(default="SF", description="承运商代码")
    trackingNumber: str = Field(..., description="快递运单编号")
    status: str = Field(default="DELIVERED", description="运单状态：DELIVERED / IN_TRANSIT / WAREHOUSE_RECEIVED / PENDING_PICKUP")
    statusDescription: str = Field(default="已签收", description="当前物流状态简述")
    timeline: List[ExpressTimelineItem] = Field(default_factory=list, description="全程物流轨迹时序")


class OrderReceiverModel(BaseModel):
    name: str = Field(..., description="收件人姓名")
    phone: str = Field(..., description="收件人电话")
    address: str = Field(..., description="详细配送地址")


class OrderAfterSalesModel(BaseModel):
    canReturn7Days: bool = Field(default=True, description="是否符合7天无理由退货条件")
    returnDaysRemaining: int = Field(default=0, description="7天无理由退货剩余有效天数")
    signedDays: int = Field(default=0, description="自签收起的自然日天数")
    returnPolicy: str = Field(default="支持7天无理由退货", description="退换政策明细")
    shippingSubsidy: str = Field(default="按商城基础运费规则", description="运费承担与会员补贴权益")
    warrantyStatus: str = Field(default="全国联保生效中", description="保修状态")
    warrantyExpiredDate: str = Field(default="2027-03-25", description="保修截至日期")
    warrantyPolicy: str = Field(default="1年全国联保，15天免费换新机", description="保修权益条款")


class OrderModel(BaseModel):
    orderId: str = Field(..., description="业务订单号，如 ORD-2026-88992")
    orderSn: str = Field(..., description="全数字支付流水号，如 202603258899201")
    userId: str = Field(..., description="关联购买客户 ID，如 user_001")
    userName: str = Field(..., description="客户姓名")
    userPhone: str = Field(default="", description="下单联系电话")
    vipLevel: str = Field(default="普通会员", description="下单时的客户 VIP 级别")
    status: str = Field(default="DELIVERED", description="状态码：DELIVERED / IN_TRANSIT / RETURNING_INSPECTION / COMPLETED / PENDING_PAYMENT")
    statusText: str = Field(default="已签收", description="展示状态名")
    statusCode: int = Field(default=4, description="状态顺序码 (1~6)")
    createTime: str = Field(..., description="下单时间")
    payTime: Optional[str] = Field(default=None, description="支付成功时间")
    shipTime: Optional[str] = Field(default=None, description="仓库发货时间")
    deliveryTime: Optional[str] = Field(default=None, description="最终签收时间")
    items: List[OrderItemModel] = Field(default_factory=list, description="订单商品行项目列表")
    totalAmount: float = Field(..., description="订单总金额")
    paidAmount: float = Field(..., description="客户实付金额")
    shippingFee: float = Field(default=0.0, description="实收运费")
    express: ExpressModel = Field(..., description="物流配送轨迹信息")
    receiver: OrderReceiverModel = Field(..., description="收货地址信息")
    afterSales: OrderAfterSalesModel = Field(..., description="售后服务与权益判定快照")
    updatedAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ==================== 4. 消息与会话模型 (Message & Session Entity) ====================
class ChatMessageModel(BaseModel):
    id: str = Field(..., description="消息唯一ID，如 m_171000000_1")
    role: str = Field(..., description="发言角色：user (客户) / assistant (AI) / human_agent (人工坐席) / system (系统公告)")
    content: str = Field(..., description="消息正文")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%H:%M:%S"), description="发送时分秒")
    confidenceScore: Optional[float] = Field(default=None, description="AI 答复置信度")
    sentiment: Optional[str] = Field(default=None, description="情感识别")
    intent: Optional[str] = Field(default=None, description="意图识别")
    references: Optional[List[Dict[str, Any]]] = Field(default=None, description="知识库引用溯源")
    stepTrace: Optional[List[Dict[str, Any]]] = Field(default=None, description="LangGraph 决策链路追踪")
    queriedOrder: Optional[Dict[str, Any]] = Field(default=None, description="挂载的订单卡片数据")


class SessionMetricsModel(BaseModel):
    totalTurns: int = Field(default=0, description="对话总轮次")
    avgLatencyMs: int = Field(default=320, description="平均响应延时(毫秒)")
    avgConfidence: float = Field(default=0.95, description="平均置信度")
    escalatedAt: Optional[str] = Field(default=None, description="转人工介入时间")


class SessionModel(BaseModel):
    id: str = Field(..., description="会话唯一 ID，如 session_user_001")
    userName: str = Field(default="客户", description="客户昵称")
    status: str = Field(default="AI_HANDLING", description="会话状态：AI_HANDLING / NEEDS_INTERVENTION / HUMAN_INTERVENED / RESOLVED")
    assignedAgent: Optional[str] = Field(default=None, description="指派的人工坐席姓名")
    assignedAgentId: Optional[str] = Field(default=None, description="指派的人工坐席工号")
    customerProfile: Dict[str, Any] = Field(default_factory=dict, description="挂载的客户画像")
    summaryMemory: str = Field(default="", description="长期工作记忆摘要")
    messages: List[ChatMessageModel] = Field(default_factory=list, description="全量消息时序流")
    metrics: SessionMetricsModel = Field(default_factory=SessionMetricsModel, description="会话指标快照")
    contextSnapshot: Optional[Dict[str, Any]] = Field(default=None, description="转交工单快照")
    latestTransfer: Optional[Dict[str, Any]] = Field(default=None, description="最新一次转人工记录")
    unreadForAgent: bool = Field(default=False, description="人工坐席未读标红")
    createdAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updatedAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ==================== 5. 工单转接审计模型 (Transfer Log Entity) ====================
class TransferLogModel(BaseModel):
    id: str = Field(..., description="转接工单编号，如 TRF-1710000000-A1B2")
    sessionId: str = Field(..., description="关联会话 ID")
    customerName: str = Field(..., description="客户姓名")
    vipLevel: str = Field(default="普通会员", description="客户等级")
    reason: str = Field(..., description="转人工理由")
    triggerType: str = Field(default="user_requested", description="触发源类型：user_requested / low_confidence / emotion_warning / manual_dispatch")
    assignedAgentId: str = Field(..., description="指派坐席工号")
    assignedAgentName: str = Field(..., description="指派坐席姓名")
    assignedDepartment: str = Field(default="XX商城 售后服务中心", description="指派部门")
    status: str = Field(default="SUCCESS", description="工单状态：SUCCESS / TRANSFERRED / CANCELLED")
    transferredAt: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    operatorNote: Optional[str] = Field(default="", description="前台备注")
    dialogueRounds: int = Field(default=0, description="移交前对话轮数")
    contextSnapshot: Optional[Dict[str, Any]] = Field(default=None, description="移交当时的上下文全量冻结包")
