"""
XX商城 订单与物流中台服务 (Order & Logistics Service)
已全面对接 storage_service PostgreSQL 持久化存储，支持订单检索、归属校验、退款阈值分流与人工审批。
"""

from typing import Dict, Any, List, Optional, Tuple
import datetime
import re
from services.storage_service import storage_service
from config import settings, PROCESSED_REQUEST_IDS_LIMIT


class OrderNotFoundError(LookupError, ValueError):
    """订单不存在异常（同时继承 LookupError 与 ValueError，兼容已有捕获逻辑并支持路由区分 404/400）"""


_APPROVE_ACTIONS = frozenset({"approve", "pass", "agree"})
_REJECT_ACTIONS = frozenset({"reject", "deny", "refuse"})

# 演示商品口语别名 -> 订单商品标题匹配关键词（仅在归属当前客户的订单范围内匹配）
_PRODUCT_ALIAS_TO_TITLE_KW = {
    "理线器": "理线器",
    "湿巾": "湿巾",
    "小额": "理线器",
    "2.5": "理线器",
    "扫地机器人": "扫地机器人",
    "扫地机": "扫地机器人",
    "紫砂壶": "紫砂壶",
    "定制杯": "定制",
    "刻字": "刻字",
    "投影仪": "投影仪",
    "幕布": "幕布",
    "耳机": "耳机",
    "降噪耳机": "降噪耳机",
}

_ORDER_INTENT_KEYWORDS = (
    "订单", "物流", "发货", "货运", "转运", "运单", "快递",
    "到哪了", "什么时候到", "送达", "签收", "退款", "退货",
)

_ORDER_ID_RE = re.compile(r"(?:ORD[-_])?(\d{4}[-_]\d{4,6})\b|\bORD[-_](\d{5,6})\b", re.IGNORECASE)


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _calc_refund_amount_cents(order: Dict[str, Any], refund_amount: Optional[float] = None) -> Tuple[float, int]:
    """统一计算退款金额（元 & 分，避免浮点比较精度误差）"""
    if refund_amount is not None and refund_amount > 0:
        amount = round(float(refund_amount), 2)
    else:
        amount = round(float(order.get("paidAmount", 0.0) or 0.0), 2)
    return amount, int(round(amount * 100))


def _build_refund_outcome(
    order_id: str,
    request_id: str,
    status: str,
    reply: str,
    *,
    handoff: bool = False,
    escalation_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "order_id": order_id,
        "request_id": request_id,
        "status": status,
        "reply": reply,
        "handoff": handoff,
        "escalation_reason": escalation_reason,
    }


