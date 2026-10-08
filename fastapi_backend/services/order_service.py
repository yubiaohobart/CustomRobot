"""
XX商城 订单与物流中台服务 (Order & Logistics Service)
提供：
1. 订单详情与历史检索（按订单号、用户、手机号、商品关键词）
2. 物流轨迹追踪与时效推算（顺丰、京东等真实节点）
3. 售后权益判定（7天无理由退换资格、剩余天数、1年全国联保到期日、会员免运费资格）
4. 为大模型 (DeepSeek) 与 LangGraph 节点提供结构化上下文注入
"""

from typing import Dict, Any, List, Optional
import datetime
import re

# XX商城 模拟订单数据库（涵盖不同会员、商品类型、物流状态及售后情景）
MOCK_ORDERS: List[Dict[str, Any]] = [
    {
        "orderId": "ORD-2026-88992",
        "orderSn": "202603258899201",
        "userId": "user_001",
        "userName": "王女士",
        "userPhone": "138****6699",
        "vipLevel": "黄金会员",
        "status": "DELIVERED",
        "statusText": "已签收",
        "statusCode": 4,  # 1:待付款, 2:待发货, 3:运输中, 4:已签收, 5:售后中, 6:已退款
        "createTime": "2026-03-22 14:20:10",
        "payTime": "2026-03-22 14:21:05",
        "shipTime": "2026-03-23 09:30:00",
        "deliveryTime": "2026-03-25 11:24:36",
        "items": [
            {
                "skuId": "SKU-ROBOT-001",
                "title": "XX智能全自动扫地机器人 Pro (双向避障激光导航版)",
                "category": "生活电器",
                "spec": "曜石黑 / 双盘旋转擦地 / 自动集尘基站",
                "price": 2999.00,
                "quantity": 1,
                "imageUrl": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=160&q=80",
                "isSpecialProduct": False,
                "isCustomized": False
            }
        ],
        "totalAmount": 2999.00,
        "paidAmount": 2999.00,
        "shippingFee": 0.00,
        "express": {
            "company": "顺丰速运",
            "companyCode": "SF",
            "trackingNumber": "SF1882049281",
            "status": "DELIVERED",
            "statusDescription": "买家已在菜鸟驿站/自提柜签收",
            "timeline": [
                {
                    "time": "2026-03-25 11:24:36",
                    "status": "已签收",
                    "context": "【已签收】您的快件已由本人在 [北京市朝阳区亮马桥路XX花园菜鸟驿站] 签收，感谢使用顺丰速运！如有疑问请联系派送员。"
                },
                {
                    "time": "2026-03-25 08:15:20",
                    "status": "派送中",
                    "context": "【派送中】顺丰速运 派件员 张师傅 (电话: 13900112233) 正在为您派送，请保持电话畅通。"
                },
                {
                    "time": "2026-03-24 23:40:11",
                    "status": "运输中",
                    "context": "【运输中】快件已到达 [北京市朝阳区分拨中心]，正准备发往亮马桥营业点。"
                },
                {
                    "time": "2026-03-23 18:20:00",
                    "status": "运输中",
                    "context": "【运输中】快件已离开 [上海松江转运中心]，正发往 [北京分拨中心]。"
                },
                {
                    "time": "2026-03-23 09:30:00",
                    "status": "已揽收",
                    "context": "【已揽收】顺丰速运 华东智慧物流园区 已收件，揽收员: 李师傅。"
                }
            ]
        },
        "receiver": {
            "name": "王女士",
            "phone": "138****6699",
            "address": "北京市朝阳区亮马桥路88号XX花园3号楼1202室"
        },
        "afterSales": {
            "canReturn7Days": True,
            "returnDaysRemaining": 4,  # 签收第3天，还剩4天
            "signedDays": 3,
            "returnPolicy": "支持7天无理由退货（商品完好、配件齐全、未影响二次销售）",
            "shippingSubsidy": "黄金会员享有平台免运费退货补贴",
            "warrantyStatus": "生效中",
            "warrantyExpiredDate": "2027-03-25",
            "warrantyPolicy": "1年全国联保，15天内非人为故障可免费换新机"
        }
    },
    {
        "orderId": "ORD-2026-90412",
        "orderSn": "202603279041202",
        "userId": "user_002",
        "userName": "张先生",
        "userPhone": "139****1122",
        "vipLevel": "普通会员",
        "status": "IN_TRANSIT",
        "statusText": "运输中",
        "statusCode": 3,
        "createTime": "2026-03-26 10:15:00",
        "payTime": "2026-03-26 10:16:30",
        "shipTime": "2026-03-27 08:45:00",
        "deliveryTime": None,
        "items": [
            {
                "skuId": "SKU-TEA-002",
                "title": "纯手工定制刻字紫砂壶 (大师编号收藏版)",
                "category": "工艺礼品",
                "spec": "底款刻字：『宁静致远』 / 280ml 原矿紫泥",
                "price": 880.00,
                "quantity": 1,
                "imageUrl": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=160&q=80",
                "isSpecialProduct": True,
                "isCustomized": True
            }
        ],
        "totalAmount": 880.00,
        "paidAmount": 880.00,
        "shippingFee": 0.00,
        "express": {
            "company": "京东快递",
            "companyCode": "JD",
            "trackingNumber": "JD0092817263",
            "status": "IN_TRANSIT",
            "statusDescription": "快件正在高速运输中，预计次日送达",
            "timeline": [
                {
                    "time": "2026-03-27 16:30:00",
                    "status": "运输中",
                    "context": "【运输中】快件已到达 [杭州萧山智慧转运中心]，正在分拣出库，发往西湖区文三路营业部。"
                },
                {
                    "time": "2026-03-27 11:20:00",
                    "status": "运输中",
                    "context": "【运输中】快件已离开 [江苏宜兴陶艺集散中心]，正发往 [杭州萧山转运中心]。"
                },
                {
                    "time": "2026-03-27 08:45:00",
                    "status": "已揽收",
                    "context": "【已揽收】京东快递 已在江苏宜兴营业部揽收完成。"
                }
            ]
        },
        "receiver": {
            "name": "张先生",
            "phone": "139****1122",
            "address": "浙江省杭州市西湖区文三路398号创新大厦A座8楼"
        },
        "afterSales": {
            "canReturn7Days": False,
            "returnDaysRemaining": 0,
            "signedDays": 0,
            "returnPolicy": "此商品为个人定制专属刻字工艺品，根据XX商城2026政策第2条，非质量问题不支持7天无理由退货",
            "shippingSubsidy": "普通会员个人退货需自行承担运费",
            "warrantyStatus": "破损包赔",
            "warrantyExpiredDate": "2026-04-26",
            "warrantyPolicy": "若签收时发现运输碎裂破损，支持极速拍照补发或全额先行赔付"
        }
    },
    {
        "orderId": "ORD-2026-77310",
        "orderSn": "202603207731003",
        "userId": "user_003",
        "userName": "刘总",
        "userPhone": "186****9988",
        "vipLevel": "钻石会员",
        "status": "RETURNING_INSPECTION",
        "statusText": "售后质检中",
        "statusCode": 5,
        "createTime": "2026-03-18 16:00:00",
        "payTime": "2026-03-18 16:02:15",
        "shipTime": "2026-03-19 09:00:00",
        "deliveryTime": "2026-03-20 15:30:00",
        "items": [
            {
                "skuId": "SKU-PROJ-003",
                "title": "4K超高清投影仪旗舰款 (智能画框幕布套装)",
                "category": "影音娱乐",
                "spec": "激光高亮3000流明 + 100寸抗光幕布",
                "price": 5999.00,
                "quantity": 2,
                "imageUrl": "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=160&q=80",
                "isSpecialProduct": False,
                "isCustomized": False
            }
        ],
        "totalAmount": 11998.00,
        "paidAmount": 11998.00,
        "shippingFee": 0.00,
        "express": {
            "company": "顺丰速运 (退货回寄单)",
            "companyCode": "SF",
            "trackingNumber": "SF9928371928",
            "status": "WAREHOUSE_RECEIVED",
            "statusDescription": "售后仓库已签收退件，工程师正在48小时质检",
            "timeline": [
                {
                    "time": "2026-03-24 09:30:00",
                    "status": "仓库签收",
                    "context": "【仓库质检】退回商品已送达 [XX商城华北售后中心]，质检专员正在核验机器外观与配件完整性。"
                },
                {
                    "time": "2026-03-23 14:10:00",
                    "status": "运输中",
                    "context": "【运输中】快件正发往 [XX商城华北中央售后退换中心]。"
                },
                {
                    "time": "2026-03-22 10:00:00",
                    "status": "寄件发出",
                    "context": "【寄件发出】客户刘总已通过顺丰上门取件寄出退货商品。"
                }
            ]
        },
        "receiver": {
            "name": "刘总",
            "phone": "186****9988",
            "address": "上海市浦东新区陆家嘴环路1000号恒生银行大厦28楼"
        },
        "afterSales": {
            "canReturn7Days": True,
            "returnDaysRemaining": 0,
            "signedDays": 4,
            "returnPolicy": "已进入退款流程：48小时内完成质检入库，质检合格后原路退款至原支付银行卡（1-3工作日）",
            "shippingSubsidy": "钻石会员尊享专属顺丰免费上门取件与全额运费代付",
            "warrantyStatus": "退货质检中",
            "warrantyExpiredDate": "-",
            "warrantyPolicy": "质检合格后将全额冲正退款 ¥11,998.00"
        }
    },
    {
        "orderId": "ORD-2026-66521",
        "orderSn": "202602156652104",
        "userId": "user_001",
        "userName": "王女士",
        "userPhone": "138****6699",
        "vipLevel": "黄金会员",
        "status": "COMPLETED",
        "statusText": "已完成",
        "statusCode": 6,
        "createTime": "2026-02-15 11:00:00",
        "payTime": "2026-02-15 11:01:20",
        "shipTime": "2026-02-15 16:30:00",
        "deliveryTime": "2026-02-17 14:20:00",
        "items": [
            {
                "skuId": "SKU-EAR-004",
                "title": "无线主动降噪蓝牙耳机 Pro (白色)",
                "category": "数码配件",
                "spec": "皓月白 / 空间音频 / 48小时长续航",
                "price": 499.00,
                "quantity": 1,
                "imageUrl": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=160&q=80",
                "isSpecialProduct": False,
                "isCustomized": False
            }
        ],
        "totalAmount": 499.00,
        "paidAmount": 499.00,
        "shippingFee": 0.00,
        "express": {
            "company": "中通快递",
            "companyCode": "ZTO",
            "trackingNumber": "ZTO7788192031",
            "status": "DELIVERED",
            "statusDescription": "买家已于2月17日签收",
            "timeline": [
                {
                    "time": "2026-02-17 14:20:00",
                    "status": "已签收",
                    "context": "【已签收】已签收，签收人: 本人。"
                }
            ]
        },
        "receiver": {
            "name": "王女士",
            "phone": "138****6699",
            "address": "北京市朝阳区亮马桥路88号XX花园3号楼1202室"
        },
        "afterSales": {
            "canReturn7Days": False,
            "returnDaysRemaining": 0,
            "signedDays": 38,
            "returnPolicy": "已超过签收7天期限，不再支持无理由退货",
            "shippingSubsidy": "保修期内非人为故障维修享受双向包邮",
            "warrantyStatus": "联保生效中",
            "warrantyExpiredDate": "2027-02-17",
            "warrantyPolicy": "享有1年全国联保，若出现功能性故障可申请免费官方售后维修"
        }
    }
]


