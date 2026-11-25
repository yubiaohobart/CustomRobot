"""
轻量彩色终端日志模块 (Color Logger)
基于标准库 logging 封装，提供统一彩色输出与 LangGraph 节点追踪装饰器。
"""

import functools
import inspect
import logging
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class LogColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_RED = "\033[41m"


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: LogColor.BRIGHT_BLUE,
        logging.INFO: LogColor.BRIGHT_GREEN,
        logging.WARNING: LogColor.BRIGHT_YELLOW,
        logging.ERROR: LogColor.BRIGHT_RED,
        logging.CRITICAL: f"{LogColor.BOLD}{LogColor.BG_RED}{LogColor.BRIGHT_WHITE}",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, LogColor.WHITE)
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"{LogColor.DIM}{ts}{LogColor.RESET} {color}[{record.levelname:<5}]{LogColor.RESET} {record.getMessage()}"
        if record.exc_info:
            line = f"{line}\n{color}{self.formatException(record.exc_info)}{LogColor.RESET}"
        return line


def _create_logger(name: str = "IntelliServe") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger


log = _create_logger()


class ColorPrinter:
    """精简彩色终端打印助手"""

    @staticmethod
    def colorize(text: str, color: str) -> str:
        return f"{color}{text}{LogColor.RESET}" if color else text

    def __call__(self, msg: str, color: Optional[str] = None) -> None:
        print(self.colorize(msg, color or LogColor.BRIGHT_WHITE))

    @staticmethod
    def divider(char: str = "═", width: int = 68, color: str = LogColor.BRIGHT_CYAN) -> None:
        print(f"{color}{char * width}{LogColor.RESET}")

    @staticmethod
    def banner(title: str, subtitle: Optional[str] = None) -> None:
        border = "═" * 68
        print(f"\n{LogColor.BRIGHT_CYAN}{border}{LogColor.RESET}")
        print(f"{LogColor.BOLD}{LogColor.BRIGHT_WHITE}🚀 {title}{LogColor.RESET}")
        if subtitle:
            print(f"{LogColor.DIM}{subtitle}{LogColor.RESET}")
        print(f"{LogColor.BRIGHT_CYAN}{border}{LogColor.RESET}\n")

    @staticmethod
    def startup_item(label: str, value: str, value_color: str = LogColor.BRIGHT_WHITE, extra: Optional[str] = None) -> None:
        suffix = f" {extra}" if extra else ""
        print(f"🔹 {label:<18} {value_color}{value}{LogColor.RESET}{suffix}")

    @staticmethod
    def flow_start(session_id: str, mode: str, user_message: str, confirm_action: Optional[str] = None, customer_label: Optional[str] = None) -> None:
        preview = user_message if len(user_message) <= 48 else f"{user_message[:45]}..."
        extra = f" [{confirm_action}]" if confirm_action else ""
        cust = f" {customer_label}" if customer_label else ""
        print(f"\n{LogColor.BRIGHT_CYAN}━━▶{LogColor.RESET} [{session_id}]{cust} | {mode}{extra} | \"{preview}\"")

    @staticmethod
    def node(node_name: str, action: str, details: Optional[str] = None) -> None:
        detail_str = f" ({details})" if details else ""
        print(f"  {LogColor.BRIGHT_GREEN}•{LogColor.RESET} {LogColor.BRIGHT_CYAN}{node_name:<18}{LogColor.RESET} {action}{detail_str}")

    @staticmethod
    def node_interrupt(node_name: str, action: str, details: Optional[str] = None) -> None:
        detail_str = f" ({details})" if details else ""
        print(f"  {LogColor.BRIGHT_YELLOW}•{LogColor.RESET} {LogColor.BRIGHT_CYAN}{node_name:<18}{LogColor.RESET} {LogColor.BRIGHT_YELLOW}{action}{LogColor.RESET}{detail_str}")

    @staticmethod
    def flow_end(session_id: str, node_path: List[str], status: str = "COMPLETED", duration_ms: int = 0, extra: Optional[str] = None) -> None:
        suffix = f" | {extra}" if extra else ""
        print(f"{LogColor.BRIGHT_CYAN}━━🏁{LogColor.RESET} [{session_id}] {status} | {duration_ms}ms{suffix} | {' -> '.join(node_path)}\n")

    @classmethod
    def flow_summary(cls, session_id: str, final_state: Dict[str, Any], duration_ms: int = 0, is_resumed: bool = False) -> None:
        is_interrupted = bool(final_state.get("__interrupt__"))
        status = "INTERRUPTED" if is_interrupted else ("HANDOFF" if final_state.get("handoff") else "COMPLETED")
        nodes = [t.split(":", 1)[0].strip() for t in (final_state.get("trace") or []) if isinstance(t, str) and ":" in t]
        path = ["START", *(["resume"] if is_resumed else []), *nodes, "INTERRUPT" if is_interrupted else "END"]
        cls.flow_end(session_id, path, status=status, duration_ms=duration_ms)

    @staticmethod
    def llm(model: str, prompt_len: int, token_latency: float, is_fallback: bool = False) -> None:
        tag = f"{LogColor.YELLOW}降级{LogColor.RESET}" if is_fallback else f"{LogColor.BRIGHT_GREEN}正常{LogColor.RESET}"
        print(f"    │ 🤖 LLM: {model} | {prompt_len}字 | {token_latency:.2f}s | {tag}")

    @staticmethod
    def transfer(session_id: str, agent_id: str, reason: str) -> None:
        print(f"    │ ⚡ 转人工: [{session_id}] ➜ {agent_id} ({reason})")

    @staticmethod
    def websocket(event_type: str, session_id: str, detail: str) -> None:
        print(f"🔌 [WS·{event_type}] {session_id} ➜ {detail}")

    @staticmethod
    def success(msg: str) -> None:
        print(f"{LogColor.BRIGHT_GREEN}✅ {msg}{LogColor.RESET}")

    @staticmethod
    def warning(msg: str) -> None:
        print(f"{LogColor.BRIGHT_YELLOW}⚠️  {msg}{LogColor.RESET}")

    @staticmethod
    def error(msg: str) -> None:
        print(f"{LogColor.BRIGHT_RED}❌ {msg}{LogColor.RESET}")

    @staticmethod
    def info(msg: str) -> None:
        print(f"{LogColor.CYAN}ℹ️  {msg}{LogColor.RESET}")


