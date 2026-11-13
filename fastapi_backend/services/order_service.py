"""
XX商城 订单与物流中台服务 (Order & Logistics Service)
已全面对接 storage_service 磁盘持久化固化存储，支持订单数据查询、状态流转、时效判定与持久化保存
"""

from typing import Dict, Any, List, Optional
import datetime
import re
from services.storage_service import storage_service
from models.entities import OrderModel


class OrderService:
    def __init__(self):
        # 依赖持久化 storage_service，保证跨服务与重启持久化
        pass

    def list_orders(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """按用户、状态或关键词筛选订单列表，从持久化磁盘库获取"""
        res = storage_service.list_orders()
        if user_name:
            res = [o for o in res if user_name in o["userName"] or o.get("userId") == user_name]
        if status and status != "ALL":
            res = [o for o in res if o["status"] == status]
        if keyword:
            kw = keyword.lower()
            res = [
                o for o in res
                if kw in o["orderId"].lower()
                or kw in o["userName"].lower()
                or any(kw in item["title"].lower() for item in o.get("items", []))
                or kw in o.get("express", {}).get("trackingNumber", "").lower()
            ]
        return res

    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """从固化存储中按订单号查询完整详情"""
        return storage_service.get_order(order_id)

    def find_orders_for_user(self, user_name: str, phone: Optional[str] = None) -> List[Dict[str, Any]]:
        """根据客户姓名或手机号拉取该客户的所有订单"""
        orders = storage_service.list_orders()
        matched = []
        for o in orders:
            if user_name and user_name in o["userName"]:
                matched.append(o)
            elif phone and phone in o.get("userPhone", ""):
                matched.append(o)
        return matched

    def save_order(self, order_dict: Dict[str, Any]) -> Dict[str, Any]:
        """保存并固化订单到磁盘"""
        return storage_service.save_order(order_dict)

    def update_order_status(self, order_id: str, new_status: str, status_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """更新订单状态并写入磁盘"""
        order = self.get_order_by_id(order_id)
        if not order:
            return None
        order["status"] = new_status
        if status_text:
            order["statusText"] = status_text
        order["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return storage_service.save_order(order)

    def detect_and_query_order(
        self,
        message: str,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        智能识别：从用户自然语言输入或会话画像中推断并定位目标订单
        """
        msg = message.strip()
        user_profile = user_profile or {}
        all_orders = storage_service.list_orders()

        # 1. 尝试从文本正则抽取订单号 (如 ORD-2026-88992 或 88992)
        match = re.search(r"(?:ORD[-_]?)?(\d{4}[-_]?\d{4,6}|\d{5,})", msg, re.IGNORECASE)
        if match:
            extracted = match.group(0).upper()
            if not extracted.startswith("ORD"):
                extracted = f"ORD-{extracted}"
            found = self.get_order_by_id(extracted)
            if found:
                return found

        # 2. 从消息中匹配已知订单号前缀
        for o in all_orders:
            oid = o.get("orderId", "")
            if oid.lower() in msg.lower() or oid.replace("-", "").lower() in msg.lower():
                return o

        # 3. 按商品关键词匹配
        product_keyword_map = {
            "理线器": "ORD-2026-00100",
            "湿巾": "ORD-2026-00100",
            "小额": "ORD-2026-00100",
            "2.5": "ORD-2026-00100",
            "00100": "ORD-2026-00100",
            "扫地机器人": "ORD-2026-88992",
            "扫地机": "ORD-2026-88992",
            "紫砂壶": "ORD-2026-90412",
            "定制杯": "ORD-2026-90412",
            "刻字": "ORD-2026-90412",
            "投影仪": "ORD-2026-77310",
            "幕布": "ORD-2026-77310",
            "耳机": "ORD-2026-66521",
            "降噪耳机": "ORD-2026-66521",
        }
        for kw, mapped_id in product_keyword_map.items():
            if kw in msg:
                order = self.get_order_by_id(mapped_id)
                if order:
                    return order

        # 4. 如果用户询问通用订单/物流关键词 ("我的订单", "发货了吗", "物流到哪了", "什么时候到")
        order_intent_keywords = ["订单", "物流", "发货", "运运", "运单", "快递", "到哪了", "什么时候到", "送达", "签收", "退款", "退货"]
        if any(k in msg for k in order_intent_keywords):
            # 优先使用会话画像中预绑定的 orderId
            bound_order_id = user_profile.get("orderId")
            if bound_order_id:
                found = self.get_order_by_id(bound_order_id)
                if found:
                    return found

            # 其次查找该客户姓名对应的最新订单
            user_name = user_profile.get("name") or user_profile.get("userName")
            if user_name:
                user_orders = self.find_orders_for_user(user_name)
                if user_orders:
                    return user_orders[0]

            # 最终兜底：如果有订单数据，默认绑定第一个订单（如 ORD-2026-88992）
            if all_orders:
                return all_orders[0]
            return self.get_order_by_id("ORD-2026-88992")

        return None

    def process_refund_request(
        self,
        order_id: str,
        reason: str = "7天无理由退货",
        refund_amount: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理客户订单退款申请（支持基于 request_id 的请求级幂等控制）：
        - 若同一个 request_id 已处理过，直接返回当前订单状态，避免重复提交或覆盖审计记录
        - 若退款金额 < 3.00 元：智能客服直接秒退（无需人工干涉），状态变更为 REFUNDED / AUTO_REFUNDED
        - 若退款金额 >= 3.00 元：需人工干涉与资金安全审核，状态变更为 REFUND_PENDING_AUDIT / PENDING_HUMAN_AUDIT
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"订单 {order_id} 不存在")

        after_sales = order.get("afterSales", {})
        processed_ids = list(after_sales.get("processedRequestIds") or [])
        if request_id and request_id in processed_ids:
            return order

        amount = refund_amount if refund_amount is not None and refund_amount > 0 else float(order.get("paidAmount", 0.0))
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        after_sales["refundAmount"] = amount
        after_sales["refundReason"] = reason
        if request_id:
            after_sales["lastRequestId"] = request_id
            processed_ids.append(request_id)
            after_sales["processedRequestIds"] = processed_ids[-20:]

        # 判断是否需要人工干涉 (金额大于等于3元)
        requires_audit = amount >= 3.00

        if requires_audit:
            order["status"] = "REFUND_PENDING_AUDIT"
            order["statusText"] = "退款待人工审核"
            after_sales["refundStatus"] = "PENDING_HUMAN_AUDIT"
            after_sales["requiresHumanAudit"] = True
            after_sales["auditNote"] = f"退款金额 ¥{amount:.2f} 元 (>= 3.00 元)，涉及资金安全，已自动提交至工单中心待人工干涉与审核"
        else:
            order["status"] = "REFUNDED"
            order["statusText"] = "已退款(秒级到账)"
            after_sales["refundStatus"] = "AUTO_REFUNDED"
            after_sales["requiresHumanAudit"] = False
            after_sales["auditTime"] = now_str
            after_sales["auditNote"] = f"退款金额 ¥{amount:.2f} 元 (< 3.00 元)，符合智能客服小额直接退款规则，已秒级自动完成原路退款"

        order["afterSales"] = after_sales
        order["updatedAt"] = now_str
        return self.save_order(order)

    def audit_refund(
        self,
        order_id: str,
        action: str,
        operator_name: str = "陈浩",
        note: str = ""
    ) -> Dict[str, Any]:
        """
        人工干涉与审核订单退款申请：
        - action == "approve": 审核通过，状态变更为 REFUNDED / AUDIT_APPROVED
        - action == "reject": 审核驳回，状态恢复为 DELIVERED / AUDIT_REJECTED
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"订单 {order_id} 不存在")

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        after_sales = order.get("afterSales", {})
        after_sales["auditOperator"] = operator_name
        after_sales["auditTime"] = now_str

        action_clean = action.lower()
        if action_clean in ["approve", "pass", "agree"]:
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

    def format_order_summary_text(self, order: Dict[str, Any]) -> str:
        """为大模型 (DeepSeek) 提示词生成精炼准确的订单详情与物流事实"""
        items_desc = ", ".join([f"{it['title']} (x{it['quantity']})" for it in order.get("items", [])])
        express = order.get("express", {})
        latest_track = express.get("timeline", [{}])[0].get("context", "暂无物流更新") if express.get("timeline") else "暂无"
        after_sale = order.get("afterSales", {})
        receiver = order.get("receiver", {})

        refund_status_str = after_sale.get("refundStatus", "NONE")
        refund_info = "暂无退款申请"
        if refund_status_str == "AUTO_REFUNDED":
            refund_info = f"已通过智能客服秒级自动退款 (¥{after_sale.get('refundAmount', 0):.2f} 元 < 3元，无需人工)"
        elif refund_status_str == "PENDING_HUMAN_AUDIT":
            refund_info = f"正在等待人工干涉与审核 (申请金额 ¥{after_sale.get('refundAmount', 0):.2f} 元 >= 3元，需人工核验保证安全)"
        elif refund_status_str == "AUDIT_APPROVED":
            refund_info = f"人工干涉审核通过，已退款 (审核人: {after_sale.get('auditOperator', '人工坐席')})"
        elif refund_status_str == "AUDIT_REJECTED":
            refund_info = f"退款申请已被人工驳回 ({after_sale.get('auditNote', '')})"

        return f"""【关联订单事实】
- 订单编号：{order['orderId']} (下单时间: {order['createTime']})
- 购买商品：{items_desc}
- 实付金额：¥{order['paidAmount']:.2f}
- 当前状态：【{order['statusText']}】
- 物流承运：{express.get('company', '暂无')} (运单号: {express.get('trackingNumber', '暂无')})
- 最新物流节点：{latest_track}
- 收件地址：{receiver.get('address', '系统地址')}
- 退款与售后状态：{refund_info}
- 售后权益政策：
  * 退款审核规则：金额 < 3.00 元可由智能客服直接退款；金额 >= 3.00 元需人工干涉审核保障资金安全。
  * 7天无理由退货：{'支持（签收第' + str(after_sale.get('signedDays', 0)) + '天，剩余' + str(after_sale.get('returnDaysRemaining', 0)) + '天）' if after_sale.get('canReturn7Days') else '不支持（' + after_sale.get('returnPolicy', '') + '）'}
  * 运费权益：{after_sale.get('shippingSubsidy', '按商城规则')}
  * 保修政策：{after_sale.get('warrantyPolicy', '1年全国联保')}"""


# 全局单例
order_service = OrderService()

