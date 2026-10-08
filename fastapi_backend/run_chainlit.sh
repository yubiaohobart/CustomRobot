#!/usr/bin/env bash
# 一键启动 IntelliServe Chainlit 对话自测平台
# 包含自动配置修复：启动前自动清除过期的旧版 config.toml，彻底防止 "config file is outdated" 报错
set -e
cd "$(dirname "$0")"

# 自动清理旧版或版本冲突的 .chainlit 配置文件（Chainlit 启动时会自动重新生成匹配当前版本的配置）
if [ -f ".chainlit/config.toml" ]; then
    echo "🧹 自动清理旧版本 .chainlit/config.toml（Chainlit 将自动生成适配当前版本的配置）..."
    rm -rf .chainlit
fi

echo "=================================================="
echo "🚀 启动 IntelliServe Chainlit 对话自测客户端"
echo "👉 后端 API 地址: http://127.0.0.1:8000 (已规避 macOS 5000 端口 AirPlay 冲突)"
echo "👉 自测 UI 地址:  http://localhost:8001"
echo "=================================================="

# 优先调用当前 Python 环境的 chainlit 模块，确保使用激活的虚拟环境
if command -v python &> /dev/null && python -m chainlit --help &> /dev/null; then
    python -m chainlit run chainlit_app.py -w --port 8001
elif command -v python3 &> /dev/null && python3 -m chainlit --help &> /dev/null; then
    python3 -m chainlit run chainlit_app.py -w --port 8001
else
    chainlit run chainlit_app.py -w --port 8001
fi
