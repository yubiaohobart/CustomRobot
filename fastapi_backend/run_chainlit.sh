#!/usr/bin/env bash
# IntelliServe Chainlit 对话自测启动脚本
set -e
cd "$(dirname "$0")"

echo "🚀 启动 IntelliServe Chainlit 对话自测平台 (http://localhost:8000)..."
chainlit run chainlit_app.py -w --port 8000
