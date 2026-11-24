import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { WsClientEvent, WsRole, WsServerEvent } from "../types";

export interface JoinParams {
  sessionId: string;
  role: WsRole;
  name?: string;
}

interface WebSocketContextValue {
  isConnected: boolean;
  joinSession: (params: JoinParams) => void;
  sendJson: (payload: WsClientEvent) => void;
  subscribe: (listener: (payload: WsServerEvent) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// 全局单连接实例状态（跨标签页复用同一条 /ws 长连接，避免切换页面或 StrictMode 重复建连）
let sharedSocket: WebSocket | null = null;
let sharedConnected = false;
let desiredJoin: JoinParams | null = null;
let lastSentJoinKey = "";
let pendingCloseTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let providerActiveCount = 0;

const HEARTBEAT_INTERVAL_MS = 30_000;

const messageListeners = new Set<(payload: WsServerEvent) => void>();
const statusListeners = new Set<(connected: boolean) => void>();

function notifyStatus(connected: boolean) {
  sharedConnected = connected;
  statusListeners.forEach((cb) => cb(connected));
}

function getWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const hostname = window.location.hostname === "0.0.0.0" ? "127.0.0.1" : window.location.hostname;
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${protocol}//${hostname}${port}/ws`;
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function startHeartbeat(ws: WebSocket) {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (sharedSocket === ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping", data: {} } satisfies WsClientEvent));
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function sendJoinIfNeeded(force = false) {
  if (!sharedSocket || sharedSocket.readyState !== WebSocket.OPEN || !desiredJoin) return;
  const key = `${desiredJoin.sessionId}::${desiredJoin.role}::${desiredJoin.name || ""}`;
  if (!force && key === lastSentJoinKey) return;
  lastSentJoinKey = key;
  const joinFrame: WsClientEvent = {
    type: "join",
    sessionId: desiredJoin.sessionId,
    data: {
      role: desiredJoin.role,
      name: desiredJoin.name || "",
    },
  };
  sharedSocket.send(JSON.stringify(joinFrame));
}

function connectSharedSocket() {
  if (pendingCloseTimer) {
    clearTimeout(pendingCloseTimer);
    pendingCloseTimer = null;
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (
    sharedSocket &&
    (sharedSocket.readyState === WebSocket.OPEN || sharedSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  try {
    const ws = new WebSocket(getWsUrl());
    sharedSocket = ws;

    ws.onerror = () => {
      // suppress unhandled WebSocket connection errors
    };

    ws.onopen = () => {
      if (sharedSocket !== ws || providerActiveCount <= 0) {
        try {
          ws.close();
        } catch (e) {}
        return;
      }
      lastSentJoinKey = "";
      notifyStatus(true);
      sendJoinIfNeeded(true);
      startHeartbeat(ws);
    };

    ws.onmessage = (evt) => {
      if (sharedSocket !== ws) return;
      try {
        const payload = JSON.parse(evt.data) as WsServerEvent;
        messageListeners.forEach((listener) => {
          try {
            listener(payload);
          } catch (e) {
            // isolate individual listener errors
          }
        });
      } catch (e) {
        // ignore non-JSON frames
      }
    };

    ws.onclose = () => {
      if (sharedSocket === ws) {
        sharedSocket = null;
        lastSentJoinKey = "";
        stopHeartbeat();
        notifyStatus(false);
        if (providerActiveCount > 0 && !reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            if (providerActiveCount > 0) {
              connectSharedSocket();
            }
          }, 3000);
        }
      }
    };
  } catch (e) {
    notifyStatus(false);
  }
}

function scheduleCloseIfUnused() {
  if (pendingCloseTimer) clearTimeout(pendingCloseTimer);
  pendingCloseTimer = setTimeout(() => {
    pendingCloseTimer = null;
    if (providerActiveCount > 0) return;
    stopHeartbeat();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (sharedSocket) {
      const ws = sharedSocket;
      sharedSocket = null;
      lastSentJoinKey = "";
      notifyStatus(false);
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.close();
        } catch (e) {}
      }
    }
  }, 150);
}

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isConnected, setIsConnected] = useState(sharedConnected);

  useEffect(() => {
    providerActiveCount++;
    const onStatusChange = (connected: boolean) => setIsConnected(connected);
    statusListeners.add(onStatusChange);
    connectSharedSocket();

    return () => {
      providerActiveCount = Math.max(0, providerActiveCount - 1);
      statusListeners.delete(onStatusChange);
      if (providerActiveCount === 0) {
        scheduleCloseIfUnused();
      }
    };
  }, []);

  const joinSession = useCallback((params: JoinParams) => {
    desiredJoin = params;
    sendJoinIfNeeded(false);
  }, []);

  const sendJson = useCallback((payload: WsClientEvent) => {
    if (sharedSocket && sharedSocket.readyState === WebSocket.OPEN) {
      sharedSocket.send(JSON.stringify(payload));
    }
  }, []);

  const subscribe = useCallback((listener: (payload: WsServerEvent) => void) => {
    messageListeners.add(listener);
    return () => {
      messageListeners.delete(listener);
    };
  }, []);

  return (
    <WebSocketContext.Provider value={{ isConnected, joinSession, sendJson, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocket must be used within WebSocketProvider");
  }
  return ctx;
}
