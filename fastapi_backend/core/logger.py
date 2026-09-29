"""
彩色终端日志工具模块 (Color Logger Module)
提供开箱即用、工业级、支持 ANSI 绚丽色彩的终端日志工具
无需第三方复杂库，基于 Python 标准库 logging 封装，支持多级别彩色输出与业务标签高亮
"""

import sys
import logging
from datetime import datetime
from typing import Optional

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


class ColoredFormatter(logging.Formatter):
    """自定义带颜色的格式化器"""

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
        # 获取颜色与图标
        color = self.LEVEL_COLORS.get(record.levelno, LogColor.WHITE)
        icon = self.LEVEL_ICONS.get(record.levelno, f"[{record.levelname}]")
        reset = LogColor.RESET

        # 格式化时间戳
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        time_str = f"{LogColor.DIM}{timestamp}{reset}"

        # 模块名称高亮 (青色)
        module_name = f"{LogColor.CYAN}{record.name}{reset}"

        # 获取消息内容
        message = record.getMessage()

        # 组装完整彩色日志行
        # 格式: 2026-09-29 10:15:30.123 ✨ [INFO ] (module) 消息内容
        return f"{time_str} {color}{icon}{reset} {LogColor.DIM}({module_name}){reset} {color}{message}{reset}"


def setup_logger(name: str = "IntelliServe", level: int = logging.INFO) -> logging.Logger:
    """初始化并返回全局标准彩色 Logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复挂载 handler
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

    @staticmethod
    def banner(title: str, subtitle: Optional[str] = None):
        """打印项目启动或核心模块大横幅 (霓虹紫蓝渐变感)"""
        border = "═" * 68
        print(f"\n{LogColor.BRIGHT_CYAN}{border}{LogColor.RESET}")
        print(f"{LogColor.BOLD}{LogColor.BRIGHT_WHITE}🚀 {title}{LogColor.RESET}")
        if subtitle:
            print(f"{LogColor.DIM}{subtitle}{LogColor.RESET}")
        print(f"{LogColor.BRIGHT_CYAN}{border}{LogColor.RESET}\n")

    @staticmethod
    def node(node_name: str, action: str, details: Optional[str] = None):
        """LangGraph 节点流转日志 (高亮青色/紫罗兰色)"""
        tag = f"{LogColor.BOLD}{LogColor.BRIGHT_MAGENTA}┠─ [LangGraph 节点]{LogColor.RESET}"
        name = f"{LogColor.BRIGHT_CYAN}{node_name:<20}{LogColor.RESET}"
        act = f"{LogColor.BRIGHT_WHITE}{action}{LogColor.RESET}"
        print(f"{tag} {name} ➜ {act}")
        if details:
            print(f"   {LogColor.DIM}↳ 详情: {details}{LogColor.RESET}")

    @staticmethod
    def rag(query: str, hits: int, top_score: float, matched_title: Optional[str] = None):
        """Qdrant 向量召回日志 (高亮绿色/翠绿)"""
        tag = f"{LogColor.BOLD}{LogColor.BRIGHT_GREEN}🔍 [Qdrant 检索]{LogColor.RESET}"
        score_color = LogColor.BRIGHT_GREEN if top_score >= 0.70 else LogColor.BRIGHT_YELLOW
        print(f"{tag} 查询: \"{LogColor.WHITE}{query}{LogColor.RESET}\"")
        print(f"   {LogColor.DIM}↳ 命中文档数: {hits} 条 | Top 相似度: {score_color}{top_score:.3f}{LogColor.RESET} | 最佳匹配: {LogColor.CYAN}{matched_title or 'N/A'}{LogColor.RESET}")

    @staticmethod
    def llm(model: str, prompt_len: int, token_latency: float, is_fallback: bool = False):
        """DeepSeek 大模型调用日志 (蓝色 / 琥珀色)"""
        if is_fallback:
            tag = f"{LogColor.BOLD}{LogColor.BRIGHT_YELLOW}🤖 [DeepSeek 降级模式]{LogColor.RESET}"
            status = f"{LogColor.YELLOW}规则引擎严谨保障响应{LogColor.RESET}"
        else:
            tag = f"{LogColor.BOLD}{LogColor.BRIGHT_BLUE}🤖 [DeepSeek 推理]{LogColor.RESET}"
            status = f"{LogColor.BRIGHT_GREEN}API 响应正常{LogColor.RESET}"

        print(f"{tag} 模型: {LogColor.BRIGHT_CYAN}{model}{LogColor.RESET} | 耗时: {token_latency:.2f}s | 状态: {status}")

    @staticmethod
    def transfer(session_id: str, agent_id: str, reason: str):
        """人工升级转接日志 (高亮橘黄/警戒红)"""
        tag = f"{LogColor.BOLD}{LogColor.BG_YELLOW}{LogColor.BLACK} ⚡ 转接人工坐席 {LogColor.RESET}"
        print(f"{tag} 会话ID: {LogColor.BRIGHT_WHITE}{session_id}{LogColor.RESET} ➜ 指派坐席: {LogColor.BRIGHT_CYAN}{agent_id}{LogColor.RESET}")
        print(f"   {LogColor.BRIGHT_YELLOW}↳ 触发原因: {reason}{LogColor.RESET}")

    @staticmethod
    def success(msg: str):
        """成功日志 (翠绿色)"""
        print(f"{LogColor.BRIGHT_GREEN}✅ {msg}{LogColor.RESET}")

    @staticmethod
    def warning(msg: str):
        """警告日志 (金黄色)"""
        print(f"{LogColor.BRIGHT_YELLOW}⚠️  {msg}{LogColor.RESET}")

    @staticmethod
    def error(msg: str):
        """错误日志 (亮红色)"""
        print(f"{LogColor.BRIGHT_RED}❌ {msg}{LogColor.RESET}")

    @staticmethod
    def info(msg: str):
        """普通信息日志 (青白色)"""
        print(f"{LogColor.CYAN}ℹ️  {msg}{LogColor.RESET}")


# 便捷导出
log = app_logger
cprint = ColorPrinter
