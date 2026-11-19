"""
彩色终端日志工具模块 (Color Logger Module)
提供开箱即用、工业级、支持 ANSI 绚丽色彩的终端日志工具
无需第三方复杂库，基于 Python 标准库 logging 封装，支持多级别彩色输出与业务标签高亮
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional

_ANSI_DISABLED = bool(os.getenv("NO_COLOR"))


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


class ColorPrinter:
    """
    业务级高亮彩色终端打印助手
    用于 LangGraph 状态图执行、Qdrant 向量检索、人机协同转接等关键节点的视觉沉浸式展示
    """

    def __call__(self, msg: str, color: Optional[str] = None):
        """支持直接调用 cprint("消息", LogColor.GREEN)"""
        color_code = _c(color or LogColor.BRIGHT_WHITE)
        print(f"{color_code}{msg}{_c(LogColor.RESET)}")

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
    def node(node_name: str, action: str, details: Optional[str] = None):
        """LangGraph 节点流转日志"""
        reset = _c(LogColor.RESET)
        tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_MAGENTA)}┠─ [LangGraph 节点]{reset}"
        name = f"{_c(LogColor.BRIGHT_CYAN)}{node_name:<20}{reset}"
        act = f"{_c(LogColor.BRIGHT_WHITE)}{action}{reset}"
        print(f"{tag} {name} ➜ {act}")
        if details:
            print(f"   {_c(LogColor.DIM)}↳ 详情: {details}{reset}")

    @staticmethod
    def rag(query: str, hits: int, top_score: float, matched_title: Optional[str] = None):
        """Qdrant 向量召回日志"""
        reset = _c(LogColor.RESET)
        tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_GREEN)}🔍 [Qdrant 检索]{reset}"
        score_color = _c(LogColor.BRIGHT_GREEN if top_score >= 0.70 else LogColor.BRIGHT_YELLOW)
        print(f"{tag} 查询: \"{_c(LogColor.WHITE)}{query}{reset}\"")
        print(
            f"   {_c(LogColor.DIM)}↳ 命中文档数: {hits} 条 | Top 相似度: {score_color}{top_score:.3f}{reset} "
            f"| 最佳匹配: {_c(LogColor.CYAN)}{matched_title or 'N/A'}{reset}"
        )

    @staticmethod
    def llm(model: str, prompt_len: int, token_latency: float, is_fallback: bool = False):
        """DeepSeek 大模型调用日志"""
        reset = _c(LogColor.RESET)
        if is_fallback:
            tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_YELLOW)}🤖 [DeepSeek 降级模式]{reset}"
            status = f"{_c(LogColor.YELLOW)}规则引擎严谨保障响应{reset}"
        else:
            tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_BLUE)}🤖 [DeepSeek 推理]{reset}"
            status = f"{_c(LogColor.BRIGHT_GREEN)}API 响应正常{reset}"

        print(
            f"{tag} 模型: {_c(LogColor.BRIGHT_CYAN)}{model}{reset} "
            f"| Prompt: {prompt_len} 字符 | 耗时: {token_latency:.2f}s | 状态: {status}"
        )

    @staticmethod
    def transfer(session_id: str, agent_id: str, reason: str):
        """人工升级转接日志"""
        reset = _c(LogColor.RESET)
        tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BG_YELLOW)}{_c(LogColor.BLACK)} ⚡ 转接人工坐席 {reset}"
        print(
            f"{tag} 会话ID: {_c(LogColor.BRIGHT_WHITE)}{session_id}{reset} "
            f"➜ 指派坐席: {_c(LogColor.BRIGHT_CYAN)}{agent_id}{reset}"
        )
        print(f"   {_c(LogColor.BRIGHT_YELLOW)}↳ 触发原因: {reason}{reset}")

    @staticmethod
    def websocket(event_type: str, session_id: str, detail: str):
        """WebSocket 实时通信全双工日志"""
        reset = _c(LogColor.RESET)
        tag = f"{_c(LogColor.BOLD)}{_c(LogColor.BG_BLUE)}{_c(LogColor.BRIGHT_WHITE)} 🔌 [WebSocket] {reset}"
        evt = f"{_c(LogColor.BRIGHT_CYAN)}{event_type}{reset}"
        sess = f"{_c(LogColor.BOLD)}{_c(LogColor.BRIGHT_YELLOW)}{session_id}{reset}"
        print(f"{tag} [{evt}] 会话: {sess} ➜ {_c(LogColor.BRIGHT_GREEN)}{detail}{reset}")

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
