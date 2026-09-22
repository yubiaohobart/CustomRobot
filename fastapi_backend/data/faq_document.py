"""
公司专属售后政策知识库文档 (FAQ Document)
严格录入 XX商城售后服务与退换货政策（2026版）并提供结构化切片与解析器
"""

import re
from typing import List, Dict, Any

FAQ_MARKDOWN_DOC = """
# XX商城售后服务与退换货政策（2026版）

## 1. 7天无理由退货政策
- 支持范围：用户在签收商品之日起 7 天内（含 7 天），在商品完好、不影响二次销售的前提下，均可申请“7天无理由退换货”。
- 运费规则：
  - 因商品质量问题（如破损、错发、功能故障）导致的退换货，来回运费由本公司全额承担。
  - 因客户个人原因（如不喜欢、拍错、七天无理由）发起的退换货，寄回运费需由买家自行承担。
  - 黄金会员及以上等级用户，享有“退货免运费”专属权益，退货运费由平台补贴。

## 2. 不支持7天无理由退换的特殊商品
以下商品一经售出，非质量问题不予退换：
1. 个人定制类商品（如刻字、按需定制尺寸的工艺品）；
2. 鲜活易腐类商品（如生鲜水果、鲜花）；
3. 在线下载或者拆封的数字化商品（如软件激活码、充值卡）；
4. 交付后拆封即影响人身安全或者生命健康的贴身衣物（如内裤、泳裤）、母婴用品。

## 3. 退款到账时间
- 仓库在收到退回商品并在 48 小时内完成质检入库；
- 质检合格后，系统自动原路发起退款：
  - 微信/支付宝零钱：即时到账；
  - 借记卡：1~3 个工作日到账；
  - 信用卡：3~5 个工作日到账。

## 4. 维修与保修条款
- 全系电子产品享有 1 年全国联保服务。
- 超过 7 天但在 15 天内发生非人为损坏的硬件故障，可申请“免费换新机”。
- 保修期内因人为摔落、进水、私自拆修导致的损坏，不属于免费保修范围，需收取配件成本费。
""".strip()

def parse_faq_markdown(doc_text: str = FAQ_MARKDOWN_DOC) -> List[Dict[str, Any]]:
    """
    将 FAQ Markdown 文档按照二级标题 `##` 进行层级解析和结构化切片
    提取标题、内容、分类、检索标签和关键词，供 Qdrant 向量库持久化
    """
    chunks: List[Dict[str, Any]] = []
    
    # 获取主标题
    main_title_match = re.search(r"^#\s+(.+)$", doc_text, re.MULTILINE)
    main_title = main_title_match.group(1).strip() if main_title_match else "售后服务与退换货政策"

    # 按二级标题切分
    sections = re.split(r"(?m)^##\s+", doc_text)
    
    for i, section in enumerate(sections):
        section = section.strip()
        if not section or section.startswith("# "):
            continue
            
        lines = section.split("\n", 1)
        section_title = lines[0].strip()
        section_content = lines[1].strip() if len(lines) > 1 else ""
        
        # 归类与标签提取
        category = "售后政策"
        tags = ["XX商城", "2026新规"]
        keywords: List[str] = []

        if "7天无理由" in section_title:
            category = "售后政策"
            tags.extend(["无理由退货", "运费规则", "黄金会员免运费", "退货范围"])
            keywords = ["退货", "退款", "7天", "七天", "无理由", "运费", "运费险", "质量问题", "黄金会员", "个人原因", "二次销售"]
        elif "特殊商品" in section_title or "不支持" in section_title:
            category = "特殊规则"
            tags.extend(["不支持退换", "特殊商品", "生鲜", "定制", "虚拟商品", "贴身衣物", "母婴"])
            keywords = ["定制", "生鲜", "水果", "鲜花", "数字化", "激活码", "充值卡", "贴身", "内裤", "母婴", "不可退"]
        elif "退款到账" in section_title or "时间" in section_title:
            category = "账务与退款"
            tags.extend(["退款到账", "质检入库", "原路退回", "微信到账", "银行卡"])
            keywords = ["退款", "到账", "48小时", "质检", "微信", "支付宝", "借记卡", "信用卡", "多久到账", "工作日"]
        elif "维修" in section_title or "保修" in section_title:
            category = "维修保修"
            tags.extend(["保修条款", "全国联保", "15天换新", "进水保修", "人为损坏"])
            keywords = ["保修", "维修", "全国联保", "1年", "一年", "换新", "15天", "人为损坏", "进水", "摔落", "配件费"]

        doc_id = f"faq_chunk_{i}"
        
        chunks.append({
            "id": doc_id,
            "title": section_title,
            "main_title": main_title,
            "category": category,
            "content": f"【{main_title} - {section_title}】\n{section_content}",
            "raw_content": section_content,
            "tags": tags,
            "keywords": keywords,
            "updatedAt": "2026-01-15T09:00:00Z"
        })
        
    return chunks

def get_default_faq_chunks() -> List[Dict[str, Any]]:
    """获取预设切片列表"""
    return parse_faq_markdown(FAQ_MARKDOWN_DOC)
