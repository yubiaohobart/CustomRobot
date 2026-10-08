#!/usr/bin/env bash
# 一键启动 IntelliServe Chainlit 对话自测平台
set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "🚀 启动 IntelliServe Chainlit 对话自测客户端"
echo "👉 后端 API 地址: http://127.0.0.1:8000"
echo "👉 自测 UI 地址:  http://localhost:8001"
echo "=================================================="

chainlit run chainlit_app.py -w --port 8001
