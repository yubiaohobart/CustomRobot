# IntelliServe 极简前后端独立运行指南（无 Docker、无 Nginx 裸机模式）

如果你的环境**没有安装 Docker，也没有配置 Nginx**，只需开两个终端窗口，即可最直观、最纯粹地跑起独立的 Python FastAPI 后端与 React 前端服务。

> 💡 **零 Docker 依赖声明**：本系统向量数据库默认采用 **Qdrant 纯内存运行模式 (`:memory:`)**，直接内嵌在 Python FastAPI 进程内存中，**完全无需安装或启动任何 Docker 容器**。执行 `pip install -r requirements.txt` 和 `python app.py` 即可开箱即用！

---

## 总体架构与端口规划

```
[ 用户浏览器 ] 
      │
      ├──> 页面访问: http://IP:5173 (React 前端开发/静态分发)
      │
      └──> API 请求: http://IP:5000 (Python FastAPI 核心接口)
```

---

## 本地 / 开发环境极速双终端运行

### 终端 1：单独启动 Python FastAPI 核心后端 (端口 5000)

```bash
# 1. 进入后端目录
cd fastapi_backend

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 启动 FastAPI + LangGraph 后端
python app.py
```
> 控制台输出：
> `FastAPI + LangGraph Intelligent Customer Service Server starting on port 5000...`  
> `Interactive Swagger Docs available at: http://127.0.0.1:5000/docs`  
> 此时后端已完全就绪，在浏览器打开 `http://127.0.0.1:5000/docs` 即可看到完整的 Swagger 调试面板。

---

### 终端 2：单独启动前端服务 (端口 5173)

打开第二个终端窗口，在项目根目录下执行：

```bash
# 启动 Vite 前端（自动反代 5000 端口）
npm run dev:frontend
```
> 控制台输出：`Local: http://localhost:5173/`  
> 此时在浏览器打开 `http://localhost:5173` 即可与 FastAPI 实时交互。  
> 任何在网页上的问答、转人工、知识库检索，都会实时在终端 1 中打印出 Python 日志！

---

## 生产服务器裸机分离常驻（无需 Nginx，使用 PM2）

在云服务器上，若想同时常驻前端与后端，可直接使用进程管理工具 **PM2**：

### 1. 构建前端产物
```bash
npm run build
```
编译产物生成在 `dist/` 目录。

### 2. 使用 PM2 常驻 Python FastAPI 后端 (端口 5000)
```bash
cd fastapi_backend
pm2 start "python app.py" --name "fastapi-backend"
```

### 3. 使用轻量静态文件工具 serve 托管前端 (例如端口 80)
```bash
# 全局安装静态服务器工具 serve
npm install -g serve

# 常驻托管 dist 静态资源
pm2 start "serve -s dist -l 80" --name "react-frontend"

# 保存开机自启
pm2 save
```

运行 `pm2 list` 查看状态：
```text
┌────┬──────────────────┬──────────┬──────┬───────────┐
│ id │ name             │ mode     │ ↺    │ status    │
├────┼──────────────────┼──────────┼──────┼───────────┤
│ 0  │ fastapi-backend  │ fork     │ 0    │ online    │
│ 1  │ react-frontend   │ fork     │ 0    │ online    │
└────┴──────────────────┴──────────┴──────┴───────────┘
```
- 前端更新只需重新构建 `npm run build` 并 `pm2 restart react-frontend`；
- 后端改动逻辑只需重启 `pm2 restart fastapi-backend`；
- 两个服务完全解耦、互不阻塞！
