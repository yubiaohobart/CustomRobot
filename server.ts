import express from "express";
import http from "http";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";

dotenv.config();

const PORT = 3000;
const PYTHON_BACKEND_URL = process.env.FASTAPI_BACKEND_URL || process.env.BACKEND_URL || "http://127.0.0.1:8000";

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

  // 健康检查
  app.get("/api/gateway/status", async (req, res) => {
    res.json({
      gateway: "IntelliServe Pure Proxy Gateway",
      architecture: "Python FastAPI Authoritative (PostgreSQL)",
      pythonBackendUrl: PYTHON_BACKEND_URL,
    });
  });

  // ==================== HTTP API 纯代理路由 (透传至 FastAPI) ====================
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
      console.error(`[Gateway Proxy Error] Failed to reach Python FastAPI at ${targetUrl}:`, err.message);
      return res.status(502).json({
        error: "Python FastAPI backend is offline or unreachable",
        detail: err.message,
        targetUrl
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

  // ==================== WEBSOCKET 纯反向代理 ====================
  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const pathname = request.url
      ? new URL(request.url, `http://${request.headers.host}`).pathname
      : "";

    if (pathname.startsWith("/ws")) {
      wss.handleUpgrade(request, socket, head, (clientWs) => {
        setupWebSocketConnection(clientWs, request.url || "/ws");
      });
    } else {
      socket.destroy();
    }
  });

  async function setupWebSocketConnection(clientWs: WebSocket, targetPath: string) {
    const wsBaseUrl = PYTHON_BACKEND_URL.replace(/^http/, "ws");
    const pythonTargetWs = `${wsBaseUrl}${targetPath}`;
    
    const bufferQueue: Array<{ data: any; isBinary: boolean }> = [];
    let isPyWsOpen = false;
    let pyWs: WebSocket | null = null;

    const clientMessageHandler = (data: any, isBinary: boolean) => {
      if (isPyWsOpen && pyWs && pyWs.readyState === WebSocket.OPEN) {
        pyWs.send(data, { binary: isBinary });
      } else {
        bufferQueue.push({ data, isBinary });
      }
    };

    clientWs.on("message", clientMessageHandler);

    try {
      pyWs = new WebSocket(pythonTargetWs);
    } catch (e: any) {
      clientWs.close();
      return;
    }

    pyWs.on("open", () => {
      isPyWsOpen = true;
      while (bufferQueue.length > 0) {
        const item = bufferQueue.shift()!;
        pyWs?.send(item.data, { binary: item.isBinary });
      }
    });

    pyWs.on("message", (data, isBinary) => {
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(data, { binary: isBinary });
      }
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

    pyWs.on("error", () => {
      try { pyWs?.terminate(); } catch {}
      clientWs.close();
    });
  }

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[IntelliServe Gateway] Running on http://localhost:${PORT}`);
    console.log(`[IntelliServe Gateway] Authoritative Backend: ${PYTHON_BACKEND_URL} (PostgreSQL)`);
  });
}

startServer();
