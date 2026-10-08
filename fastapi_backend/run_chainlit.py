#!/usr/bin/env python3
"""
IntelliServe Chainlit 对话自测启动入口 (带配置自愈修复)
自动检测并清除旧版或冲突的 .chainlit/config.toml，彻底防止 "is outdated" 报错
"""

import os
import sys
import shutil
import subprocess

def auto_heal_config():
    """检查并清理旧版本 config.toml，交由当前版本的 Chainlit 自动重新生成"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    chainlit_dir = os.path.join(current_dir, ".chainlit")
    config_file = os.path.join(chainlit_dir, "config.toml")
    
    if os.path.exists(config_file):
        try:
            print("🧹 检测到本地 .chainlit/config.toml，正在自动重置为当前 Chainlit 版本匹配的配置...")
            shutil.rmtree(chainlit_dir, ignore_errors=True)
        except Exception as e:
            print(f"⚠️ 清理配置文件警告: {e}")

def main():
    auto_heal_config()

    # 禁用系统代理干扰 localhost
    os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"
    os.environ["no_proxy"] = "127.0.0.1,localhost,0.0.0.0"
    for proxy_key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"]:
        os.environ.pop(proxy_key, None)
    
    try:
        from config import settings
        backend_port = settings.FASTAPI_PORT if settings.FASTAPI_PORT != 5000 else 8000
    except Exception:
        backend_port = 8000

    print("==================================================")
    print("🚀 启动 IntelliServe Chainlit 对话自测客户端")
    print(f"👉 后端 API 地址: http://127.0.0.1:{backend_port} (默认 8000，避开 macOS 5000 AirPlay 冲突)")
    print("👉 自测 UI 地址:  http://localhost:8001")
    print("==================================================")
    
    cmd = [sys.executable, "-m", "chainlit", "run", "chainlit_app.py", "-w", "--port", "8001"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Chainlit 服务已安全退出")

if __name__ == "__main__":
    main()
