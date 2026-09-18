"""
企业知识库向量存储与相似度检索 (Vector Store & Semantic Search)
"""

import math
from typing import List, Dict, Any, Tuple

DEFAULT_KNOWLEDGE_DOCS = [
    {
        "id": "doc_return_policy",
        "title": "售后退换货服务细则与7天无理由政策",
        "category": "售后服务",
        "keywords": ["退货", "退款", "7天无理由", "换货", "运费险", "折旧", "钻石VIP"],
        "content": "自商品签收之日起7日内，商品完好且配件齐全的，支持7天无理由退货。针对钻石VIP会员，提供特批极速退款通道与顺丰上门免费取件；退款在顺丰揽收录入后2小时内原路退回至原支付渠道。"
    },
    {
        "id": "doc_invoice_spec",
        "title": "企业增值税专用发票与电子发票开具规范",
        "category": "财务结算",
        "keywords": ["发票", "专票", "增值税", "税号", "开户行", "电子普票", "纸质"],
        "content": "如需开具企业增值税专用发票，请在下单时或签收后30天内，在订单中心提供统一社会信用代码、开户行名称、账号及开票地址电话。发票开具后将通过顺丰特快免费寄送，通常3个工作日内送达。"
    },
    {
        "id": "doc_shipping_standards",
        "title": "仓储配送标准、顺丰时效与运费规则",
        "category": "物流仓储",
        "keywords": ["物流", "顺丰", "时效", "运费", "次日达", "发货", "冷链"],
        "content": "全场订单实付金额满99元即可享受全国顺丰包邮服务。每日16:00前支付成功的订单确保当日出库，华东、华南主要省会城市支持次日达。偏远地区（新疆、西藏等）预计3-5日送达。"
    },
    {
        "id": "doc_vip_privileges",
        "title": "高净值会员体系等级权益与特权",
        "category": "会员权益",
        "keywords": ["VIP", "会员", "积分", "白金", "钻石", "优先介入", "折扣"],
        "content": "平台会员分为普通会员、黄金会员、白金会员与钻石VIP。钻石VIP专享：专属1对1客服经理24小时在线、售后极速免检垫付、生日专属定制礼品，以及大额订单极速发货特权。"
    },
    {
        "id": "doc_dispute_resolution",
        "title": "疑难客诉争议先行赔付与快速仲裁准则",
        "category": "风控仲裁",
        "keywords": ["投诉", "争议", "仲裁", "赔付", "破损", "少件", "人工"],
        "content": "遇商品破损、物流超期或严重质量问题，客户提供签收拍照凭证后，客服值班主管有权启动最高500元的『先行赔付』流程，款项15分钟内到账，随后由平台专职追溯物流承运商责任。"
    }
]

class VectorKnowledgeStore:
    def __init__(self):
        self.documents = DEFAULT_KNOWLEDGE_DOCS

    def similarity_search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """计算查询语句与知识文档的余弦/关键词匹配相似度并排序"""
        scored_results = []
        q_lower = query.lower()

        for doc in self.documents:
            score = 0.35 # 基础底分
            
            # 关键词强匹配
            for kw in doc["keywords"]:
                if kw.lower() in q_lower:
                    score += 0.28
                    
            # 标题与正文重叠匹配
            for word in ["退款", "退货", "发票", "专票", "物流", "顺丰", "会员", "vip", "赔偿", "投诉"]:
                if word in q_lower and (word in doc["title"].lower() or word in doc["content"].lower()):
                    score += 0.15
                    
            score = min(0.98, max(0.40, score))
            scored_results.append({
                "doc": doc,
                "score": round(score, 3)
            })

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:k]
