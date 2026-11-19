"""
PostgreSQL 初始业务种子数据定义 (Initial Seed Data)
用于首次启动空库时幂等写入演示客户画像、人工坐席、订单与初始会话记录。
"""

import json
from typing import Dict, Any, List


def build_seed_customers(now: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "user_001",
            "name": "王女士",
            "phone": "138****6699",
            "vip_level": "黄金会员",
            "sentiment": "frustrated",
            "urgency": "高",
            "intent": "7天无理由退货运费与到账时间",
            "tags_json": json.dumps(["黄金会员", "免运费特权", "急躁", "签收第3天"], ensure_ascii=False),
            "order_id": "ORD-2026-88992",
            "avatar": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=120&q=80",
            "registered_date": "2023-08-15",
            "total_orders_count": 18,
            "total_spent": 14580.0,
            "shipping_address": "北京市朝阳区亮马桥路88号XX花园3号楼1202室",
            "updated_at": now,
        },
        {
            "id": "user_002",
            "name": "张先生",
            "phone": "139****1122",
            "vip_level": "普通会员",
            "sentiment": "neutral",
            "urgency": "中",
            "intent": "个人定制刻字紫砂壶退货咨询",
            "tags_json": json.dumps(["普通会员", "定制工艺品", "运输中"], ensure_ascii=False),
            "order_id": "ORD-2026-90412",
            "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80",
            "registered_date": "2024-01-20",
            "total_orders_count": 3,
            "total_spent": 1260.0,
            "shipping_address": "浙江省杭州市西湖区文三路398号创新大厦A座8楼",
            "updated_at": now,
        },
        {
            "id": "user_003",
            "name": "刘总",
            "phone": "186****9988",
            "vip_level": "钻石会员",
            "sentiment": "positive",
            "urgency": "低",
            "intent": "极速退款到账时效确认",
            "tags_json": json.dumps(["钻石会员", "大额客户", "已寄回质检"], ensure_ascii=False),
            "order_id": "ORD-2026-77310",
            "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
            "registered_date": "2022-04-10",
            "total_orders_count": 52,
            "total_spent": 98600.0,
            "shipping_address": "上海市浦东新区陆家嘴环路1000号恒生银行大厦28楼",
            "updated_at": now,
        },
    ]


def build_seed_agents(now: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "agent_101",
            "name": "陈浩",
            "title": "高级售后督导",
            "department": "XX商城 客户关怀中心",
            "status": "IDLE",
            "current_workload": 1,
            "max_workload": 5,
            "rating": 4.98,
            "specialties_json": json.dumps(["7天无理由退货", "黄金会员运费补贴", "客诉安抚"], ensure_ascii=False),
            "recommended_for_json": json.dumps(["退运费", "到账时间", "情绪安抚", "会员特权"], ensure_ascii=False),
            "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80",
            "phone": "分机 8011",
            "email": "chenhao@xx-mall.com",
            "updated_at": now,
        },
        {
            "id": "agent_102",
            "name": "林雅",
            "title": "退换货与物流主管",
            "department": "售后争议调解组",
            "status": "IDLE",
            "current_workload": 0,
            "max_workload": 5,
            "rating": 4.95,
            "specialties_json": json.dumps(["特殊商品退货政策", "定制品纠纷", "物流丢件理赔"], ensure_ascii=False),
            "recommended_for_json": json.dumps(["定制商品", "刻字不退", "物流延误", "顺丰拦截"], ensure_ascii=False),
            "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=120&q=80",
            "phone": "分机 8012",
            "email": "linya@xx-mall.com",
            "updated_at": now,
        },
        {
            "id": "agent_103",
            "name": "张建国",
            "title": "资深技术支持专员",
            "department": "智能硬件售后组",
            "status": "IDLE",
            "current_workload": 0,
            "max_workload": 4,
            "rating": 4.91,
            "specialties_json": json.dumps(["扫地机器人故障", "激光雷达标定", "固件OTA升级"], ensure_ascii=False),
            "recommended_for_json": json.dumps(["机器异响", "无法充电", "质量检测"], ensure_ascii=False),
            "avatar": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=120&q=80",
            "phone": "分机 8015",
            "email": "zhangjg@xx-mall.com",
            "updated_at": now,
        },
        {
            "id": "agent_104",
            "name": "李晓静",
            "title": "VIP专属客户管家",
            "department": "钻石会员专属服务组",
            "status": "IDLE",
            "current_workload": 0,
            "max_workload": 3,
            "rating": 4.99,
            "specialties_json": json.dumps(["大客户极速冲正", "专属绿色通道", "高管关怀"], ensure_ascii=False),
            "recommended_for_json": json.dumps(["钻石会员", "极速退款", "大额退换"], ensure_ascii=False),
            "avatar": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=120&q=80",
            "phone": "专线 8000",
            "email": "lixiaojing@xx-mall.com",
            "updated_at": now,
        },
    ]