cprint = ColorPrinter()


def trace_node(node_name: str, description: Optional[str] = None) -> Callable:
    """LangGraph 节点执行耗时与状态追踪装饰器"""

    def _on_success(t0: float, result: Any) -> Any:
        ms = int((time.perf_counter() - t0) * 1000)
        traces = [t for t in (result.get("trace") or []) if t != "__RESET__"] if isinstance(result, dict) else []
        summary = str(traces[-1]).split(":", 1)[-1].strip() if traces else "完成"
        cprint.node(node_name, summary, f"{ms}ms")
        return result

    def _on_error(t0: float, exc: BaseException) -> None:
        ms = int((time.perf_counter() - t0) * 1000)
        if exc.__class__.__name__ == "GraphInterrupt":
            cprint.node_interrupt(node_name, "触发 interrupt() 挂起等待确认", f"{ms}ms")
        else:
            cprint.error(f"[{node_name}] 节点执行异常: {exc!r}")

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                t0 = time.perf_counter()
                try:
                    return _on_success(t0, await fn(*args, **kwargs))
                except BaseException as exc:
                    _on_error(t0, exc)
                    raise
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return _on_success(t0, fn(*args, **kwargs))
            except BaseException as exc:
                _on_error(t0, exc)
                raise
        return sync_wrapper

    return decorator
