import React, { useState, useEffect } from "react";
import { 
  Bot, 
  Headphones, 
  Activity, 
  Database, 
  Sparkles
} from "lucide-react";
import { CustomerChatView } from "./components/CustomerChatView";
import { AgentWorkbench } from "./components/AgentWorkbench";
import { DualChatView } from "./components/DualChatView";
import { MonitoringDashboard } from "./components/MonitoringDashboard";
import { VectorKnowledgeBase } from "./components/VectorKnowledgeBase";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: any;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }

  componentDidCatch(error: any, errorInfo: any) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center bg-slate-50">
          <div className="w-12 h-12 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center mb-3">
            <Activity className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold text-slate-800 mb-1">页面组件遇到渲染异常</h2>
          <p className="text-xs text-slate-500 max-w-md mb-4 bg-white p-3 rounded-lg border border-slate-200 font-mono text-left">
            {this.state.error?.message || "未知错误"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition cursor-pointer"
          >
            重试恢复
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<
    "dual" | "chat" | "workbench" | "monitoring" | "vector"
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
                智能客服协同中台
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              全双工 WebSocket • 会话状态机 • 向量知识检索 • 人工坐席协同接管
            </p>
          </div>
        </div>

        {/* Navigation Tabs - 纯真实业务功能模块 */}
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
        </nav>

        {/* Header Right: Backend Status & Session Switcher */}
        <div className="flex items-center gap-2.5">
          {/* Backend Status Badge */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold rounded-lg border transition-all ${
              pythonStatus.connected
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-amber-50 text-amber-700 border-amber-200"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                pythonStatus.connected
                  ? "bg-emerald-500 animate-pulse"
                  : "bg-amber-500 animate-ping"
              }`}
            />
            <span>
              {pythonStatus.connected ? "后端服务在线 (FastAPI + WS)" : "Python 后端待连接"}
            </span>
          </div>

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

      {/* Standby Banner when Python Backend is offline */}
      {!pythonStatus.connected && (
        <div className="bg-amber-50 border-b border-amber-200/80 px-5 py-2 flex items-center justify-between text-xs text-amber-900 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
            <span>
              💡 <strong>应急热备模式运行中</strong>：前端会话、人工坐席接管与全双工 WebSocket 已全量可用。如需开启完整 AI 知识检索与 LangGraph 核心，请在本地终端运行：
            </span>
            <code className="bg-amber-100 text-amber-900 px-2 py-0.5 rounded font-mono font-bold text-[11px] border border-amber-300">
              npm run fastapi
            </code>
          </div>
          <span className="text-[11px] text-amber-700 hidden lg:inline">
            后端启动后，网关将自动秒级切换至 Python 引擎
          </span>
        </div>
      )}

      {/* Main Workspace Body */}
      <main className="flex-1 w-full h-[calc(100vh-4rem)] overflow-hidden">
        <ErrorBoundary>
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
        </ErrorBoundary>
      </main>
    </div>
  );
}