class OrderService:
    @staticmethod
    def _is_owned_by_profile(
        order: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """校验订单是否归属当前客户（占位访客画像放行，具名客户严格隔离）"""
        profile = user_profile or {}
        profile_name = (profile.get("name") or profile.get("userName") or "").strip()
        is_placeholder = not profile_name or "客户" in profile_name or "访客" in profile_name
        if is_placeholder:
            return True
        return profile_name in (order.get("userName") or "")

    def list_orders(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按用户、状态或关键词筛选订单列表（状态过滤下推至 SQL）"""
        db_status = None if not status or status == "ALL" else status
        res = storage_service.list_orders(status=db_status)
        if user_name:
            res = [
                o for o in res
                if user_name in (o.get("userName") or "") or o.get("userId") == user_name
            ]
        if keyword:
            kw = keyword.lower()
            res = [
                o for o in res
                if kw in (o.get("orderId") or "").lower()
                or kw in (o.get("userName") or "").lower()
                or any(kw in (item.get("title") or "").lower() for item in (o.get("items") or []))
                or kw in ((o.get("express") or {}).get("trackingNumber") or "").lower()
            ]
        return res

    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """从固化存储中按订单号查询完整详情"""
        return storage_service.get_order(order_id)

    def get_owned_order(
        self,
        order_id: Optional[str],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """校验并加载归属当前客户的持久化订单，防止跨客户越权查询或退款"""
        if not order_id:
            return None
        persisted = self.get_order_by_id(order_id)
        if not persisted:
            return None
        return persisted if self._is_owned_by_profile(persisted, user_profile) else None

    def find_orders_for_user(self, user_name: str, phone: Optional[str] = None) -> List[Dict[str, Any]]:
        """根据客户姓名或手机号拉取该客户的所有订单"""
        orders = storage_service.list_orders()
        return [
            o for o in orders
            if (user_name and user_name in (o.get("userName") or ""))
            or (phone and phone in (o.get("userPhone") or ""))
        ]

    def save_order(self, order_dict: Dict[str, Any]) -> Dict[str, Any]:
        """保存并固化订单到数据库"""
        return storage_service.save_order(order_dict)

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        status_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新订单状态并写入数据库"""
        order = self.get_order_by_id(order_id)
        if not order:
            return None
        order["status"] = new_status
        if status_text:
            order["statusText"] = status_text
        order["updatedAt"] = _now_str()
        return storage_service.save_order(order)

    def detect_and_query_order(
        self,
        message: str,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        智能识别：从用户自然语言输入或会话画像中推断并定位归属当前客户的订单（单次查库，严格隔离跨客户订单）
        """
        msg = (message or "").strip()
        if not msg:
            return None

        user_profile = user_profile or {}
        all_orders = storage_service.list_orders()
        scoped_orders = [o for o in all_orders if self._is_owned_by_profile(o, user_profile)]
        if not scoped_orders:
            return None

        scoped_by_id = {(o.get("orderId") or "").upper(): o for o in scoped_orders if o.get("orderId")}
        msg_lower = msg.lower()
        msg_compact = msg_lower.replace("-", "").replace("_", "")

        # 1. 从文本正则抽取规范化订单号 (如 ORD-2026-88992 / ord_2026_88992 / ORD-00100)
        match = _ORDER_ID_RE.search(msg)
        if match:
            raw_part = (match.group(1) or match.group(2) or "").replace("_", "-").upper()
            candidate_id = raw_part if raw_part.startswith("ORD-") else f"ORD-{raw_part}"
            if candidate_id in scoped_by_id:
                return scoped_by_id[candidate_id]
            return None

        # 2. 在当前客户订单中直接匹配订单号或后段数字编号
        for o in scoped_orders:
            oid = o.get("orderId") or ""
            oid_lower = oid.lower()
            if oid_lower in msg_lower or oid_lower.replace("-", "") in msg_compact:
                return o
            tail_num = oid.rsplit("-", 1)[-1]
            if len(tail_num) >= 5 and tail_num in msg:
                return o

        # 3. 基于当前客户订单商品标题与常见口语别名动态匹配
        for o in scoped_orders:
            titles = " ".join((it.get("title") or "") for it in (o.get("items") or []))
            if not titles:
                continue
            for alias, title_kw in _PRODUCT_ALIAS_TO_TITLE_KW.items():
                if alias in msg and title_kw in titles:
                    return o
            # 支持任意新建订单的商品标题关键词（取长度 >= 2 的词组）直接命中
            for it in o.get("items") or []:
                title = (it.get("title") or "").strip()
                if title and len(title) >= 2 and any(
                    seg in msg for seg in re.split(r"[\s/()（）]+", title) if len(seg) >= 2
                ):
                    return o

        # 若客户明确点名了其他品类的商品别名但当前客户名下无对应订单，不强行兜底到无关订单
        if any(alias in msg for alias in _PRODUCT_ALIAS_TO_TITLE_KW):
            return None

        # 4. 通用订单/物流/退款意图兜底（仅在当前客户已归属的订单范围内选择）
        if any(k in msg for k in _ORDER_INTENT_KEYWORDS):
            bound_order_id = (user_profile.get("orderId") or "").upper()
            if bound_order_id and bound_order_id in scoped_by_id:
                return scoped_by_id[bound_order_id]
            return scoped_orders[0]

        return None

    def _apply_refund_to_order(
        self,
        order: Dict[str, Any],
        reason: str,
        refund_amount: Optional[float],
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        """在已加载且通过前置校验的订单对象上执行退款落盘与幂等流水记录"""
        after_sales = dict(order.get("afterSales") or {})
        processed_ids = list(after_sales.get("processedRequestIds") or [])
        if request_id and request_id in processed_ids:
            return order

        amount, amount_cents = _calc_refund_amount_cents(order, refund_amount)
        limit_cents = settings.auto_refund_limit_cents
        limit_text = settings.auto_refund_limit_text
        now_str = _now_str()

        after_sales["refundAmount"] = amount
        after_sales["refundReason"] = reason
        if request_id:
            after_sales["lastRequestId"] = request_id
            processed_ids.append(request_id)
            after_sales["processedRequestIds"] = processed_ids[-PROCESSED_REQUEST_IDS_LIMIT:]

        if amount_cents >= limit_cents:
            order["status"] = "REFUND_PENDING_AUDIT"
            order["statusText"] = "退款待人工审核"
            after_sales["refundStatus"] = "PENDING_HUMAN_AUDIT"
            after_sales["requiresHumanAudit"] = True
            after_sales["auditNote"] = (
                f"退款金额 ¥{amount:.2f} 元 (>= {limit_text} 元)，涉及资金安全，已自动提交至工单中心待人工干涉与审核"
            )
        else:
            order["status"] = "REFUNDED"
            order["statusText"] = "已退款(秒级到账)"
            after_sales["refundStatus"] = "AUTO_REFUNDED"
            after_sales["requiresHumanAudit"] = False
            after_sales["auditTime"] = now_str
            after_sales["auditNote"] = (
                f"退款金额 ¥{amount:.2f} 元 (< {limit_text} 元)，符合智能客服小额直接退款规则，已秒级自动完成原路退款"
            )

        order["afterSales"] = after_sales
        order["updatedAt"] = now_str
        return self.save_order(order)

    def process_refund_request(
        self,
        order_id: str,
        reason: str = "7天无理由退货",
        refund_amount: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理客户订单退款申请（支持 request_id 幂等控制与重复提交状态拦截）：
        - 若同一个 request_id 已处理过，直接返回当前订单状态
        - 若订单已退款或待人工审核，拒绝重复覆写
        - 金额 < AUTO_REFUND_LIMIT_YUAN：自动秒退 (REFUNDED / AUTO_REFUNDED)
        - 金额 >= AUTO_REFUND_LIMIT_YUAN：转人工审核 (REFUND_PENDING_AUDIT / PENDING_HUMAN_AUDIT)
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderNotFoundError(f"订单 {order_id} 不存在")

        after_sales = dict(order.get("afterSales") or {})
        processed_ids = after_sales.get("processedRequestIds") or []
        if request_id and request_id in processed_ids:
            return order

        current_status = order.get("status")
        if current_status in ("REFUNDED", "REFUND_PENDING_AUDIT"):
            raise ValueError(f"订单 {order_id} 当前状态为【{order.get('statusText') or current_status}】，不可重复提交退款")

        return self._apply_refund_to_order(order, reason, refund_amount, request_id)

    def audit_refund(
        self,
        order_id: str,
        action: str,
        operator_name: str = "陈浩",
        note: str = "",
    ) -> Dict[str, Any]:
        """
        人工干涉与审核订单退款申请：
        - action in approve/pass/agree: 审核通过 -> REFUNDED / AUDIT_APPROVED
        - action in reject/deny/refuse: 审核驳回 -> DELIVERED / AUDIT_REJECTED
        """
        action_clean = (action or "").strip().lower()
        if action_clean not in _APPROVE_ACTIONS and action_clean not in _REJECT_ACTIONS:
            raise ValueError(f"非法审核动作 '{action}'，仅支持 approve 或 reject")

        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderNotFoundError(f"订单 {order_id} 不存在")

        if order.get("status") != "REFUND_PENDING_AUDIT":
            raise ValueError(f"订单 {order_id} 当前状态为【{order.get('statusText') or order.get('status')}】，仅待人工审核订单可执行审批")

        now_str = _now_str()
        after_sales = dict(order.get("afterSales") or {})
        after_sales["auditOperator"] = operator_name
        after_sales["auditTime"] = now_str

        if action_clean in _APPROVE_ACTIONS:
            order["status"] = "REFUNDED"
            order["statusText"] = "已退款(人工审核通过)"
            after_sales["refundStatus"] = "AUDIT_APPROVED"
            after_sales["auditNote"] = note or f"人工坐席【{operator_name}】干涉核验通过，资金已原路退回解冻"
        else:
            order["status"] = "DELIVERED"
            order["statusText"] = "退款已驳回"
            after_sales["refundStatus"] = "AUDIT_REJECTED"
            after_sales["auditNote"] = note or f"人工坐席【{operator_name}】核验驳回退款申请，原因: 不符合退换货政策"

        order["afterSales"] = after_sales
        order["updatedAt"] = now_str
        return self.save_order(order)

    def build_refund_gate_reply(self, order: Dict[str, Any]) -> str:
        """生成退款二次确认门控提示文案"""
        oid = order.get("orderId", "")
        amount, amount_cents = _calc_refund_amount_cents(order)
        limit_cents = settings.auto_refund_limit_cents
        limit_text = settings.auto_refund_limit_text
        current_status = order.get("status", "")
        header = f"收到您针对订单【{oid}】（实付 ¥{amount:.2f} 元）的退款申请。\n"

        if current_status == "REFUND_PENDING_AUDIT":
            return (
                f"{header}该订单当前正处于【退款待人工审核】状态（因金额 >= {limit_text} 元触发资金安全人工干涉）。\n"
                f"如需确认或变更诉求，请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
            )
        if current_status == "REFUNDED":
            return (
                f"{header}系统显示该订单此前已完成退款解冻。\n"
                f"您可在下方卡片中点击【确认提交退款】复核退款状态，或点击【取消 / 我再想想】退出："
            )
        rule_text = (
            f"金额 < {limit_text} 元，确认后将由智能客服直接秒退"
            if amount_cents < limit_cents
            else f"金额 >= {limit_text} 元，确认后将提交人工干涉与资金安全审核"
        )
        return (
            f"{header}根据商城退款规则（{rule_text}），在正式提交前，请您确认以下权益调整：\n"
            f"• 订单对应的黄金/钻石会员积分及运费补贴将同步收回；\n"
            f"• 退款将通过原支付渠道（支付宝/微信/银行卡）解冻退回。\n\n"
            f"请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
        )

    def execute_refund_decision(
        self,
        order: Dict[str, Any],
        action: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """执行退款确认/取消业务决策（含 request_id 幂等去重与动态审核阈值分流）"""
        oid = order.get("orderId", "")
        amount, amount_cents = _calc_refund_amount_cents(order)
        limit_cents = settings.auto_refund_limit_cents
        limit_text = settings.auto_refund_limit_text
        current_status = order.get("status", "")
        processed_ids = (order.get("afterSales") or {}).get("processedRequestIds") or []

        if action == "cancel":
            return _build_refund_outcome(
                oid,
                request_id,
                "CANCELED",
                f"已为您取消退款申请，订单【{oid}】将保持正常签收状态。如需其他帮助，随时联系我！",
            )

        if request_id and request_id in processed_ids:
            draft_status = "PENDING_AUDIT" if current_status == "REFUND_PENDING_AUDIT" else "SUBMITTED"
            return _build_refund_outcome(
                oid,
                request_id,
                draft_status,
                f"【幂等提示】您的本次退款申请（流水号：{request_id}）已成功受理，订单【{oid}】无需重复提交。",
            )

        if current_status == "REFUNDED":
            return _build_refund_outcome(
                oid,
                request_id,
                "SUBMITTED",
                f"【温馨提示】订单【{oid}】此前已完成退款，款项已原路退回解冻，请您查收账户通知！",
            )

        if current_status == "REFUND_PENDING_AUDIT":
            return _build_refund_outcome(
                oid,
                request_id,
                "PENDING_AUDIT",
                f"【温馨提示】订单【{oid}】的退款审核工单已在处理中，无需重复提交，专员正在加急核验！",
            )

        if amount_cents < limit_cents:
            self._apply_refund_to_order(
                order,
                reason="用户二次确认提交退款(自动秒退)",
                refund_amount=amount,
                request_id=request_id,
            )
            return _build_refund_outcome(
                oid,
                request_id,
                "SUBMITTED",
                f"【智能客服秒退成功】您已二次确认！订单【{oid}】实付金额为 ¥{amount:.2f} 元 (< {limit_text} 元)，智能客服已为您直接原路退回解冻，请查收！",
            )

        self._apply_refund_to_order(
            order,
            reason="用户二次确认提交退款(人工审核)",
            refund_amount=amount,
            request_id=request_id,
        )
        return _build_refund_outcome(
            oid,
            request_id,
            "PENDING_AUDIT",
            f"【退款审核工单已提交】您已二次确认！订单【{oid}】实付金额为 ¥{amount:.2f} 元 (>= {limit_text} 元)，涉及商城资金安全，已自动为您无缝对接人工客服加急干涉与核验！",
            handoff=True,
            escalation_reason=f"订单 {oid} 申请退款金额 ¥{amount:.2f} 元 (>= {limit_text} 元)，涉及资金安全，已通过二次确认提交至人工干涉与审核队列",
        )

    def format_order_summary_text(self, order: Dict[str, Any]) -> str:
        """为大模型 (DeepSeek) 提示词生成精炼准确的订单详情与物流事实"""
        items_desc = ", ".join(
            f"{it.get('title', '商品')} (x{it.get('quantity', 1)})"
            for it in (order.get("items") or [])
        ) or "暂无商品明细"
        express = order.get("express") or {}
        timeline = express.get("timeline") or []
        latest_track = (timeline[0] or {}).get("context", "暂无物流更新") if timeline else "暂无"
        after_sale = order.get("afterSales") or {}
        receiver = order.get("receiver") or {}
        limit_text = settings.auto_refund_limit_text

        refund_status_str = after_sale.get("refundStatus", "NONE")
        refund_info = "暂无退款申请"
        if refund_status_str == "AUTO_REFUNDED":
            refund_info = f"已通过智能客服秒级自动退款 (¥{after_sale.get('refundAmount', 0):.2f} 元 < {limit_text} 元，无需人工)"
        elif refund_status_str == "PENDING_HUMAN_AUDIT":
            refund_info = f"正在等待人工干涉与审核 (申请金额 ¥{after_sale.get('refundAmount', 0):.2f} 元 >= {limit_text} 元，需人工核验保证安全)"
        elif refund_status_str == "AUDIT_APPROVED":
            refund_info = f"人工干涉审核通过，已退款 (审核人: {after_sale.get('auditOperator', '人工坐席')})"
        elif refund_status_str == "AUDIT_REJECTED":
            refund_info = f"退款申请已被人工驳回 ({after_sale.get('auditNote', '')})"

        return f"""【关联订单事实】
- 订单编号：{order.get('orderId', '')} (下单时间: {order.get('createTime', '未知')})
- 购买商品：{items_desc}
- 实付金额：¥{float(order.get('paidAmount', 0.0) or 0.0):.2f}
- 当前状态：【{order.get('statusText', order.get('status', '未知'))}】
- 物流承运：{express.get('company', '暂无')} (运单号: {express.get('trackingNumber', '暂无')})
- 最新物流节点：{latest_track}
- 收件地址：{receiver.get('address', '系统地址')}
- 退款与售后状态：{refund_info}
- 售后权益政策：
  * 退款审核规则：金额 < {limit_text} 元可由智能客服直接退款；金额 >= {limit_text} 元需人工干涉审核保障资金安全。
  * 7天无理由退货：{'支持（签收第' + str(after_sale.get('signedDays', 0)) + '天，剩余' + str(after_sale.get('returnDaysRemaining', 0)) + '天）' if after_sale.get('canReturn7Days') else '不支持（' + after_sale.get('returnPolicy', '') + '）'}
  * 运费权益：{after_sale.get('shippingSubsidy', '按商城规则')}
  * 保修政策：{after_sale.get('warrantyPolicy', '1年全国联保')}"""


# 全局单例
order_service = OrderService()
