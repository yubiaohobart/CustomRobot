"""
公司专属售后政策知识库文档 (FAQ Document)
严格录入 XX商城售后服务与退换货政策（2026版）并提供结构化切片与解析器
"""

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import uuid
from typing import List, Dict, Any, Tuple

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


def _compute_chunk_hash(chunk: Dict[str, Any]) -> str:
    """对影响检索向量与展示的核心字段计算 SHA-256，用于 Qdrant 增量同步判定"""
    canonical = json.dumps(
        {
            "title": chunk["title"],
            "category": chunk["category"],
            "content": chunk["content"],
            "tags": chunk["tags"],
            "keywords": chunk["keywords"],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_faq_markdown(doc_text: str = FAQ_MARKDOWN_DOC) -> List[Dict[str, Any]]:
    """
    将 FAQ Markdown 文档按照二级标题 `##` 进行层级解析和结构化切片
    提取稳定 UUID 主键、内容哈希、标题、分类、检索标签和关键词，供 Qdrant 增量同步
    """
    chunks: List[Dict[str, Any]] = []

    main_title_match = re.search(r"^#\s+(.+)$", doc_text, re.MULTILINE)
    main_title = main_title_match.group(1).strip() if main_title_match else "售后服务与退换货政策"

    sections = re.split(r"(?m)^##\s+", doc_text)

    for section in sections:
        section = section.strip()
        if not section or section.startswith("# "):
            continue

        lines = section.split("\n", 1)
        section_title = lines[0].strip()
        section_content = lines[1].strip() if len(lines) > 1 else ""

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

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"intelliserve:faq:{main_title}:{section_title}"))
        chunk: Dict[str, Any] = {
            "id": doc_id,
            "title": section_title,
            "category": category,
            "content": f"【{main_title} - {section_title}】\n{section_content}",
            "tags": tags,
            "keywords": keywords,
            "source": "builtin_faq",
            "updatedAt": "2026-01-15T09:00:00Z",
        }
        chunk["content_hash"] = _compute_chunk_hash(chunk)
        chunks.append(chunk)

    return chunks


_CHUNK_MAX_CHARS = 500
_CHUNK_OVERLAP_CHARS = 80


def _split_body_with_overlap(text: str, max_chars: int = _CHUNK_MAX_CHARS, overlap: int = _CHUNK_OVERLAP_CHARS) -> List[str]:
    """按段落优先切分超长章节，单段超限时按滑动窗口切分并保留上下文重叠"""
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]
    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    def _flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append("\n".join(buf))
            buf = []
            buf_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            _flush()
            step = max(1, max_chars - overlap)
            for start in range(0, len(para), step):
                part = para[start : start + max_chars].strip()
                if part:
                    chunks.append(part)
                if start + max_chars >= len(para):
                    break
            continue

        added = len(para) + (1 if buf else 0)
        if buf and buf_len + added > max_chars:
            prev_text = "\n".join(buf)
            _flush()
            tail = prev_text[-overlap:].strip() if overlap > 0 and len(prev_text) > overlap else ""
            if tail and len(tail) + 1 + len(para) <= max_chars:
                buf = [tail, para]
                buf_len = len(tail) + 1 + len(para)
                continue

        buf.append(para)
        buf_len += added

    _flush()
    return chunks


def _format_docx_table(table: Any) -> str:
    """将 Word 表格按行展开为语义文本，兼容合并单元格"""
    rows_text: List[str] = []
    headers: List[str] = []

    for r_idx, row in enumerate(table.rows):
        cells: List[str] = []
        seen_tc = set()
        for cell in row.cells:
            tc_id = id(cell._tc)
            if tc_id in seen_tc:
                continue
            seen_tc.add(tc_id)
            cells.append(" ".join(cell.text.split()))

        if not any(cells):
            continue
        if r_idx == 0 and len(table.rows) > 1:
            headers = cells
            continue

        if headers and len(headers) == len(cells):
            pairs = [f"{h}: {c}" if h else c for h, c in zip(headers, cells) if c]
            if pairs:
                rows_text.append(" | ".join(pairs))
        else:
            non_empty = [c for c in cells if c]
            if non_empty:
                rows_text.append(" | ".join(non_empty))

    if not rows_text and headers:
        non_empty = [h for h in headers if h]
        if non_empty:
            rows_text.append(" | ".join(non_empty))
    return "\n".join(rows_text)


def parse_docx_bytes(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    解析上传的 .docx 企业文档字节流：
    按阅读顺序提取段落与表格，依 Heading 标题及滑动窗口切片，返回可直接写入 Qdrant 的结构化分块
    """
    from docx import Document
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(file_bytes))
    doc_stem = Path(filename).stem.strip() or "企业文档"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sections: List[Tuple[str, List[str]]] = []
    current_title = doc_stem
    current_blocks: List[str] = []

    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style_name = (para.style.name if para.style else "") or ""
            lower_style = style_name.lower()
            is_heading = (
                lower_style.startswith("heading")
                or lower_style == "title"
                or "标题" in style_name
            )
            if is_heading:
                if current_blocks:
                    sections.append((current_title, current_blocks))
                current_title = text[:80]
                current_blocks = []
            else:
                current_blocks.append(text)
        elif isinstance(child, CT_Tbl):
            table_text = _format_docx_table(Table(child, doc))
            if table_text:
                current_blocks.append(table_text)

    if current_blocks:
        sections.append((current_title, current_blocks))

    chunks: List[Dict[str, Any]] = []
    chunk_seq = 0
    for sec_title, blocks in sections:
        parts = _split_body_with_overlap("\n".join(blocks))
        total_parts = len(parts)
        for part_idx, body in enumerate(parts, start=1):
            chunk_seq += 1
            display_title = sec_title if total_parts == 1 else f"{sec_title} ({part_idx}/{total_parts})"
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"intelliserve:upload:{filename}:{chunk_seq}:{display_title}"))
            chunk: Dict[str, Any] = {
                "id": doc_id,
                "title": display_title,
                "category": doc_stem,
                "content": f"【{doc_stem} - {display_title}】\n{body}",
                "tags": [doc_stem],
                "keywords": [],
                "source": f"upload:{filename}",
                "updatedAt": now_iso,
            }
            chunk["content_hash"] = _compute_chunk_hash(chunk)
            chunks.append(chunk)

    return chunks

def get_default_faq_chunks() -> List[Dict[str, Any]]:
    """获取预设切片列表"""
    return parse_faq_markdown(FAQ_MARKDOWN_DOC)
