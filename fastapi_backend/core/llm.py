"""
DeepSeek 大模型客户端 (DeepSeek LLM Client)
模式: 官方 API 直连 (deepseek-chat / deepseek-reasoner)
职责: 连接池管理、瞬态错误重试、上下文/多轮消息组装与结构化调用结果返回
"""

import asyncio
from dataclasses import dataclass
import time
from typing import Any, Dict, List, Literal, Optional
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


class DeepSeekLLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None
        self._client_lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

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

    def _get_lock(self, loop: asyncio.AbstractEventLoop) -> asyncio.Lock:
        if self._client_lock is None or self._lock_loop is not loop:
            self._client_lock = asyncio.Lock()
            self._lock_loop = loop
        return self._client_lock

    async def _get_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if (
            self._client is not None
            and not self._client.is_closed
            and self._client_loop is loop
        ):
            return self._client

        async with self._get_lock(loop):
            if (
                self._client is None
                or self._client.is_closed
                or self._client_loop is not loop
            ):
                if self._client is not None and not self._client.is_closed and self._client_loop is loop:
                    await self._client.aclose()
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=5.0,
                        read=self.timeout,
                        write=10.0,
                        pool=5.0,
                    ),
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
    def _format_hits(hits: Optional[List[Dict[str, Any]]]) -> str:
        if not hits:
            return "暂无直接匹配的知识库条款。"
        blocks: List[str] = []
        for idx, doc in enumerate(hits, 1):
            title = doc.get("title") or f"参考条款 {idx}"
            content = (doc.get("snippet") or doc.get("content") or "").strip()
            if content:
                blocks.append(f"【参考条款 {idx} - {title}】\n{content}")
        return "\n\n".join(blocks) if blocks else "暂无直接匹配的知识库条款。"

    @staticmethod
    def _format_business_facts(business_facts: str, order_id: Optional[str]) -> str:
        text = business_facts.strip()
        if text:
            return text
        if order_id:
            return f"关联订单号：{order_id}"
        return "当前尚未关联特定订单或物流实体数据。"

    def _build_system_prompt(
        self,
        *,
        mode: PromptMode,
        hits: Optional[List[Dict[str, Any]]],
        memory_summary: str,
        user_profile: Optional[Dict[str, Any]],
        business_facts: str,
        order_id: Optional[str],
    ) -> str:
        profile = user_profile or {}
        vip_level = profile.get("vipLevel", "普通会员")
        customer_name = profile.get("name", "尊敬的客户")
        context_str = self._format_hits(hits)
        facts_str = self._format_business_facts(business_facts, order_id)
        summary_str = memory_summary.strip() or "新会话接入，暂无历史摘要。"
        limit_text = settings.auto_refund_limit_text

        role_intro = (
            "你是一名官方资深人工客服坐席助手（Copilot），请直接站在坐席角度起草一段专业、礼貌、可直接发送给客户的回复草稿。"
            if mode == "copilot"
            else "你是一名官方资深智能客服主管，请以严谨、专业、温暖的口吻直接解答客户咨询并协助推进售后与订单处理。"
        )

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

    @staticmethod
    def _build_messages(
        *,
        system_prompt: str,
        user_message: str,
        recent_messages: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        current_text = user_message.strip()

        if recent_messages:
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

            # 若调用方传入的 recent_messages 末尾已包含本轮 user_message，则避免重复发送两遍
            if history_turns and history_turns[-1]["role"] == "user" and history_turns[-1]["content"] == current_text:
                history_turns = history_turns[:-1]

            if history_turns:
                messages.extend(history_turns[-_MAX_HISTORY_MESSAGES:])

        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_request_payload(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
        }
        # deepseek-reasoner 对采样参数有严格限制，仅对常规对话模型传入 temperature
        if "reasoner" not in self.model.lower():
            payload["temperature"] = settings.DEEPSEEK_TEMPERATURE
        return payload

    async def _post_with_retry(
        self,
        *,
        api_key: str,
        payload: Dict[str, Any],
    ) -> httpx.Response:
        client = await self._get_client()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_BASE_SEC * (2 ** attempt)
                    cprint.warning(
                        f"DeepSeek API 返回可重试状态 HTTP {resp.status_code}，"
                        f"{delay:.1f}s 后第 {attempt + 1} 次重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_BASE_SEC * (2 ** attempt)
                    cprint.warning(
                        f"DeepSeek 网络抖动 ({type(exc).__name__})，"
                        f"{delay:.1f}s 后第 {attempt + 1} 次重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        assert last_exc is not None
        raise last_exc

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
    ) -> LLMResult:
        """
        调用 DeepSeek API 生成答复，返回携带状态与耗时信息的结构化 LLMResult。
        """
        system_prompt = self._build_system_prompt(
            mode=mode,
            hits=hits,
            memory_summary=memory_summary,
            user_profile=user_profile,
            business_facts=business_facts,
            order_id=order_id,
        )

        api_key = self.api_key
        if not api_key:
            cprint.llm(self.model, len(system_prompt), 0.0, is_fallback=True)
            return LLMResult(
                content="智能大模型服务暂未配置 API Key，请先配置 DEEPSEEK_API_KEY 或点击转接人工客服为您处理。",
                ok=False,
                is_fallback=True,
                error="MISSING_API_KEY",
            )

        messages = self._build_messages(
            system_prompt=system_prompt,
            user_message=user_message,
            recent_messages=recent_messages,
        )
        payload = self._build_request_payload(messages)

        t_req = time.time()
        try:
            resp = await self._post_with_retry(api_key=api_key, payload=payload)
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
                )

            choices = data.get("choices") or []
            message = choices[0].get("message") or {} if choices else {}
            reply = (message.get("content") or "").strip()
            if not reply:
                cprint.error("DeepSeek API 返回内容为空")
                return LLMResult(
                    content="抱歉，智能客服暂时未能生成有效回复，请稍后重试或联系人工客服。",
                    ok=False,
                    is_fallback=True,
                    error="EMPTY_CONTENT",
                    latency_ms=latency_ms,
                    usage=data.get("usage"),
                )

            cprint.llm(self.model, len(system_prompt), latency, is_fallback=False)
            return LLMResult(
                content=reply,
                ok=True,
                is_fallback=False,
                latency_ms=latency_ms,
                usage=data.get("usage"),
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
            )

    async def generate_response(
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
    ) -> str:
        """便捷文本接口：返回生成的文本或兜底提示"""
        result = await self.generate_completion(
            user_message,
            hits=hits,
            memory_summary=memory_summary,
            user_profile=user_profile,
            business_facts=business_facts,
            order_id=order_id,
            recent_messages=recent_messages,
            mode=mode,
        )
        return result.content


# 全局单例 DeepSeek 客户端
deepseek_client = DeepSeekLLMClient()
