"""
DeepSeek 大模型客户端 (DeepSeek LLM Client)
模式: 官方 API 直连 (deepseek-chat / deepseek-reasoner)
特性: 严格以 FAQ 知识库与业务中台事实为基准，提供专业、温暖、严谨的智能客服答复
"""

import time
from typing import List, Dict, Any, Optional
import httpx
from config import settings
from core.logger import cprint


class DeepSeekLLMClient:
    def __init__(
        self,
        api_key: str = settings.DEEPSEEK_API_KEY,
        base_url: str = settings.DEEPSEEK_BASE_URL,
        model: str = settings.DEEPSEEK_MODEL
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 45.0

    async def generate_response(
        self,
        user_message: str,
        retrieved_docs: List[Dict[str, Any]],
        summary_memory: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        business_facts: str = "",
        order_info: Optional[Dict[str, Any]] = None,
        order_summary: str = ""
    ) -> str:
        """
        调用 DeepSeek API 生成客服答复
        采用通用业务事实槽位 (business_facts)，严格遵循知识库与业务实体作答
        """
        user_profile = user_profile or {}
        vip_level = user_profile.get("vipLevel", "普通会员")
        customer_name = user_profile.get("name", "尊敬的客户")

        # 1. 整理知识库参考条款
        context_blocks = []
        for idx, doc in enumerate(retrieved_docs, 1):
            title = doc.get("title", f"参考条款 {idx}")
            content = doc.get("content", "")
            context_blocks.append(f"【参考条款 {idx} - {title}】\n{content}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "暂无直接匹配的知识库条款。"

        # 2. 提取通用业务事实 (优先 business_facts，兼容 order_summary / order_info)
        facts_text = (business_facts or order_summary).strip()
        if not facts_text and order_info:
            from services.order_service import order_service
            facts_text = order_service.format_order_summary_text(order_info)

        business_facts_block = facts_text if facts_text else "当前客户尚未触发或关联特定业务中台实体数据。"

        # 3. 构建高标准客服 Prompt
        system_prompt = f"""你是一名【XX商城】的官方资深金牌智能客服主管。
你的职责是严谨、专业、礼貌、温和地解答客户咨询，并结合业务中台事实协助办理售后、订单、物流及相关权益。

【客户画像与特权】
- 称呼：{customer_name}
- 会员等级：{vip_level}
（提示：如果客户是【黄金会员】或以上，请务必主动提醒其享有“退货免运费”专属特权，退货运费由平台全额补贴！）

【动态业务实体事实 (Business Facts)】
{business_facts_block}

【XX商城官方售后与退换货政策参考 (2026版)】
{context_str}

【历史会话记忆摘要】
{summary_memory if summary_memory else "新用户接入，初次提问。"}

【回答纪律】：
1. 涉及具体业务实体（如订单、物流、商品、发票、权益、优惠券等）时，必须严格基于【动态业务实体事实】作答；
2. 商城政策、时效规定（7天退换、运费承担、特殊商品范围、48小时质检及到账、1年联保）严格遵循【XX商城官方售后与退换货政策参考】；
3. 事实与政策中未提及的信息如实告知，严禁凭空编造不存在的事实或服务；
4. 口吻温暖热情、换位思考，条理清晰；
5. 如客户表达强烈不满、催促或明确要求人工，表达理解并告知已为您做好加急人工转接准备。"""

        # 4. 直接发起 DeepSeek 异步请求 (api_key 确定存在)
        t_req = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": settings.DEEPSEEK_TEMPERATURE,
                        "max_tokens": settings.DEEPSEEK_MAX_TOKENS
                    }
                )
                latency = time.time() - t_req
                if resp.status_code == 200:
                    data = resp.json()
                    reply = data["choices"][0]["message"]["content"].strip()
                    cprint.llm(self.model, len(system_prompt), latency, is_fallback=False)
                    return reply
                else:
                    cprint.error(f"DeepSeek API 响应异常 (HTTP {resp.status_code}): {resp.text[:120]}")
                    return f"抱歉，智能客服服务响应异常 (HTTP {resp.status_code})，请稍后再试或联系人工客服为您处理。"
        except Exception as e:
            cprint.error(f"DeepSeek 网络请求异常: {e}")
            return "抱歉，与智能客服大模型通信遇到异常，请稍后重试或联系人工客服。"


# 全局单例 DeepSeek 客户端
deepseek_client = DeepSeekLLMClient()
