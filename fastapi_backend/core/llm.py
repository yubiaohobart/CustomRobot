"""
DeepSeek 大语言模型异步客户端 (DeepSeek Async Client)
提供连接池复用、指数退避重试、结构化 JSON 输出、客服对话生成与意图路由能力。
"""

import asyncio
from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Dict, List, Literal, Optional
import httpx

from config import settings
from core.logger import cprint

PromptMode = Literal["customer", "copilot"]

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_DEFAULT_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE_SEC = 0.4
_MAX_HISTORY_MESSAGES = 6


@dataclass(slots=True)
class LLMResult:
    """大模型单次生成的结构化结果（区分真实生成与降级兜底）"""

    content: str
    ok: bool
    is_fallback: bool = False
    error: Optional[str] = None
    latency_ms: int = 0
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    reasoning_content: Optional[str] = None


def _is_reasoning_model(model_name: str) -> bool:
    lowered = (model_name or "").lower()
    return any(tag in lowered for tag in ("reasoner", "o1-", "o3-")) or lowered in ("o1", "o3")


def _format_knowledge_hits(hits: Optional[List[Dict[str, Any]]]) -> str:
    if not hits:
        return "暂无直接匹配的知识库条款。"
    blocks: List[str] = []
    for idx, doc in enumerate(hits, 1):
        title = doc.get("title") or f"参考条款 {idx}"
        content = (doc.get("snippet") or doc.get("content") or "").strip()
        if content:
            blocks.append(f"【参考条款 {idx} - {title}】\n{content}")
    return "\n\n".join(blocks) if blocks else "暂无直接匹配的知识库条款。"


def _format_business_facts(business_facts: str, order_id: Optional[str]) -> str:
    text = (business_facts or "").strip()
    if text:
        return text
    if order_id:
        return f"关联订单号：{order_id}"
    return "当前尚未关联特定订单或物流实体数据。"


def build_service_system_prompt(
    *,
    mode: PromptMode = "customer",
    hits: Optional[List[Dict[str, Any]]] = None,
    memory_summary: str = "",
    user_profile: Optional[Dict[str, Any]] = None,
    business_facts: str = "",
    order_id: Optional[str] = None,
) -> str:
    """组装客服回复 / 坐席 Copilot 草稿系统提示词"""
    role_intro = (
        "你是一名官方资深人工客服坐席助手（Copilot），请直接站在坐席角度起草一段专业、礼貌、可直接发送给客户的回复草稿。"
        if mode == "copilot"
        else "你是一名官方资深智能客服主管，请以严谨、专业、温暖的口吻直接解答客户咨询并协助推进售后与订单处理。"
    )
    profile = user_profile or {}
    vip_level = profile.get("vipLevel", "普通会员")
    customer_name = profile.get("name", "尊敬的客户")
    context_str = _format_knowledge_hits(hits)
    facts_str = _format_business_facts(business_facts, order_id)
    summary_str = (memory_summary or "").strip() or "新会话接入，暂无历史摘要。"
    limit_text = settings.auto_refund_limit_text

    return (
        f"{role_intro}\n\n"
        f"【客户画像】\n"
        f"- 称呼：{customer_name}\n"
        f"- 会员等级：{vip_level}（黄金/钻石会员退换货享平台退货运费补贴特权，可在相关场景主动提醒）\n\n"
        f"【退款安全门控规则】\n"
        f"- 单笔退款金额 < {limit_text} 元：支持智能客服自动极速退款（需客户确认后触发）。\n"
        f"- 单笔退款金额 >= {limit_text} 元：涉及资金安全，须提交工单转人工客服加急审核。\n\n"
        f"【动态业务事实 (Business Facts)】\n{facts_str}\n\n"
        f"【知识库参考条款】\n{context_str}\n\n"
        f"【历史会话记忆摘要】\n{summary_str}\n\n"
        f"【回答纪律】\n"
        f"1. 订单、物流、发票、退款状态等事实严格以【动态业务事实】为准，政策时效以【知识库参考条款】为准；\n"
        f"2. 未提及的信息如实告知待核实，严禁编造不存在的承诺、单号或服务；\n"
        f"3. 若客户表达强烈不满、催促或要求人工，需表达理解并明确人工加急跟进。"
    )