def build_seed_orders(now: str) -> List[Dict[str, Any]]:
    o1_items = [{
        "skuId": "SKU-ROBOT-001",
        "title": "XX智能全自动扫地机器人 Pro (双向避障激光导航版)",
        "category": "生活电器",
        "spec": "曜石黑 / 双盘旋转擦地 / 自动集尘基站",
        "price": 2999.0,
        "quantity": 1,
        "imageUrl": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=160&q=80",
        "isSpecialProduct": False,
        "isCustomized": False,
    }]
    o1_express = {
        "company": "顺丰速运",
        "companyCode": "SF",
        "trackingNumber": "SF1882049281",
        "status": "DELIVERED",
        "statusDescription": "买家已在菜鸟驿站/自提柜签收",
        "timeline": [
            {"time": "2026-03-25 11:24:36", "status": "已签收", "context": "【已签收】您的快件已由本人在 [北京市朝阳区亮马桥路XX花园菜鸟驿站] 签收。"},
            {"time": "2026-03-25 08:15:20", "status": "派送中", "context": "【派送中】顺丰速运 派件员 张师傅正在派送。"},
        ],
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
        "warrantyPolicy": "1年全国联保，15天内非人为故障可免费换新机",
    }

    o2_items = [{
        "skuId": "SKU-TEA-002",
        "title": "纯手工定制刻字紫砂壶 (大师编号收藏版)",
        "category": "工艺礼品",
        "spec": "底款刻字：『宁静致远』 / 280ml 原矿紫泥",
        "price": 880.0,
        "quantity": 1,
        "imageUrl": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=160&q=80",
        "isSpecialProduct": True,
        "isCustomized": True,
    }]
    o2_express = {
        "company": "京东快递",
        "companyCode": "JD",
        "trackingNumber": "JD0092817263",
        "status": "IN_TRANSIT",
        "statusDescription": "快件正在高速运输中，预计次日送达",
        "timeline": [{"time": "2026-03-27 16:30:00", "status": "运输中", "context": "【运输中】快件已到达杭州萧山转运中心。"}],
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
        "warrantyPolicy": "若签收时发现运输碎裂破损，支持极速拍照补发或先行赔付",
    }

    o3_items = [{
        "skuId": "SKU-CABLE-005",
        "title": "便携多功能柔性理线器/清洁湿巾 (3包装)",
        "category": "数码配件",
        "spec": "黑色 3包装 / 简易收纳",
        "price": 2.50,
        "quantity": 1,
        "imageUrl": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=160&q=80",
        "isSpecialProduct": False,
        "isCustomized": False,
    }]
    o3_express = {
        "company": "中通快递",
        "companyCode": "ZTO",
        "trackingNumber": "ZT771029381",
        "status": "DELIVERED",
        "statusDescription": "买家已于菜鸟驿站完成签收",
        "timeline": [{"time": "2026-03-28 09:30:00", "status": "已签收", "context": "【已签收】您的快件已在自提柜完成签收。"}],
    }
    o3_receiver = {"name": "王女士", "phone": "138****6699", "address": "北京市朝阳区亮马桥路88号XX花园3号楼1202室"}
    o3_after_sales = {
        "canReturn7Days": True,
        "returnDaysRemaining": 6,
        "signedDays": 1,
        "returnPolicy": "支持7天无理由退货（商品未拆封）",
        "shippingSubsidy": "黄金会员享极速小额免审核退款特权",
        "warrantyStatus": "生效中",
        "warrantyExpiredDate": "2026-04-28",
        "warrantyPolicy": "质量问题直接换新",
        "refundStatus": "NONE",
        "refundAmount": 0.0,
        "refundReason": "",
        "requiresHumanAudit": False,
    }

    return [
        {
            "order_id": "ORD-2026-88992",
            "order_sn": "202603258899201",
            "user_id": "user_001",
            "user_name": "王女士",
            "user_phone": "138****6699",
            "vip_level": "黄金会员",
            "status": "DELIVERED",
            "status_text": "已签收",
            "status_code": 4,
            "create_time": "2026-03-22 14:20:10",
            "pay_time": "2026-03-22 14:21:05",
            "ship_time": "2026-03-23 09:30:00",
            "delivery_time": "2026-03-25 11:24:36",
            "items_json": json.dumps(o1_items, ensure_ascii=False),
            "total_amount": 2999.0,
            "paid_amount": 2999.0,
            "shipping_fee": 0.0,
            "express_json": json.dumps(o1_express, ensure_ascii=False),
            "receiver_json": json.dumps(o1_receiver, ensure_ascii=False),
            "after_sales_json": json.dumps(o1_after_sales, ensure_ascii=False),
            "updated_at": now,
        },
        {
            "order_id": "ORD-2026-90412",
            "order_sn": "202603279041202",
            "user_id": "user_002",
            "user_name": "张先生",
            "user_phone": "139****1122",
            "vip_level": "普通会员",
            "status": "IN_TRANSIT",
            "status_text": "运输中",
            "status_code": 3,
            "create_time": "2026-03-26 10:15:00",
            "pay_time": "2026-03-26 10:16:30",
            "ship_time": "2026-03-27 08:45:00",
            "delivery_time": None,
            "items_json": json.dumps(o2_items, ensure_ascii=False),
            "total_amount": 880.0,
            "paid_amount": 880.0,
            "shipping_fee": 0.0,
            "express_json": json.dumps(o2_express, ensure_ascii=False),
            "receiver_json": json.dumps(o2_receiver, ensure_ascii=False),
            "after_sales_json": json.dumps(o2_after_sales, ensure_ascii=False),
            "updated_at": now,
        },
        {
            "order_id": "ORD-2026-00100",
            "order_sn": "202603280010003",
            "user_id": "user_001",
            "user_name": "王女士",
            "user_phone": "138****6699",
            "vip_level": "黄金会员",
            "status": "DELIVERED",
            "status_text": "已签收",
            "status_code": 4,
            "create_time": "2026-03-27 10:00:00",
            "pay_time": "2026-03-27 10:00:15",
            "ship_time": "2026-03-27 14:00:00",
            "delivery_time": "2026-03-28 09:30:00",
            "items_json": json.dumps(o3_items, ensure_ascii=False),
            "total_amount": 2.50,
            "paid_amount": 2.50,
            "shipping_fee": 0.0,
            "express_json": json.dumps(o3_express, ensure_ascii=False),
            "receiver_json": json.dumps(o3_receiver, ensure_ascii=False),
            "after_sales_json": json.dumps(o3_after_sales, ensure_ascii=False),
            "updated_at": now,
        },
    ]


