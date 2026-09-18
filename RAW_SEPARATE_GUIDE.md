# IntelliServe 极简前后端独立运行与部署（无 Docker、无 Nginx）

如果你的环境**没有安装 Docker，也没有配置 Nginx**，只需两台机器（或者一台机器开两个终端端口），即可最纯粹地跑起独立的前端和后端服务。

---

## 总体架构与端口规划

```
[ 用户浏览器 ] 
      │
      ├──> 页面访问: http://IP:5173 (前端开发或预览服务)
      │
      └──> API 请求: http://IP:3000 (或 5000) 自动代理与跨域通信
```

---

## 模式一：本地 / 开发环境分开启动（最直观）

### 终端 1：单独启动后端 API 服务
在项目根目录（或任意终端窗口）执行：
```bash
# 1. 配置环境变量（确保 GEMINI_API_KEY 配置妥当）
cp .env.example .env

# 2. 启动后端 API（监听 3000 端口）
npm run dev:backend
```
> 控制台输出：`[IntelliServe] Server running on http://0.0.0.0:3000`  
> 后端已默认开启全域 CORS 跨域支持，任何前端端口均可直连。

---

### 终端 2：单独启动前端服务
打开新的终端窗口，执行：
```bash
# 启动 Vite 前端开发服务器（监听 5173 端口）
npm run dev:frontend
```
> 控制台输出：`http://localhost:5173/`  
> 此时直接在浏览器打开 `http://localhost:5173`。  
> Vite 内部已预置 `/api` 自动代理，会自动把所有客服请求转到后端的 3000 端口，开箱即用！

---

## 模式二：生产服务器裸机分离部署（后台常驻运行）

在云服务器（Linux/Windows/macOS）上，若想不用 Nginx，也可以直接使用轻量进程工具（如 **PM2** 或自带的后台命令 `nohup`）：

### 1. 构建前端与后端
```bash
# 构建前端静态文件到 dist 目录
npm run build:frontend

# 打包后端自包含单文件到 dist/server.cjs
npm run build:backend
```

### 2. 启动后端 API（端口 3000）
```bash
# 安装 PM2 进程守护工具（保证崩溃自动重启）
npm install -g pm2

# 启动后端
pm2 start dist/server.cjs --name "cs-backend"
```

### 3. 启动前端服务（无需 Nginx，使用 serve 或 vite preview）
只需用 Node 自带的静态服务器工具或者 vite 即可分发前端页面：
```bash
# 方式 A：使用 vite preview（监听 4173 或自定义端口）
pm2 start "npm run preview -- --port 80 --host 0.0.0.0" --name "cs-frontend"

# 方式 B：使用超轻量静态服务器 serve (推荐)
npm install -g serve
pm2 start "serve -s dist -l 80" --name "cs-frontend"
```

查看两个独立进程：
```bash
pm2 list
```
输出显示：
- `cs-backend` (端口 3000)
- `cs-frontend` (端口 80)

两个进程互不依赖，升级前端只需重新构建 `dist`，重启 `cs-frontend`，完全不需要动后端！

---

## 模式三：如果是使用 Python Flask 后端 + 前端

如果你想用纯 Python 作为独立后端：

### 终端 1（Python 后端）：
```bash
cd flask_backend
pip install -r requirements.txt
python app.py
```
> 后端监听 `http://0.0.0.0:5000`，内置 `flask_cors` 跨域已启用。

### 终端 2（前端）：
若后端改用了 5000 端口，在启动前端前指定目标地址即可：
```bash
BACKEND_URL=http://localhost:5000 npm run dev:frontend
```
浏览器打开 `http://localhost:5173` 即可完美调用 Python 后端！
