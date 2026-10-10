import express from "express";
import http from "http";
import path from "path";
import dotenv from "dotenv";
import { WebSocketServer, WebSocket } from "ws";
import { createServer as createViteServer } from "vite";

dotenv.config();

/**
 * IntelliServe 统一应用宿主与透明代理网关 (Gateway & Host Server)
 * 
 * 核心架构规范：
 * 1. 后端业务与 WebSocket 全权交由 Python FastAPI 承担 (Single Source of Truth)
 * 2. Node.js 专职负责：
 *    - Vite 前端工程托管与 SPA 服务 (端口 3000)
 *    - HTTP API 请求反向代理 (将 /api/* 透明转发给 Python FastAPI: 5000/8000)
 *    - WebSocket 长连接透明反向代理 (将 /ws/* 双向透明接入 Python WebSocket Manager)
 * 3. 杜绝双重后端逻辑分裂，所有业务状态（会话、人工转接、RAG、LLM、实时广播）统一由 Python 维护
 */

const PORT = 3000;
const PYTHON_BACKEND_URL =
  process.env.FASTAPI_BACKEND_URL ||
  process.env.BACKEND_URL ||
  "http://127.0.0.1:5000";

const PYTHON_WS_BASE_URL = PYTHON_BACKEND_URL.replace(/^http/, "ws");

async function startServer() {
  const app = express();

  app.use(express.json());

  // 全局 CORS 支持
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.header(
      "Access-Control-Allow-Headers",
      "Origin, X-Requested-With, Content-Type, Accept, Authorization"
    );
    if (req.method === "OPTIONS") {
      return res.sendStatus(200);
    }
    next();
  });

  // 网关状态探测与健康检查
  app.get("/api/gateway/status", async (req, res) => {
    let pythonConnected = false;
    let pythonHealthData: any = null;

    try {
      const resp = await fetch(`${PYTHON_BACKEND_URL}/api/health`, {
        signal: AbortSignal.timeout(1500),
      });
      if (resp.ok) {
        pythonConnected = true;
        pythonHealthData = await resp.json();
      }
    } catch {
      pythonConnected = false;
    }

    res.json({
      gateway: "IntelliServe Node.js Gateway",
      architecture: "Python-Authoritative (All Backend & WebSocket Handled by Python FastAPI)",
      pythonBackendUrl: PYTHON_BACKEND_URL,
      pythonWsUrl: `${PYTHON_WS_BASE_URL}/ws`,
      pythonConnected,
      fastapi: pythonHealthData,
      instructions: pythonConnected
        ? "Python 后端与 WebSocket 服务运行中"
        : "请在终端执行 'cd fastapi_backend && python app.py' 启动 Python 后端",
    });
  });

  // ==================== HTTP API 透明反向代理 ====================
  // 将所有 /api/* 请求透明穿透给 Python FastAPI
  app.all("/api/*", async (req, res) => {
    const targetUrl = `${PYTHON_BACKEND_URL}${req.originalUrl}`;

    try {
      const options: RequestInit = {
        method: req.method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
      };

      if (
        req.method !== "GET" &&
        req.method !== "HEAD" &&
        req.body &&
        Object.keys(req.body).length > 0
      ) {
        options.body = JSON.stringify(req.body);
      }

      const backendRes = await fetch(targetUrl, options);
      const data = await backendRes.text();

      res.status(backendRes.status);
      res.setHeader(
        "Content-Type",
        backendRes.headers.get("content-type") || "application/json"
      );
      return res.send(data);
    } catch (err: any) {
      // 当 Python 后端暂时未启动时的友好提示
      console.warn(`[Gateway Proxy] Python backend unreachable at ${targetUrl}:`, err.message);
      return res.status(503).json({
        error: "Python Backend Unavailable",
        message: "后端服务全权交由 Python FastAPI 处理。当前未检测到活跃的 Python 服务实例。",
        targetUrl,
        hint: "请运行: cd fastapi_backend && python app.py",
      });
    }
  });

  // ==================== VITE 前端托管 ====================
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  // ==================== WEBSOCKET 透明反向代理 ====================
  // 建立 HTTP Server，WebSocket 连接 100% 穿透到 Python FastAPI 处理
  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const pathname = request.url
      ? new URL(request.url, `http://${request.headers.host}`).pathname
      : "";

    if (pathname.startsWith("/ws")) {
      wss.handleUpgrade(request, socket, head, (clientWs) => {
        // 创建通往 Python FastAPI 的 WebSocket 连接，实现全双工字节级管道代理
        proxyWebSocketToPython(clientWs, request.url || "/ws");
      });
    } else {
      socket.destroy();
    }
  });

  function proxyWebSocketToPython(clientWs: WebSocket, targetPath: string) {
    const pythonTargetWs = `${PYTHON_WS_BASE_URL}${targetPath}`;
    let pyWs: WebSocket | null = null;

    try {
      pyWs = new WebSocket(pythonTargetWs);
    } catch (e: any) {
      console.warn("[WS Proxy] Failed to instantiate Python WebSocket:", e.message);
      clientWs.send(
        JSON.stringify({
          type: "system_notice",
          error: "Python WebSocket unavailable",
          message: `无法连接到 Python FastAPI WebSocket: ${pythonTargetWs}，请确保 Python 服务正在运行。`,
        })
      );
      return;
    }

    pyWs.on("open", () => {
      console.log(`[WS Proxy] Connected client to Python WebSocket -> ${pythonTargetWs}`);
      // 客户端 -> Python FastAPI
      clientWs.on("message", (data, isBinary) => {
        if (pyWs && pyWs.readyState === WebSocket.OPEN) {
          pyWs.send(data, { binary: isBinary });
        }
      });

      // Python FastAPI -> 客户端
      pyWs.on("message", (data, isBinary) => {
        if (clientWs.readyState === WebSocket.OPEN) {
          clientWs.send(data, { binary: isBinary });
        }
      });
    });

    clientWs.on("close", () => {
      if (pyWs && (pyWs.readyState === WebSocket.OPEN || pyWs.readyState === WebSocket.CONNECTING)) {
        pyWs.close();
      }
    });

    pyWs.on("close", () => {
      if (clientWs.readyState === WebSocket.OPEN || clientWs.readyState === WebSocket.CONNECTING) {
        clientWs.close();
      }
    });

    pyWs.on("error", (err) => {
      console.warn(`[WS Proxy] Python WebSocket connection error (${pythonTargetWs}):`, err.message);
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(
          JSON.stringify({
            type: "system_notice",
            error: "Python WebSocket Unreachable",
            message: `后端 WebSocket 由 Python 管理，目前 Python 服务未响应 (${pythonTargetWs})。请启动 Python 后端。`,
          })
        );
      }
    });
  }

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[IntelliServe Gateway] Running on http://0.0.0.0:${PORT}`);
    console.log(`[IntelliServe Gateway] HTTP API Proxy -> ${PYTHON_BACKEND_URL}/api/*`);
    console.log(`[IntelliServe Gateway] WebSocket Proxy -> ${PYTHON_WS_BASE_URL}/ws/*`);
    console.log(`[IntelliServe Gateway] Backend authority: 100% Python FastAPI`);
  });
}

startServer();
