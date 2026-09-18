# IntelliServe 智能客服系统环境部署与上线指南

本系统提供两种标准的部署形态：
1. **形态 A（推荐·最简便）：Node.js 全栈一体化部署** —— 单端口托管 React 19 前端静态资源与 Express API 服务，适合中小型企业、快速容器化上线（Docker / Cloud Run / 云服务器）。
2. **形态 B：前后端分离部署（Python Flask + React）** —— Python 3.10+ 独立运行 LangGraph 与 Flask API，前端构建后由 Nginx 托管并反向代理。

---

## 目录
- [一、准备工作与环境依赖](#一准备工作与环境依赖)
- [二、方案一：Node.js 全栈一体化部署（最快）](#二方案一nodejs-全栈一体化部署最快)
  - [1. 本地或云服务器直接运行](#1-本地或云服务器直接运行)
  - [2. 使用 PM2 进程守护常驻](#2-使用-pm2-进程守护常驻)
- [三、方案二：Docker 容器化一键部署](#三方案二docker-容器化一键部署)
- [四、方案三：Python Flask + LangGraph 后端独立部署](#四方案三python-flask--langgraph-后端独立部署)
- [五、生产环境 Nginx 反向代理配置与 HTTPS](#五生产环境-nginx-反向代理配置与-https)
- [六、环境变量配置说明](#六环境变量配置说明)

---

## 一、准备工作与环境依赖

| 组件 | 最低要求 | 推荐版本 |
| :--- | :--- | :--- |
| **Node.js** | 18.0.0+ | 20.x LTS |
| **npm** | 9.0.0+ | 10.x |
| **Python**（若运行 Flask） | 3.10+ | 3.11+ |
| **Docker**（若容器部署） | 20.10+ | 最新版 |
| **操作系统** | Linux (Ubuntu/Debian/CentOS), macOS, Windows | Linux (Ubuntu 22.04 LTS) |

---

## 二、方案一：Node.js 全栈一体化部署（最快）

该方案将 React 前端与 Express 后端打包为单个服务，启动后即可访问完整客服与坐席工作台。

### 1. 本地或云服务器直接运行

```bash
# 1. 检出代码或解压源码包
cd intelliserve-customer-service

# 2. 安装项目依赖
npm install

# 3. 配置环境变量 (复制模板)
cp .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY 等必要参数

# 4. 执行生产环境打包编译 (构建 Vite 前端并使用 esbuild 打包后端到 dist/server.cjs)
npm run build

# 5. 启动生产服务
npm start
```
此时服务将监听 `http://0.0.0.0:3000`，在浏览器打开即可正常访问。

### 2. 使用 PM2 进程守护常驻（生产推荐）

在云服务器（如阿里云、腾讯云、AWS）上部署时，建议使用 PM2 保证进程崩溃自动重启与开机自启：

```bash
# 全局安装 PM2
npm install -g pm2

# 启动并命名为 intelliserve
pm2 start dist/server.cjs --name "intelliserve" --env NODE_ENV=production

# 查看服务状态与日志
pm2 status
pm2 logs intelliserve

# 保存当前进程列表并配置开机自启
pm2 save
pm2 startup
```

---

## 三、方案二：Docker 容器化一键部署

项目根目录已内置多阶段构建的 `Dockerfile` 与 `docker-compose.yml`。

### 1. 使用 Docker Compose 一键启动

```bash
# 1. 启动容器 (后台运行)
docker compose up -d --build

# 2. 查看容器运行状态
docker compose ps

# 3. 查看实时日志
docker compose logs -f

# 4. 停止服务
docker compose down
```

### 2. 单独构建与运行 Docker 镜像

```bash
# 构建镜像
docker build -t intelliserve:latest .

# 运行容器
docker run -d \
  --name intelliserve \
  -p 3000:3000 \
  -e NODE_ENV=production \
  -e GEMINI_API_KEY="your_api_key_here" \
  --restart always \
  intelliserve:latest
```

---

## 四、方案三：Python Flask + LangGraph 后端独立部署

若需要纯 Python 生态（运行原始 LangChain/LangGraph/ChromaDB），按以下步骤部署：

### 1. 部署 Python 后端

```bash
cd flask_backend

# 创建并激活 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install gunicorn  # 生产环境 WSGI 推荐

# 启动生产服务 (4个 Worker，监听 5000 端口)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 2. 编译前端并关联后端

```bash
# 回到项目根目录
cd ..

# 构建前端产物
npm run build
# 产物将输出在 dist 目录，可直接由 Nginx 托管
```

---

## 五、生产环境 Nginx 反向代理配置与 HTTPS

生产环境中推荐使用 Nginx 作为 Web 服务器与反向代理，同时配置 SSL 证书：

```nginx
# /etc/nginx/conf.d/intelliserve.conf

upstream intelliserve_backend {
    server 127.0.0.1:3000;  # 指向 Node 全栈服务 (或 Flask 服务的 5000)
    keepalive 32;
}

server {
    listen 80;
    server_name cs.yourdomain.com;
    
    # 强制跳转 HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name cs.yourdomain.com;

    # SSL 证书配置
    ssl_certificate /etc/letsencrypt/live/cs.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cs.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 静态文件缓存加速
    location /assets/ {
        proxy_pass http://intelliserve_backend;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # API 与页面代理
    location / {
        proxy_pass http://intelliserve_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时时间调整
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

测试并重启 Nginx：
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 六、环境变量配置说明

在项目根目录新建 `.env` 文件：

```env
# 端口设置 (默认 3000)
PORT=3000

# 运行环境
NODE_ENV=production

# Gemini 大模型 API Key（用于智能问答与客服回复生成）
GEMINI_API_KEY=AIzaSy...

# Flask 独立部署时可选：
FLASK_PORT=5000
```
