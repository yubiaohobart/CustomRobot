# IntelliServe 极简前后端分离部署指南 (3步极速启动)

本项目的前后端完全解耦，前端基于 **React 19 + Vite**，后端提供 **Node.js (Express)** 与 **Python (Flask + LangGraph)** 两套标准实现。

---

## 方案 A：最简单的分步启动（本地/服务器）

### 步骤 1：启动后端（任选其一）

#### 选项 1.1：启动 Node.js 后端（端口 3000）
```bash
# 1. 根目录下安装依赖并配置密钥
npm install
cp .env.example .env

# 2. 单独启动后端服务 (无需前端构建)
npm run dev
```

#### 选项 1.2：启动 Python Flask 后端（端口 5000）
```bash
# 1. 进入 Python 后端目录
cd flask_backend

# 2. 安装依赖并启动
pip install -r requirements.txt
python app.py
```
> Flask 服务将启动在 `http://127.0.0.1:5000`，已默认配置 `flask_cors` 跨域支持。

---

### 步骤 2：启动前端独立服务

如果你在本地开发或单独调试前端：
```bash
# 根目录下运行（Vite 开发热重载服务器）
npm run build
```
若需要将前端请求指向后端端口，通过 Nginx 反代或直接配置反向代理即可。

---

## 方案 B：生产环境标准分离部署（Nginx + 静态前端 + API 后端）

这是企业中最主流、最纯粹的前后端分离架构：
- **前端**：通过 `npm run build` 生成纯静态 html/js/css 文件，直接放在 `/var/www/intelliserve/dist`，由 Nginx 直接极速分发；
- **后端**：使用 PM2 或 Systemd 运行 Node.js 或 Python Flask，仅处理 `/api/` 路由。

### 1. 前端打包与放置
```bash
# 1. 在本地或 CI/CD 构建前端静态资源
npm run build

# 2. 将 dist 文件夹上传至服务器目录，例如：
# /var/www/intelliserve/dist
```

### 2. 后端常驻后台
```bash
# Node.js 后端启动（生产环境常驻）：
npm install -g pm2
pm2 start dist/server.cjs --name "intelliserve-api"

# 或 Python Flask 后端启动（生产环境常驻）：
cd flask_backend
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 app:app --daemon
```

### 3. Nginx 极简分离配置文件（直接复制即可用）
在 `/etc/nginx/conf.d/intelliserve.conf` 中填入：

```nginx
server {
    listen 80;
    server_name cs.yourdomain.com; # 你的服务器IP或域名

    # 1. 前端静态页面托管（极快，不经过后端）
    location / {
        root /var/www/intelliserve/dist;
        index index.html;
        try_files $uri $uri/ /index.html; # 支持单页应用刷新路由
    }

    # 2. 后端接口反向代理
    location /api/ {
        # 如果用 Node.js 后端，代理到 3000：
        proxy_pass http://127.0.0.1:3000;
        
        # 如果用 Python Flask 后端，代理到 5000：
        # proxy_pass http://127.0.0.1:5000;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

测试并重载 Nginx：
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 方案 C：Docker Compose 双容器前后端分离部署

使用独立的两个容器，分别承载前端 Web 服务器与后端 API。

运行根目录下的独立脚本即可：
```bash
# 1. 一键启动前后端独立容器
docker compose -f docker-compose.separated.yml up -d --build
```
此时：
- 前端 Nginx 容器运行在 `http://localhost:80` (或指定端口)
- 后端 API 容器独立运行，互不干扰
