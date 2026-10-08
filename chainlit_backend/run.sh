#!/usr/bin/env bash
# ==============================================================================
# IntelliServe Chainlit 一键启动脚本
# ==============================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🚀 启动 IntelliServe Chainlit 对话与自测平台..."
echo "📁 工作目录: $DIR"
echo "🌐 访问地址: http://localhost:8000"
echo "=========================================================="

if ! command -v chainlit &> /dev/null; then
    echo "⚠️ 未找到 chainlit 命令，正在自动安装所需依赖..."
    pip install -r requirements.txt
fi

chainlit run app.py -w --port 8000
