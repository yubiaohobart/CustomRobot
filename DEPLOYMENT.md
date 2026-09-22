# IntelliServe 智能客服系统生产环境部署与上线指南

本系统提供两种标准的部署形态：
1. **形态 A：Python FastAPI + LangGraph 后端独立部署（官方核心标准）** —— 基于 Python 3.10+、FastAPI 异步架构与 Uvicorn ASGI 高性能服务器运行，支持原生 Swagger 交互文档，前端打包为纯静态资源由 Nginx 极速分发。
2. **形态 B：一体化容器 / 反向代理宿主部署** —— 使用轻量宿主服务一并托管前端界面并将 API 流量代理至 FastAPI 后端，适合容器化快速交付（Docker / Kubernetes / Cloud Run）。

---

## 目录
- [一、准备工作与环境依赖](#一准备工作与环境依赖)
- [二、方案一：Python FastAPI 核心后端生产部署 (Uvicorn / Systemd / PM2)](#二方案一python-fastapi-核心后端生产部署-uvicorn--systemd--pm2)
  - [1. 安装环境与依赖](#1-安装环境与依赖)
  - [2. 使用 Uvicorn 生产启动](#2-使用-uvicorn-生产启动)
  - [3. 使用 Systemd 守护进程常驻](#3-使用-systemd-守护进程常驻)
  - [4. 使用 PM2 运行 Python 后端](#4-使用-pm2-运行-python-后端)
- [三、方案二：前端静态构建与 Nginx 反向代理配置](#三方案二前端静态构建与-nginx-反向代理配置)
- [四、方案三：Docker 容器化一键部署](#四方案三docker-容器化一键部署)
- [五、环境变量配置清单](#五环境变量配置清单)
- [六、健康检查与 Swagger 在线调试](#六健康检查与-swagger-在线调试)

---

## 一、准备工作与环境依赖

| 组件 | 最低要求 | 推荐版本 | 说明 |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10+ | 3.11+ | 用于运行 FastAPI + LangGraph 后端 |
| **Node.js** | 18.0.0+ | 20.x LTS | 仅用于前端静态构建 (`npm run build`) |
| **Uvicorn** | 0.28.0+ | 最新版 | 异步 ASGI 高性能应用服务器 |
| **Nginx** | 1.18+ | 1.24+ | 托管前端静态资源与反向代理 API |
| **Docker** (可选) | 20.10+ | 最新版 | 容器化部署 |

---

## 二、方案一：Python FastAPI 核心后端生产部署 (Uvicorn / Systemd / PM2)

### 1. 安装环境与依赖

```bash
cd fastapi_backend

# 建议创建并激活 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\activate  # Windows

# 安装核心依赖包 (包含 fastapi, uvicorn[standard], langgraph 等)
pip install -r requirements.txt
```

### 2. 使用 Uvicorn 生产启动

```bash
# 启动多进程生产服务 (4个 Worker 进程，监听 5000 端口)
uvicorn app:app --host 0.0.0.0 --port 5000 --workers 4 --access-log
```

若喜欢使用 Gunicorn 作为进程管理器：
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5000 app:app
```

### 3. 使用 Systemd 守护进程常驻 (Linux 生产推荐)

在 `/etc/systemd/system/intelliserve-backend.service` 创建服务单元文件：

```ini
[Unit]
Description=IntelliServe FastAPI Customer Service Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/intelliserve/fastapi_backend
Environment="PATH=/var/www/intelliserve/fastapi_backend/venv/bin"
Environment="FASTAPI_PORT=5000"
Environment="DEEPSEEK_API_KEY=your_deepseek_api_key_here"
ExecStart=/var/www/intelliserve/fastapi_backend/venv/bin/uvicorn app:app --host 0.0.0.0 --port 5000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动并设置开机自启：
```bash
sudo systemctl daemon-reload
sudo systemctl start intelliserve-backend
sudo systemctl enable intelliserve-backend
sudo systemctl status intelliserve-backend
```

### 4. 使用 PM2 运行 Python 后端

如果你服务器上已装有 PM2：
```bash
cd fastapi_backend
pm2 start "python app.py" --name "intelliserve-api"
# 或指定 uvicorn 路径：
# pm2 start "uvicorn app:app --host 0.0.0.0 --port 5000 --workers 4" --name "intelliserve-api"
pm2 save
pm2 startup
```

---

## 三、方案二：前端静态构建与 Nginx 反向代理配置

### 1. 构建前端静态资源

在本地开发机或 CI/CD 构建机执行：
```bash
# 回到项目根目录
cd ..
npm install
npm run build
```
编译产物将生成在 `dist/` 文件夹内（纯 HTML、CSS、JS 静态资源，零 Node.js 运行时依赖）。将 `dist/` 上传至服务器如 `/var/www/intelliserve/dist`。

### 2. Nginx 配置 (`/etc/nginx/conf.d/intelliserve.conf`)

```nginx
upstream fastapi_backend {
    server 127.0.0.1:5000;
    keepalive 64;
}

server {
    listen 80;
    server_name cs.yourdomain.com;

    # 1. 托管前端单页应用静态文件
    location / {
        root /var/www/intelliserve/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 静态资产长缓存
    location /assets/ {
        root /var/www/intelliserve/dist;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # 2. 将所有 /api/ 请求反向代理给 Python FastAPI 后端
    location /api/ {
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 调高大模型推理响应超时限制
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # 3. （可选）暴露 FastAPI 内置 Swagger 文档供内部调试
    location ~ ^/(docs|redoc|openapi.json) {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

测试并重载 Nginx：
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 四、方案三：Docker 容器化一键部署

### 1. 构建与运行 FastAPI 后端容器

```bash
cd fastapi_backend

# 构建镜像
docker build -f Dockerfile.fastapi -t intelliserve-api:latest .

# 启动容器
docker run -d \
  --name intelliserve-api \
  -p 5000:5000 \
  -e FASTAPI_PORT=5000 \
  -e GEMINI_API_KEY="your_api_key" \
  --restart always \
  intelliserve-api:latest
```

### 2. 构建与运行完整宿主容器

```bash
# 在项目根目录下
docker build -t intelliserve-all:latest .
docker run -d -p 3000:3000 --name intelliserve-all intelliserve-all:latest
```

---

## 五、环境变量配置清单

可在 `.env` 文件或容器环境中注入以下变量：

| 变量名 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `FASTAPI_PORT` | `5000` | Python FastAPI 后端监听端口 |
| `DEEPSEEK_API_KEY` | - | DeepSeek 大模型 API Key（用于问答与 Copilot 坐席辅助） |
| `QDRANT_LOCATION` | `:memory:` | Qdrant 运行模式：纯内存模式，**无需使用 Docker 部署独立容器** |
| `BACKEND_URL` | `http://127.0.0.1:5000` | 前端开发服务器反代目标后端地址 |
| `PORT` | `3000` | 前端宿主托管服务端口 |
| `NODE_ENV` | `production` | 生产环境标识 |

---

## 六、健康检查与 Swagger 在线调试

启动成功后，可通过以下接口验证服务状态：

1. **健康检查接口**：
   ```bash
   curl http://localhost:5000/api/health
   ```
   响应示例：
   ```json
   {
     "status": "healthy",
     "service": "IntelliServe FastAPI + LangGraph Engine",
     "framework": "FastAPI",
     "version": "2.0.0"
   }
   ```

2. **交互式 OpenAPI (Swagger) UI**：
   在浏览器访问：
   - Swagger 界面：`http://your-server-ip:5000/docs`
   - ReDoc 界面：`http://your-server-ip:5000/redoc`
   可以直接在线测试消息发送、知识库检索、人工转接和指标获取等所有接口。
