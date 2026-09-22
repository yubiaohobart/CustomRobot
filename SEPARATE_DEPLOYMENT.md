# IntelliServe 极简前后端分离部署指南 (3步极速启动)

本项目的前后端完全解耦：
- **前端**：基于 **React 19 + TypeScript + Vite + Tailwind CSS**，编译后为纯静态 HTML/CSS/JS 资源。
- **后端**：基于 **Python FastAPI + LangGraph 异步状态图引擎**，默认监听 5000 端口，原生提供 Swagger 交互文档与 CORS 跨域支持。

---

## 方案 A：本地 / 开发环境分步极速启动

### 步骤 1：启动 Python FastAPI 核心后端 (端口 5000)

```bash
# 1. 进入 Python 后端代码目录
cd fastapi_backend

# 2. 安装 Python 依赖并启动
pip install -r requirements.txt
python app.py
```
> 控制台输出：
> `FastAPI + LangGraph Intelligent Customer Service Server starting on port 5000...`  
> `Interactive Swagger Docs available at: http://127.0.0.1:5000/docs`  
> 服务自带 CORS 全开，支持任何来源的前端跨域调用。

---

### 步骤 2：启动前端界面 (自动直连 5000 端口)

保持上述 Python 终端运行，在项目根目录新开一个终端：

```bash
npm run dev:frontend
```
> 控制台输出：`http://localhost:5173/`  
> Vite 开发服务器内部已预设代理 `/api` -> `http://127.0.0.1:5000`。  
> 此时直接在浏览器打开 `http://localhost:5173` 即可立即与你的 FastAPI 后端对话！

---

## 方案 B：生产环境纯粹分离架构（Nginx 静态托管 + FastAPI 独立后端）

这是企业中最主流、最高性能的部署架构：
- **前端**：通过 `npm run build` 生成纯静态文件，由 Nginx 直接极速分发；
- **后端**：使用 Systemd、Supervisor 或 PM2 运行 FastAPI + Uvicorn，仅处理 `/api/` 路由。

### 1. 前端打包与放置
```bash
# 1. 本地或 CI/CD 构建前端静态资源
npm run build

# 2. 将编译生成的 dist 文件夹上传至服务器目录，例如：
# /var/www/intelliserve/dist
```

### 2. 后端常驻后台 (推荐使用 Uvicorn 或 PM2)
```bash
cd /var/www/intelliserve/fastapi_backend
source venv/bin/activate
pip install -r requirements.txt

# 方式 1：使用 Uvicorn 多进程生产运行
uvicorn app:app --host 127.0.0.1 --port 5000 --workers 4

# 方式 2：使用 PM2 守护常驻
pm2 start "uvicorn app:app --host 127.0.0.1 --port 5000 --workers 4" --name "intelliserve-fastapi"
pm2 save
```

### 3. Nginx 极简分离配置文件（直接复制即可用）
在 `/etc/nginx/conf.d/intelliserve.conf` 中填入：

```nginx
server {
    listen 80;
    server_name cs.yourdomain.com; # 你的服务器IP或域名

    # 1. 前端静态页面托管（零后端消耗，极速加载）
    location / {
        root /var/www/intelliserve/dist;
        index index.html;
        try_files $uri $uri/ /index.html; # 支持单页应用前端路由刷新
    }

    # 静态资产长效缓存
    location /assets/ {
        root /var/www/intelliserve/dist;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # 2. 后端接口反向代理至 FastAPI (端口 5000)
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # AI 对话与大模型推理超时放宽
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # 3. 暴露 FastAPI 的交互式 Swagger 文档（可选）
    location /docs {
        proxy_pass http://127.0.0.1:5000/docs;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:5000/openapi.json;
    }
}
```

测试并重载 Nginx：
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 方案 C：Docker 双容器分离部署

若使用 Docker 分别打包前后端：
- 前端容器：Nginx 镜像打包 `dist/`，监听 80 端口；
- 后端容器：Python 镜像执行 `Dockerfile.fastapi`，监听 5000 端口。
两个容器互不影响，后端升级无需中断前端静态页面访问。
