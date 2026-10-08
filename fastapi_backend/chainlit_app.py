"""
IntelliServe 智能客服 Chainlit 兼容转发入口 (Compatibility Wrapper)

说明:
    Chainlit 相关的独立后端代码已按照架构规范统一收拢至独立目录：
    👉 /chainlit_backend/app.py

建议运行方式:
    cd chainlit_backend
    chainlit run app.py -w --port 8000
"""

import os
import sys

# 定位统一的 chainlit_backend 目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CHAINLIT_BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "chainlit_backend"))

if CHAINLIT_BACKEND_DIR not in sys.path:
    sys.path.insert(0, CHAINLIT_BACKEND_DIR)

# 导入 chainlit_backend/app.py 中的全部定义与钩子
try:
    from app import *  # noqa: F401, F403
except Exception as err:
    print(f"[*] 正在从 {CHAINLIT_BACKEND_DIR} 加载 Chainlit 模块: {err}")