def build_seed_sessions(now: str) -> List[Dict[str, Any]]:
    s1_profile = {
        "name": "王女士",
        "phone": "138****6699",
        "vipLevel": "黄金会员",
        "sentiment": "frustrated",
        "urgency": "高",
        "intent": "7天无理由退货运费与到账时间",
        "tags": ["黄金会员", "免运费特权", "急躁", "签收第3天"],
        "orderId": "ORD-2026-88992",
    }
    s1_msgs = [
        {"id": "m1", "role": "user", "content": "我3天前买的扫地机器人，包装完好没拆过封，想退货的话运费谁承担？", "timestamp": "10:14:20"},
        {
            "id": "m2",
            "role": "assistant",
            "content": "王女士您好！根据XX商城政策：签收7天内商品完好支持7天无理由退换。虽然个人原因退换通常由买家承担运费，但检测到您是【黄金会员】，享有平台全额补贴的『退货免运费』专属权益，您无需承担任何寄回运费！",
            "confidenceScore": 0.96,
            "timestamp": "10:14:24",
        },
        {"id": "m3", "role": "user", "content": "那我退回去之后，钱大概几天能退回我的支付宝？", "timestamp": "10:15:02"},
    ]
    return [
        {
            "id": "session_user_001",
            "user_name": "王女士",
            "status": "AI_HANDLING",
            "assigned_agent": None,
            "assigned_agent_id": None,
            "customer_profile_json": json.dumps(s1_profile, ensure_ascii=False),
            "summary_memory": "客户王女士（黄金会员，订单 ORD-2026-88992）签收扫地机器人3天，因尺寸不合适想申请7天无理由退货，咨询退货运费是否需要自己出以及退款多久到账。系统已确认黄金会员享免运费补贴。",
            "messages_json": json.dumps(s1_msgs, ensure_ascii=False),
            "metrics_json": json.dumps({"totalTurns": 3, "avgLatencyMs": 320, "avgConfidence": 0.96, "escalatedAt": None}, ensure_ascii=False),
            "context_snapshot_json": None,
            "latest_transfer_json": None,
            "unread_for_agent": 0,
            "created_at": now,
            "updated_at": now,
        }
    ]