class DeepSeekLLMClient:
    """DeepSeek（及兼容 OpenAI Chat Completions 协议）异步客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model
        self._timeout = timeout
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max(0, max_retries)

        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None
        self._client_lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_api_key(self) -> str:
        return (self._api_key if self._api_key is not None else settings.DEEPSEEK_API_KEY).strip()

    def _get_base_url(self) -> str:
        return (self._base_url if self._base_url is not None else settings.DEEPSEEK_BASE_URL).rstrip("/")

    def _get_model(self, override: Optional[str] = None) -> str:
        return override or self._model or settings.DEEPSEEK_MODEL

    def _get_timeout(self) -> float:
        return self._timeout if self._timeout is not None else settings.LLM_TIMEOUT_SECONDS

    def _get_lock(self, loop: asyncio.AbstractEventLoop) -> asyncio.Lock:
        if self._client_lock is None or self._lock_loop is not loop:
            self._client_lock = asyncio.Lock()
            self._lock_loop = loop
        return self._client_lock

    async def _get_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is not None and not self._client.is_closed and self._client_loop is loop:
            return self._client

        async with self._get_lock(loop):
            if self._client is None or self._client.is_closed or self._client_loop is not loop:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=5.0, read=self._get_timeout(), write=10.0, pool=5.0),
                    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
                )
                self._client_loop = loop
        return self._client

    async def close(self) -> None:
        """优雅关闭复用的异步 HTTP 客户端"""
        client = self._client
        client_loop = self._client_loop
        self._client = None
        self._client_loop = None
        if client is not None and not client.is_closed:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if client_loop is None or running_loop is client_loop:
                await client.aclose()

    @staticmethod
    def _extract_recent_turns(
        recent_messages: Optional[List[Dict[str, Any]]],
        *,
        current_user_message: str = "",
        max_history: int = _MAX_HISTORY_MESSAGES,
    ) -> List[Dict[str, str]]:
        """提取最近有效对话轮次，跳过系统通知并避免与本轮输入重复"""
        if not recent_messages or max_history <= 0:
            return []

        current_text = current_user_message.strip()
        history_turns: List[Dict[str, str]] = []
        for item in recent_messages:
            if not isinstance(item, dict):
                continue
            raw_role = item.get("role")
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if raw_role == "user":
                history_turns.append({"role": "user", "content": content})
            elif raw_role in ("assistant", "human_agent"):
                history_turns.append({"role": "assistant", "content": content})

        if history_turns and history_turns[-1]["role"] == "user" and history_turns[-1]["content"] == current_text:
            history_turns = history_turns[:-1]

        return history_turns[-max_history:]

    @classmethod
    def build_messages(
        cls,
        *,
        system_prompt: str,
        user_message: str,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        max_history: int = _MAX_HISTORY_MESSAGES,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(
            cls._extract_recent_turns(
                recent_messages,
                current_user_message=user_message,
                max_history=max_history,
            )
        )
        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        *,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        default_temp = self._temperature if self._temperature is not None else settings.DEEPSEEK_TEMPERATURE
        default_tokens = self._max_tokens if self._max_tokens is not None else settings.DEEPSEEK_MAX_TOKENS
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else default_tokens,
        }
        if not _is_reasoning_model(model):
            payload["temperature"] = temperature if temperature is not None else default_temp
            if response_format is not None:
                payload["response_format"] = response_format
        return payload

    async def _post_with_retry(
        self,
        *,
        api_key: str,
        payload: Dict[str, Any],
        timeout_override: Optional[float] = None,
    ) -> httpx.Response:
        client = await self._get_client()
        url = f"{self._get_base_url()}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                coro = client.post(url, headers=headers, json=payload)
                resp = await (asyncio.wait_for(coro, timeout=timeout_override) if timeout_override else coro)
                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_BASE_SEC * (2 ** attempt)
                    cprint.warning(
                        f"DeepSeek API 返回可重试状态 HTTP {resp.status_code}，"
                        f"{delay:.1f}s 后第 {attempt + 1} 次重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.NetworkError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_BASE_SEC * (2 ** attempt)
                    cprint.warning(
                        f"DeepSeek 网络/超时抖动 ({type(exc).__name__})，"
                        f"{delay:.1f}s 后第 {attempt + 1} 次重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        assert last_exc is not None
        raise last_exc

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        log_prompt_chars: Optional[int] = None,
    ) -> LLMResult:
        """底层对话调用原语，统一处理鉴权、重试、JSON 解析与降级归因"""
        target_model = self._get_model(model)
        prompt_chars = log_prompt_chars if log_prompt_chars is not None else sum(len(m.get("content", "")) for m in messages)

        api_key = self._get_api_key()
        if not api_key:
            cprint.llm(target_model, prompt_chars, 0.0, is_fallback=True)
            return LLMResult(
                content="智能大模型服务暂未配置 API Key，请先配置 DEEPSEEK_API_KEY 或点击转接人工客服为您处理。",
                ok=False,
                is_fallback=True,
                error="MISSING_API_KEY",
                model=target_model,
            )

        payload = self._build_payload(
            messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        t_req = time.time()
        try:
            resp = await self._post_with_retry(
                api_key=api_key,
                payload=payload,
                timeout_override=timeout,
            )
            latency = time.time() - t_req
            latency_ms = int(latency * 1000)

            if resp.status_code != 200:
                cprint.error(f"DeepSeek API 响应异常 (HTTP {resp.status_code}): {resp.text[:160]}")
                return LLMResult(
                    content=f"抱歉，智能客服服务响应异常 (HTTP {resp.status_code})，请稍后再试或联系人工客服为您处理。",
                    ok=False,
                    is_fallback=True,
                    error=f"HTTP_{resp.status_code}",
                    latency_ms=latency_ms,
                    model=target_model,
                )

            try:
                data = resp.json()
            except ValueError as exc:
                cprint.error(f"DeepSeek API 返回非 JSON 响应: {exc}; body={resp.text[:160]}")
                return LLMResult(
                    content="抱歉，智能客服返回格式异常，请稍后重试或联系人工客服。",
                    ok=False,
                    is_fallback=True,
                    error="INVALID_JSON",
                    latency_ms=latency_ms,
                    model=target_model,
                )

            choices = data.get("choices") or []
            message = choices[0].get("message") or {} if choices else {}
            reply = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning_content") or "").strip() or None
            if not reply:
                cprint.error("DeepSeek API 返回内容为空")
                return LLMResult(
                    content="抱歉，智能客服暂时未能生成有效回复，请稍后重试或联系人工客服。",
                    ok=False,
                    is_fallback=True,
                    error="EMPTY_CONTENT",
                    latency_ms=latency_ms,
                    usage=data.get("usage"),
                    model=data.get("model") or target_model,
                    reasoning_content=reasoning,
                )

            cprint.llm(target_model, prompt_chars, latency, is_fallback=False)
            return LLMResult(
                content=reply,
                ok=True,
                is_fallback=False,
                latency_ms=latency_ms,
                usage=data.get("usage"),
                model=data.get("model") or target_model,
                reasoning_content=reasoning,
            )
        except Exception as exc:
            latency_ms = int((time.time() - t_req) * 1000)
            cprint.error(f"DeepSeek 网络请求异常: {exc}")
            return LLMResult(
                content="抱歉，与智能客服大模型通信遇到异常，请稍后重试或联系人工客服。",
                ok=False,
                is_fallback=True,
                error=type(exc).__name__,
                latency_ms=latency_ms,
                model=target_model,
            )

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        timeout: Optional[float] = None,
        validator: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """结构化 JSON 输出调用：自动开启 json_object 并剥离代码块围栏"""
        res = await self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        if not res.ok:
            return None

        text = res.content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            return validator(parsed) if validator else parsed
        except Exception as exc:
            cprint.warning(f"DeepSeek 结构化 JSON 解析失败: {type(exc).__name__}: {exc}")
            return None

    async def generate_completion(
        self,
        user_message: str,
        *,
        hits: Optional[List[Dict[str, Any]]] = None,
        memory_summary: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        business_facts: str = "",
        order_id: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        mode: PromptMode = "customer",
        system_prompt_override: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResult:
        """生成智能客服或坐席 Copilot 答复"""
        system_prompt = system_prompt_override or build_service_system_prompt(
            mode=mode,
            hits=hits,
            memory_summary=memory_summary,
            user_profile=user_profile,
            business_facts=business_facts,
            order_id=order_id,
        )
        messages = self.build_messages(
            system_prompt=system_prompt,
            user_message=user_message,
            recent_messages=recent_messages,
        )
        return await self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            log_prompt_chars=len(system_prompt),
        )

    async def classify_intent_structured(
        self,
        user_message: str,
        *,
        valid_intents: List[str],
        valid_sentiments: List[str],
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        memory_summary: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """L2 灰区结构化意图路由与上下文改写"""
        profile = user_profile or {}
        recent_order = profile.get("recentOrder")
        profile_order_id = profile.get("orderId") or (
            recent_order.get("orderId") if isinstance(recent_order, dict) else None
        )

        recent_turns = self._extract_recent_turns(
            recent_messages,
            current_user_message=user_message,
            max_history=4,
        )
        history_lines = [
            f"{'客户' if t['role'] == 'user' else '客服'}: {t['content'][:160]}"
            for t in recent_turns
        ]

        intents_desc = (
            "1. 订单查询与物流追踪：查询订单明细、发货状态、快递物流位置、签收进度。\n"
            "2. 退款申请与审批：客户明确要求现在发起/提交/办理退款或退货退款（注意：仅询问“能不能退/怎么退/运费谁出/多久到账”或明确表示“不是要退款”的，不要选此项）。\n"
            "3. 退款到账时效查询：询问退款多久到账、打款时间、审核进度。\n"
            "4. 退换货运费承担与会员权益：询问退货运费谁出、包邮、黄金/钻石会员免运费补贴。\n"
            "5. 7天无理由退货政策：询问7天无理由退货规则、条件、怎么退、能否换新。\n"
            "6. 特殊不可退换商品范围：询问拆封商品、定制商品、生鲜、内衣等是否支持退换。\n"
            "7. 1年联保与硬件保修条款：询问保修、维修、换新、进水、摔坏等质保问题。\n"
            "8. 常规售后咨询：寒暄、其他常规咨询或无法归入上述专项的问题。\n"
            "9. handoff：客户明确要求人工客服、转人工、表达强烈投诉或拒绝机器人。"
        )
        system_prompt = (
            "你是电商智能客服的 NLU 路由分析器，请结合上下文准确判断客户本轮真实意图、情绪，并在存在指代省略时补全查询。\n\n"
            f"可选 intent（必须严格精确匹配以下之一）：{', '.join(valid_intents)}\n"
            f"意图说明：\n{intents_desc}\n\n"
            f"可选 sentiment（必须严格精确匹配以下之一）：{', '.join(valid_sentiments)}\n\n"
            "请仅输出一个 JSON 对象，格式严格如下：\n"
            '{"intent": "...", "sentiment": "...", "rewritten_query": "...", "confidence": 0.92}\n'
            "要求：\n"
            "- rewritten_query：若当前提问含“它/这单/退掉吧”等指代或省略，结合历史对话和关联订单号改写为语义完整的一句话；若原句已清晰完整，直接保留原句。\n"
            "- 若客户是多意图复合句，优先判断需要业务动作（如退款/查单）或最核心诉求的意图；若仅否定退款（如“我不是要退款”），归类到其真实诉求。"
        )
        user_prompt = (
            f"关联订单号：{profile_order_id or '无'}\n"
            f"历史摘要：{memory_summary.strip() or '无'}\n"
            f"近期对话：\n{chr(10).join(history_lines) if history_lines else '无'}\n"
            f"当前客户消息：{user_message}"
        )

        def _validate(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            intent = parsed.get("intent")
            if intent not in valid_intents:
                return None
            sentiment = parsed.get("sentiment")
            if sentiment not in valid_sentiments:
                sentiment = "neutral"
            rewritten = str(parsed.get("rewritten_query") or "").strip() or user_message
            conf = float(parsed.get("confidence", 0.85))
            return {
                "intent": intent,
                "sentiment": sentiment,
                "rewritten_query": rewritten,
                "confidence": max(0.0, min(1.0, conf)),
            }

        return await self.chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=0.0,
            max_tokens=220,
            timeout=min(self._get_timeout(), 12.0),
            validator=_validate,
        )


# 全局单例 DeepSeek 客户端
deepseek_client = DeepSeekLLMClient()