class OrderService:
    def __init__(self):
        self.orders: Dict[str, Dict[str, Any]] = {o["orderId"]: o for o in MOCK_ORDERS}

    def list_orders(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """按用户、状态或关键词筛选订单列表"""
        res = list(self.orders.values())
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
        """获取单个订单完整详情"""
        clean_id = order_id.strip().upper()
        if clean_id in self.orders:
            return self.orders[clean_id]
        
        # 模糊匹配 (例如传入 88992 或 ORD88992)
        for oid, order in self.orders.items():
            if clean_id in oid or oid.replace("-", "") == clean_id.replace("-", ""):
                return order
        return None

    def find_orders_for_user(self, user_name: str, phone: Optional[str] = None) -> List[Dict[str, Any]]:
        """根据客户姓名或手机号拉取该客户的所有订单"""
        matched = []
        for o in self.orders.values():
            if user_name and user_name in o["userName"]:
                matched.append(o)
            elif phone and phone in o.get("userPhone", ""):
                matched.append(o)
        return matched

    def detect_and_query_order(
        self,
        message: str,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        核心智能识别：从用户自然语言输入或会话画像中推断并定位目标订单
        例如：
        - "查订单 ORD-2026-88992" -> 精准命中 ORD-2026-88992
        - "我的扫地机器人到哪了" -> 根据商品关键词 "扫地机器人" 匹配订单
        - "查一下我的订单" -> 结合当前用户画像绑定的 orderId 或拉取其最新一笔订单
        """
        msg = message.strip()
        user_profile = user_profile or {}

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
        for oid in self.orders.keys():
            if oid.lower() in msg.lower() or oid.replace("-", "").lower() in msg.lower():
                return self.orders[oid]

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
                return self.orders.get(mapped_id)

        # 4. 如果用户询问通用订单/物流关键词 ("我的订单", "发货了吗", "物流到哪了", "什么时候到")
        order_intent_keywords = ["订单", "物流", "发货", "运单", "快递", "到哪了", "什么时候到", "送达", "签收"]
        if any(k in msg for k in order_intent_keywords):
            # 优先使用会话画像中预绑定的 orderId
            bound_order_id = user_profile.get("orderId")
            if bound_order_id and bound_order_id in self.orders:
                return self.orders[bound_order_id]

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
