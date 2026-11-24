"""
彩色终端日志工具模块 (Color Logger Module)
提供开箱即用、工业级、支持 ANSI 绚丽色彩的终端日志工具
无需第三方复杂库，基于 Python 标准库 logging 封装，支持多级别彩色输出与业务标签高亮
"""

import functools
import inspect
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

_ANSI_DISABLED = bool(os.getenv("NO_COLOR"))
_TRACE_DURATION_RE = re.compile(r"\s*\(\d+ms\)\s*$")


# ANSI 终端颜色转义码
class LogColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # 前景色 (Foreground)
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 高亮前景色 (Bright Foreground)
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色 (Background)
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def _c(code: str) -> str:
    return "" if _ANSI_DISABLED else code


def colorize(text: str, color: str) -> str:
    """按 NO_COLOR 配置安全地为文本片段着色"""
    if _ANSI_DISABLED or not color:
        return text
    return f"{color}{text}{LogColor.RESET}"


class ColoredFormatter(logging.Formatter):
    """自定义带颜色的格式化器（保留异常堆栈与 stack_info 输出）"""

    LEVEL_COLORS = {
        logging.DEBUG: LogColor.BRIGHT_BLUE,
        logging.INFO: LogColor.BRIGHT_GREEN,
        logging.WARNING: LogColor.BRIGHT_YELLOW,
        logging.ERROR: LogColor.BRIGHT_RED,
        logging.CRITICAL: f"{LogColor.BOLD}{LogColor.BG_RED}{LogColor.BRIGHT_WHITE}",
    }

    LEVEL_ICONS = {
        logging.DEBUG: "🔍 [DEBUG]",
        logging.INFO: "✨ [INFO ]",
        logging.WARNING: "⚠️ [WARN ]",
        logging.ERROR: "❌ [ERROR]",
        logging.CRITICAL: "🚨 [CRIT ]",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = _c(self.LEVEL_COLORS.get(record.levelno, LogColor.WHITE))
        icon = self.LEVEL_ICONS.get(record.levelno, f"[{record.levelname}]")
        reset = _c(LogColor.RESET)
        dim = _c(LogColor.DIM)
        cyan = _c(LogColor.CYAN)

        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        time_str = f"{dim}{timestamp}{reset}"
        module_name = f"{cyan}{record.name}{reset}"
        message = record.getMessage()

        line = f"{time_str} {color}{icon}{reset} {dim}({module_name}){reset} {color}{message}{reset}"
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            line = f"{line}\n{color}{exc_text}{reset}"
        if record.stack_info:
            stack_text = self.formatStack(record.stack_info)
            line = f"{line}\n{dim}{stack_text}{reset}"
        return line


def setup_logger(name: str = "IntelliServe", level: int = logging.INFO) -> logging.Logger:
    """初始化并返回全局标准彩色 Logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


# 默认全局应用 logger
app_logger = setup_logger("IntelliServe")


def _extract_trace_summary(result: Any, node_name: str) -> str:
    """从节点返回值中的 trace 列表提取本节点输出摘要，避免业务代码重复写打印判断"""
    if not isinstance(result, dict):
        return "完成"
    trace_items = [t for t in (result.get("trace") or []) if t != "__RESET__"]
    if not trace_items:
        return "完成"
    latest = str(trace_items[-1]).strip()
    prefix = f"{node_name}:"
    if latest.startswith(prefix):
        latest = latest[len(prefix):].strip()
    return _TRACE_DURATION_RE.sub("", latest).strip() or "完成"


def _build_node_path(
    trace_list: List[str],
    is_interrupted: bool = False,
    is_resumed: bool = False,
) -> List[str]:
    """从 state['trace'] 提取单轮对话节点执行路径，用于终端结尾汇总展示"""
    nodes = [
        item.split(":", 1)[0].strip()
        for item in trace_list
        if isinstance(item, str) and ":" in item
    ]
    path: List[str] = ["START"]
    if is_resumed and nodes:
        if len(nodes) > 1:
            path.extend(nodes[:-1])
        path.append("Checkpoint断点唤醒")
        path.append(nodes[-1])
    else:
        path.extend(nodes)

    if is_interrupted:
        if path and path[-1] == "order_refund":
            path[-1] = "order_refund (interrupt挂起)"
        else:
            path.append("interrupt挂起")
    else:
        path.append("END")
    return path


class ColorPrinter:
    """
    业务级高亮彩色终端打印助手
    统一收口启动配置、LangGraph 节点与路由执行、Qdrant 检索、DeepSeek 推理、WebSocket 通信日志
    """

    @staticmethod
    def colorize(text: str, color: str) -> str:
        return colorize(text, color)

    def __call__(self, msg: str, color: Optional[str] = None):
        """支持直接调用 cprint("消息", LogColor.GREEN)"""
        color_code = _c(color or LogColor.BRIGHT_WHITE)
        print(f"{color_code}{msg}{_c(LogColor.RESET)}")

    @staticmethod
    def divider(char: str = "═", width: int = 68, color: str = LogColor.BRIGHT_CYAN):
        print(f"{_c(color)}{char * width}{_c(LogColor.RESET)}")

    @staticmethod
    def banner(title: str, subtitle: Optional[str] = None):
        """打印项目启动或核心模块大横幅"""
        border = "═" * 68
        reset = _c(LogColor.RESET)
        print(f"\n{_c(LogColor.BRIGHT_CYAN)}{border}{reset}")
        print(f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_WHITE)}🚀 {title}{reset}")
        if subtitle:
            print(f"{_c(LogColor.DIM)}{subtitle}{reset}")
        print(f"{_c(LogColor.BRIGHT_CYAN)}{border}{reset}\n")

    @staticmethod
    def startup_item(label: str, value: str, value_color: str = LogColor.BRIGHT_WHITE, extra: Optional[str] = None):
        """统一格式打印启动期核心组件配置项"""
        extra_str = f" {extra}" if extra else ""
        print(f"🔹 {label:<18} {colorize(value, value_color)}{extra_str}")

    @staticmethod
    def flow_start(
        session_id: str,
        mode: str,
        user_message: str,
        confirm_action: Optional[str] = None,
        customer_label: Optional[str] = None,
    ):
        """打印单轮对话 LangGraph 工作流开始单行摘要"""
        reset = _c(LogColor.RESET)
        msg_preview = user_message if len(user_message) <= 48 else f"{user_message[:45]}..."
        customer_part = f" {_c(LogColor.WHITE)}{customer_label}{reset}" if customer_label else ""
        action_part = f" {_c(LogColor.BRIGHT_YELLOW)}[{confirm_action}]{reset}" if confirm_action else ""
        print(
            f"\n{_c(LogColor.BRIGHT_CYAN)}━━▶{reset} "
            f"[{_c(LogColor.BRIGHT_YELLOW)}{session_id}{reset}]{customer_part} | "
            f"{_c(LogColor.BRIGHT_MAGENTA)}{mode}{reset}{action_part} | "
            f"\"{_c(LogColor.WHITE)}{msg_preview}{reset}\""
        )

    @staticmethod
    def node(node_name: str, action: str, details: Optional[str] = None):
        """LangGraph 节点执行完成单行日志"""
        reset = _c(LogColor.RESET)
        name = f"{_c(LogColor.BRIGHT_CYAN)}{node_name:<18}{reset}"
        act = f"{_c(LogColor.BRIGHT_WHITE)}{action}{reset}"
        detail_str = f" {_c(LogColor.DIM)}({details}){reset}" if details else ""
        print(f"  {_c(LogColor.BRIGHT_GREEN)}•{reset} {name} {act}{detail_str}")

    @staticmethod
    def node_interrupt(node_name: str, action: str, details: Optional[str] = None):
        """LangGraph 节点触发 interrupt() 挂起单行日志"""
        reset = _c(LogColor.RESET)
        name = f"{_c(LogColor.BRIGHT_CYAN)}{node_name:<18}{reset}"
        act = f"{_c(LogColor.BRIGHT_YELLOW)}{action}{reset}"
        detail_str = f" {_c(LogColor.DIM)}({details}){reset}" if details else ""
        print(f"  {_c(LogColor.BRIGHT_YELLOW)}•{reset} {name} {act}{detail_str}")

    @staticmethod
    def route(from_node: str, to_node: str, reason: Optional[str] = None):
        """LangGraph 条件路由跳转单行日志"""
        reset = _c(LogColor.RESET)
        arrow = (
            f"{_c(LogColor.CYAN)}{from_node}{reset} "
            f"{_c(LogColor.DIM)}──▶{reset} "
            f"{_c(LogColor.BRIGHT_GREEN)}{to_node}{reset}"
        )
        reason_str = f" {_c(LogColor.DIM)}({reason}){reset}" if reason else ""
        print(f"  {_c(LogColor.BRIGHT_BLUE)}🔀{reset} {arrow}{reason_str}")

    @staticmethod
    def detail(msg: str):
        """节点内部子步骤缩进单行日志"""
        reset = _c(LogColor.RESET)
        print(f"    {_c(LogColor.DIM)}│{reset} {_c(LogColor.CYAN)}{msg}{reset}")

    @staticmethod
    def flow_end(
        session_id: str,
        node_path: List[str],
        status: str = "COMPLETED",
        duration_ms: int = 0,
        extra: Optional[str] = None,
    ):
        """打印单轮对话 LangGraph 执行路径单行总结"""
        reset = _c(LogColor.RESET)
        if status == "INTERRUPTED":
            color = _c(LogColor.BRIGHT_YELLOW)
            icon = "•"
        elif status == "ERROR":
            color = _c(LogColor.BRIGHT_RED)
            icon = "❌"
        elif status == "HANDOFF":
            color = _c(LogColor.BRIGHT_MAGENTA)
            icon = "🎧"
        else:
            color = _c(LogColor.BRIGHT_GREEN)
            icon = "🏁"

        path_str = f" {_c(LogColor.DIM)}➔{reset} ".join(
            f"{_c(LogColor.CYAN)}{step}{reset}" for step in node_path
        )
        extra_str = f" | {extra}" if extra else ""
        print(
            f"{color}━━{icon}{reset} [{_c(LogColor.BRIGHT_YELLOW)}{session_id}{reset}] "
            f"{color}{status}{reset} | {_c(LogColor.BRIGHT_WHITE)}{duration_ms}ms{reset}{extra_str} | "
            f"{path_str}\n"
        )

    @classmethod
    def flow_summary(
        cls,
        session_id: str,
        final_state: Dict[str, Any],
        duration_ms: int = 0,
        is_resumed: bool = False,
    ):
        """从状态图最终输出自动提取路径与状态并打印结尾汇总"""
        is_interrupted = bool(final_state.get("__interrupt__"))
        if is_interrupted:
            status = "INTERRUPTED"
            extra = f"订单:{final_state.get('order_id') or '未知'}"
        elif final_state.get("handoff"):
            status = "HANDOFF"
            extra = None
        else:
            status = "COMPLETED"
            extra = None

        node_path = _build_node_path(
            final_state.get("trace") or [],
            is_interrupted=is_interrupted,
            is_resumed=is_resumed,
        )
        cls.flow_end(
            session_id=session_id,
            node_path=node_path,
            status=status,
            duration_ms=duration_ms,
            extra=extra,
        )

    @staticmethod
    def llm(model: str, prompt_len: int, token_latency: float, is_fallback: bool = False):
        """DeepSeek 大模型调用单行日志"""
        reset = _c(LogColor.RESET)
        status = (
            f"{_c(LogColor.YELLOW)}降级模式{reset}"
            if is_fallback
            else f"{_c(LogColor.BRIGHT_GREEN)}正常{reset}"
        )
        print(
            f"    {_c(LogColor.DIM)}│{reset} 🤖 LLM: {_c(LogColor.BRIGHT_CYAN)}{model}{reset} | "
            f"{prompt_len}字 | {token_latency:.2f}s | {status}"
        )

    @staticmethod
    def transfer(session_id: str, agent_id: str, reason: str):
        """人工升级转接单行日志"""
        reset = _c(LogColor.RESET)
        print(
            f"    {_c(LogColor.DIM)}│{reset} {_c(LogColor.BRIGHT_YELLOW)}⚡ 转人工:{reset} "
            f"[{session_id}] ➜ {_c(LogColor.BRIGHT_CYAN)}{agent_id}{reset} "
            f"{_c(LogColor.DIM)}({reason}){reset}"
        )

    @staticmethod
    def websocket(event_type: str, session_id: str, detail: str):
        """WebSocket 实时通信单行日志"""
        reset = _c(LogColor.RESET)
        evt = f"{_c(LogColor.BRIGHT_CYAN)}{event_type}{reset}"
        sess = f"{_c(LogColor.BRIGHT_YELLOW)}{session_id}{reset}"
        print(f"🔌 [WS·{evt}] {sess} ➜ {_c(LogColor.DIM)}{detail}{reset}")

    @staticmethod
    def success(msg: str):
        print(f"{_c(LogColor.BRIGHT_GREEN)}✅ {msg}{_c(LogColor.RESET)}")

    @staticmethod
    def warning(msg: str):
        print(f"{_c(LogColor.BRIGHT_YELLOW)}⚠️  {msg}{_c(LogColor.RESET)}")

    @staticmethod
    def error(msg: str):
        print(f"{_c(LogColor.BRIGHT_RED)}❌ {msg}{_c(LogColor.RESET)}")

    @staticmethod
    def info(msg: str):
        print(f"{_c(LogColor.CYAN)}ℹ️  {msg}{_c(LogColor.RESET)}")


# 便捷导出
log = app_logger
cprint = ColorPrinter()


def trace_node(node_name: str, description: Optional[str] = None) -> Callable:
    """LangGraph 节点执行追踪装饰器（单行输出完成摘要或 interrupt 挂起，零侵入业务代码）"""

    def _log_success(t0: float, result: Any) -> Any:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        cprint.node(node_name, _extract_trace_summary(result, node_name), f"{elapsed_ms}ms")
        return result

    def _log_error(t0: float, exc: BaseException) -> None:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if exc.__class__.__name__ == "GraphInterrupt":
            cprint.node_interrupt(node_name, "触发 interrupt() 挂起等待确认", f"{elapsed_ms}ms")
        else:
            cprint.error(f"[{node_name}] 节点执行异常: {exc!r}")

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                t0 = time.perf_counter()
                try:
                    return _log_success(t0, await fn(*args, **kwargs))
                except BaseException as exc:
                    _log_error(t0, exc)
                    raise

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return _log_success(t0, fn(*args, **kwargs))
            except BaseException as exc:
                _log_error(t0, exc)
                raise

        return sync_wrapper

    return decorator
