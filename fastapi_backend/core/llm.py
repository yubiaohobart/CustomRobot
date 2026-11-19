"""
DeepSeek 大模型客户端 (DeepSeek LLM Client)
模式: 官方 API 直连 (deepseek-chat / deepseek-reasoner)
特性: 严格以 FAQ 知识库与业务中台事实为基准，提供专业、温暖、严谨的智能客服答复
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
import httpx
from config import settings
from core.logger import cprint


class DeepSeekLLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def api_key(self) -> str:
        return (self._api_key if self._api_key is not None else settings.DEEPSEEK_API_KEY).strip()

    @property
    def base_url(self) -> str:
        return (self._base_url if self._base_url is not None else settings.DEEPSEEK_BASE_URL).rstrip("/")

    @property
    def model(self) -> str:
        return self._model if self._model is not None else settings.DEEPSEEK_MODEL

    @property
    def timeout(self) -> float:
        return self._timeout if self._timeout is not None else settings.LLM_TIMEOUT_SECONDS

    async def _get_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if (
            self._client is None
            or self._client.is_closed
            or self._client_loop is not loop
        ):
            if self._client is not None and not self._client.is_closed:
                # 若旧客户端绑定在不同的已切换事件循环上，仅丢弃引用避免跨循环 close 报错
                if self._client_loop is loop:
                    await self._client.aclose()
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._client_loop = loop
        return self._client

    async def close(self) -> None:
        """优雅关闭复用的异步 HTTP 客户端"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._client_loop = None

    async def generate_response(
        self,
        user_message: str,
        retrieved_docs: Optional[List[Dict[str, Any]]] = None,
        hits: Optional[List[Dict[str, Any]]] = None,
        summary_memory: str = "",
        memory_summary: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        business_facts: str = "",
        order_info: Optional[Dict[str, Any]] = None,
        order_id: Optional[str] = None,
        order_summary: str = "",
    ) -> str:
        """
        调用 DeepSeek API 生成客服答复
        优先消费调用方传入的精炼 hits、business_facts 与 memory_summary，不反向耦合上层业务服务。
        """
        user_profile = user_profile or {}
        vip_level = user_profile.get("vipLevel", "普通会员")
        customer_name = user_profile.get("name", "尊敬的客户")

        # 1. 整理知识库参考条款 (优先支持 hits 精简切片，兼容 retrieved_docs)
        doc_list = hits if hits is not None else (retrieved_docs or [])
        context_blocks = []
        for idx, doc in enumerate(doc_list, 1):
            title = doc.get("title", f"参考条款 {idx}")
            content = doc.get("snippet") or doc.get("content", "")
            context_blocks.append(f"【参考条款 {idx} - {title}】\n{content}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "暂无直接匹配的知识库条款。"

        # 2. 整理动态业务事实（由上层工作流/路由传入，若仅提供 order_info 字典则兜底序列化）
        facts_text = (business_facts or order_summary).strip()
        if not facts_text and order_info:
            facts_text = json.dumps(order_info, ensure_ascii=False)
        elif not facts_text and order_id:
            facts_text = f"关联订单号：{order_id}"

        business_facts_block = facts_text if facts_text else "当前客户尚未触发或关联特定业务中台实体数据。"
        effective_summary = (summary_memory or memory_summary or "").strip()
        limit_text = settings.auto_refund_limit_text

        # 3. 构建高标准客服 Prompt
        system_prompt = f"""你是一名【XX商城】的官方资深金牌智能客服主管。
你的职责是严谨、专业、礼貌、温和地解答客户咨询，并结合业务中台事实协助办理售后、订单、物流及相关权益。

【客户画像与特权】
- 称呼：{customer_name}
- 会员等级：{vip_level}
（提示：如果客户是【黄金会员】或以上，请务必主动提醒其享有“退货免运费”专属特权，退货运费由平台全额补贴！）

【XX商城订单退款审核与安全规则】
1. 当退款金额【< {limit_text} 元】：可通过智能客服直接秒级退款（无需人工干涉，资金原路秒级退回解冻）。
2. 当退款金额【>= {limit_text} 元】：涉及商城资金安全，必须经过人工干涉，系统自动提交工单并无缝接入人工客服加急审核。

【动态业务实体事实 (Business Facts)】
{business_facts_block}

【XX商城官方售后与退换货政策参考 (2026版)】
{context_str}

【历史会话记忆摘要】
{effective_summary if effective_summary else "新用户接入，初次提问。"}

【回答纪律】：
1. 涉及具体业务实体（如订单、物流、商品、发票、权益、退款状态等）时，必须严格基于【动态业务实体事实】作答；
2. 若客户表达退款意图，金额 < {limit_text} 元时告知“已由智能客服为您直接办理极速退款”；金额 >= {limit_text} 元时告知“涉及资金安全，已为您提交工单并转接人工客服加急审核”；
3. 商城政策、时效规定（7天退换、运费承担、特殊商品范围、48小时质检及到账、1年联保）严格遵循【XX商城官方售后与退换货政策参考】；
4. 事实与政策中未提及的信息如实告知，严禁凭空编造不存在的事实或服务；
5. 口吻温暖热情、换位思考，条理清晰；
6. 如客户表达强烈不满、催促或明确要求人工，表达理解并告知已为您做好加急人工转接准备。"""

        # 4. API Key 空值前置拦截，避免无效公网请求
        api_key = self.api_key
        if not api_key:
            cprint.llm(self.model, len(system_prompt), 0.0, is_fallback=True)
            return "智能大模型服务暂未配置 API Key，请先配置 DEEPSEEK_API_KEY 或点击转接人工客服为您处理。"

        # 5. 复用 AsyncClient 发起 DeepSeek 异步请求
        t_req = time.time()
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": settings.DEEPSEEK_TEMPERATURE,
                    "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
                },
            )
            latency = time.time() - t_req
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                message = choices[0].get("message") or {} if choices else {}
                reply = (message.get("content") or "").strip()
                if not reply:
                    cprint.error("DeepSeek API 返回内容为空")
                    return "抱歉，智能客服暂时未能生成有效回复，请稍后重试或联系人工客服。"
                cprint.llm(self.model, len(system_prompt), latency, is_fallback=False)
                return reply

            cprint.error(f"DeepSeek API 响应异常 (HTTP {resp.status_code}): {resp.text[:120]}")
            return f"抱歉，智能客服服务响应异常 (HTTP {resp.status_code})，请稍后再试或联系人工客服为您处理。"
        except Exception as e:
            cprint.error(f"DeepSeek 网络请求异常: {e}")
            return "抱歉，与智能客服大模型通信遇到异常，请稍后重试或联系人工客服。"


# 全局单例 DeepSeek 客户端
deepseek_client = DeepSeekLLMClient()
