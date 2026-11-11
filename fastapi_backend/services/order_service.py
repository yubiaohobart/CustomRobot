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
        order_intent_keywords = ["订单", "物流", "发货", "运单", "快递", "到哪了", "什么时候到", "送达", "签收"]
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

        return None

    def format_order_summary_text(self, order: Dict[str, Any]) -> str:
        """为大模型 (DeepSeek) 提示词生成精炼准确的订单详情与物流事实"""
        items_desc = ", ".join([f"{it['title']} (x{it['quantity']})" for it in order.get("items", [])])
        express = order.get("express", {})
        latest_track = express.get("timeline", [{}])[0].get("context", "暂无物流更新") if express.get("timeline") else "暂无"
        after_sale = order.get("afterSales", {})
        receiver = order.get("receiver", {})

        return f"""【关联订单事实】
- 订单编号：{order['orderId']} (下单时间: {order['createTime']})
- 购买商品：{items_desc}
- 实付金额：¥{order['paidAmount']:.2f}
- 当前状态：【{order['statusText']}】
- 物流承运：{express.get('company', '暂无')} (运单号: {express.get('trackingNumber', '暂无')})
- 最新物流节点：{latest_track}
- 收件地址：{receiver.get('address', '系统地址')}
- 售后权益状态：
  * 7天无理由退货：{'支持（签收第' + str(after_sale.get('signedDays', 0)) + '天，剩余' + str(after_sale.get('returnDaysRemaining', 0)) + '天）' if after_sale.get('canReturn7Days') else '不支持（' + after_sale.get('returnPolicy', '') + '）'}
  * 运费权益：{after_sale.get('shippingSubsidy', '按商城规则')}
  * 保修政策：{after_sale.get('warrantyPolicy', '1年全国联保')}"""


# 全局单例
order_service = OrderService()
