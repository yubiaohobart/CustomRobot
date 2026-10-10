import React, { useState, useEffect } from "react";
import { 
  Bot, 
  Headphones, 
  Activity, 
  Database, 
  GitBranch, 
  Server, 
  ShieldAlert, 
  User, 
  Sparkles,
  ChevronDown,
  Code2,
  Flame
} from "lucide-react";
import { CustomerChatView } from "./components/CustomerChatView";
import { ChainlitPlaygroundView } from "./components/ChainlitPlaygroundView";
import { AgentWorkbench } from "./components/AgentWorkbench";
import { DualChatView } from "./components/DualChatView";
import { MonitoringDashboard } from "./components/MonitoringDashboard";
import { VectorKnowledgeBase } from "./components/VectorKnowledgeBase";
import { LangGraphVisualizer } from "./components/LangGraphVisualizer";
import { FastAPIArchitectureCode } from "./components/FastAPIArchitectureCode";

export default function App() {
  const [activeTab, setActiveTab] = useState<
    "dual" | "chat" | "workbench" | "chainlit" | "monitoring" | "vector" | "langgraph" | "fastapi"
  >("dual");

  const [currentSessionId, setCurrentSessionId] = useState("session_user_001");
  const [needsInterventionCount, setNeedsInterventionCount] = useState(0);
  const [pythonStatus, setPythonStatus] = useState<{
    connected: boolean;
    url: string;
    wsUrl: string;
    checked: boolean;
  }>({
    connected: false,
    url: "http://127.0.0.1:5000",
    wsUrl: "ws://127.0.0.1:5000/ws",
    checked: false,
  });
  const [showArchModal, setShowArchModal] = useState(false);

  // 探测 Python FastAPI 及 WebSocket 后端状态
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch("/api/gateway/status");
        if (res.ok) {
          const data = await res.json();
          setPythonStatus({
            connected: !!data.pythonConnected,
            url: data.pythonBackendUrl || "http://127.0.0.1:5000",
            wsUrl: data.pythonWsUrl || "ws://127.0.0.1:5000/ws",
            checked: true,
          });
        }
      } catch {
        setPythonStatus(prev => ({ ...prev, connected: false, checked: true }));
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 4000);
    return () => clearInterval(interval);
  }, []);

  // 实时轮询会话预警状态
  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const res = await fetch("/api/sessions");
        if (res.ok) {
          const data = await res.json();
          const count = (data.sessions || []).filter(
            (s: any) => s.status === "NEEDS_INTERVENTION"
          ).length;
          setNeedsInterventionCount(count);
        }
      } catch (e) {
        // silent
      }
    };

    checkAlerts();
    const interval = setInterval(checkAlerts, 3000);
    return () => clearInterval(interval);
  }, []);

  const sessionOptions = [
    { id: "session_user_001", name: "王女士 (钻石VIP - 售后退款争议)" },
    { id: "session_user_002", name: "张先生 (普通会员 - 专票咨询)" },
    { id: "session_user_003", name: "刘总 (黄金会员 - 大宗加急专配)" },
    { id: "session_guest_new", name: "新访客体验会话 (点击开启全新对话)" },
  ];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-100 text-slate-800 font-sans">
      {/* Top Main Navigation Header */}
      <header className="h-16 border-b border-slate-200 bg-white px-5 flex items-center justify-between z-30 shadow-2xs">
        {/* Brand Logo & Name */}
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-amber-500 text-white shadow-xs font-bold">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-slate-900 tracking-tight">IntelliServe</span>
              <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 font-semibold rounded-full border border-blue-100">
                LangGraph + FastAPI 客服系统
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              向量检索增强 (RAG) • 会话记忆持久化 • 实时监控预警与人工接管介入
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-100/90 p-1 rounded-xl border border-slate-200/80">
          <button
            id="tab-dual"
            onClick={() => setActiveTab("dual")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer relative ${
              activeTab === "dual"
                ? "bg-white text-indigo-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>双端同屏实时对话</span>
            <span className="px-1 py-0.2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[9px] font-bold rounded">
              双向互通
            </span>
          </button>

          <button
            id="tab-chat"
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-white text-blue-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>客户对话端</span>
          </button>

          <button
            id="tab-chainlit"
            onClick={() => setActiveTab("chainlit")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer relative ${
              activeTab === "chainlit"
                ? "bg-white text-orange-600 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Flame className="w-3.5 h-3.5 fill-orange-500 text-orange-600" />
            <span>Chainlit 对话自测</span>
            <span className="px-1 py-0.1 bg-orange-100 text-orange-700 text-[9px] font-bold rounded">
              自测台
            </span>
          </button>

          <button
            id="tab-workbench"
            onClick={() => setActiveTab("workbench")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer relative ${
              activeTab === "workbench"
                ? "bg-white text-amber-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Headphones className="w-3.5 h-3.5" />
            <span>人工坐席工作台</span>
            {needsInterventionCount > 0 && (
              <span className="flex items-center justify-center px-1.5 py-0.2 bg-rose-600 text-white text-[10px] font-bold rounded-full animate-bounce">
                {needsInterventionCount}
              </span>
            )}
          </button>

          <button
            id="tab-monitoring"
            onClick={() => setActiveTab("monitoring")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "monitoring"
                ? "bg-white text-emerald-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>实时监控大盘</span>
          </button>

          <button
            id="tab-vector"
            onClick={() => setActiveTab("vector")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "vector"
                ? "bg-white text-indigo-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>向量知识库</span>
          </button>

          <button
            id="tab-langgraph"
            onClick={() => setActiveTab("langgraph")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "langgraph"
                ? "bg-white text-purple-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span>LangGraph 拓扑</span>
          </button>

          <button
            id="tab-code"
            onClick={() => setActiveTab("fastapi")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "fastapi"
                ? "bg-white text-indigo-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>FastAPI 架构源码</span>
          </button>
        </nav>

        {/* Header Right: Backend Status & Session Switcher */}
        <div className="flex items-center gap-2.5">
          {/* Backend Authority Badge */}
          <button
            onClick={() => setShowArchModal(true)}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold rounded-lg border transition-all cursor-pointer ${
              pythonStatus.connected
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                : "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
            }`}
            title="后端职责：100% 由 Python FastAPI + WebSocket 承载，点击查看架构"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                pythonStatus.connected
                  ? "bg-emerald-500 animate-pulse"
                  : "bg-amber-500 animate-ping"
              }`}
            />
            <span>
              {pythonStatus.connected ? "Python 后端在线 (FastAPI + WS)" : "Python 独占后端 (待连接)"}
            </span>
            <span className="text-[9px] px-1 py-0.2 bg-white/80 rounded font-mono">
              :5000
            </span>
          </button>

          <span className="text-[11px] text-slate-300 hidden md:inline">|</span>

          {/* Active Session Switcher Pill */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-slate-400 font-medium hidden lg:inline">体验会话:</span>
            <div className="relative">
              <select
                id="select-session"
                value={currentSessionId}
                onChange={(e) => setCurrentSessionId(e.target.value)}
                className="px-2.5 py-1 text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium rounded-lg border border-slate-200 focus:outline-hidden cursor-pointer"
              >
                {sessionOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* Backend Architecture & Startup Modal */}
      {showArchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full p-6 text-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <span className="p-2 bg-indigo-50 text-indigo-600 rounded-xl font-mono text-sm">🐍</span>
                <div>
                  <h3 className="font-bold text-base text-slate-900">Python 独占式后端架构 (FastAPI + WebSocket)</h3>
                  <p className="text-xs text-slate-500">统一事实源 • 后端一切逻辑均由 Python 实现</p>
                </div>
              </div>
              <button
                onClick={() => setShowArchModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-600">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>📌 架构定位与职责划分：</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                    pythonStatus.connected ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                  }`}>
                    {pythonStatus.connected ? "Python 服务运行中" : "等待启动 Python 服务"}
                  </span>
                </div>
                <p>• <strong>Python FastAPI (Port 5000/8000)</strong>：独占实现<strong>全部后端业务</strong>（Qdrant 向量匹配、LangGraph 节点流转、会话记忆持久化、人工客服分配、订单查询）以及<strong>原生 WebSocket 全双工长连接</strong>（<code>websocket_manager.py</code>）。</p>
                <p>• <strong>Node.js (Port 3000)</strong>：仅作为纯前端 Vite 托管服务和透明代理网关（HTTP 反向代理 + WebSocket 管道穿透代理），绝不维护多余的本地模拟后端状态。</p>
              </div>

              <div>
                <span className="font-semibold text-slate-700 block mb-1">🚀 本地启动 Python FastAPI 后端：</span>
                <pre className="p-3 bg-slate-900 text-emerald-400 font-mono text-[11px] rounded-xl overflow-x-auto select-all">
cd fastapi_backend{"\n"}
pip install -r requirements.txt{"\n"}
python app.py
                </pre>
              </div>

              <div className="text-[11px] text-slate-500">
                启动后，前端浏览器即可通过透明网关 <code>/ws</code> 自动无缝接入 Python 的 WebSocket 连接池，享受毫秒级双向打字感知与坐席协同。
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowArchModal(false)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-xl cursor-pointer"
              >
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Workspace Body */}
      <main className="flex-1 w-full h-[calc(100vh-4rem)] overflow-hidden">
        {activeTab === "dual" && <DualChatView />}

        {activeTab === "chat" && (
          <CustomerChatView
            currentSessionId={currentSessionId}
            onSelectSession={setCurrentSessionId}
            onInterventionAlert={() => {
              setNeedsInterventionCount((prev) => prev + 1);
            }}
          />
        )}

        {activeTab === "chainlit" && <ChainlitPlaygroundView />}

        {activeTab === "workbench" && (
          <AgentWorkbench
            currentSessionId={currentSessionId}
            onSelectSession={setCurrentSessionId}
          />
        )}

        {activeTab === "monitoring" && (
          <MonitoringDashboard
            onNavigateToWorkbench={(sessionId) => {
              if (sessionId) setCurrentSessionId(sessionId);
              setActiveTab("workbench");
            }}
          />
        )}

        {activeTab === "vector" && <VectorKnowledgeBase />}

        {activeTab === "langgraph" && <LangGraphVisualizer />}

        {activeTab === "fastapi" && <FastAPIArchitectureCode />}
      </main>
    </div>
  );
}
