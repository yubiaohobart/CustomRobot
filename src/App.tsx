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
  Code2
} from "lucide-react";
import { CustomerChatView } from "./components/CustomerChatView";
import { AgentWorkbench } from "./components/AgentWorkbench";
import { MonitoringDashboard } from "./components/MonitoringDashboard";
import { VectorKnowledgeBase } from "./components/VectorKnowledgeBase";
import { LangGraphVisualizer } from "./components/LangGraphVisualizer";
import { FlaskArchitectureCode } from "./components/FlaskArchitectureCode";

export default function App() {
  const [activeTab, setActiveTab] = useState<
    "chat" | "workbench" | "monitoring" | "vector" | "langgraph" | "flask"
  >("chat");

  const [currentSessionId, setCurrentSessionId] = useState("session_user_001");
  const [needsInterventionCount, setNeedsInterventionCount] = useState(0);

  // Periodically check for alerts so the badge on "人工坐席" tab updates automatically
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
                LangGraph + Flask 客服系统
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
            onClick={() => setActiveTab("flask")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "flask"
                ? "bg-white text-indigo-700 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>全栈工程源码</span>
          </button>
        </nav>

        {/* Active Session Switcher Pill */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 font-medium hidden md:inline">切换体验会话:</span>
          <div className="relative">
            <select
              id="select-session"
              value={currentSessionId}
              onChange={(e) => setCurrentSessionId(e.target.value)}
              className="px-3 py-1.5 text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium rounded-xl border border-slate-200 focus:outline-hidden cursor-pointer"
            >
              {sessionOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="flex-1 w-full h-[calc(100vh-4rem)] overflow-hidden">
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

        {activeTab === "langgraph" && <LangGraphVisualizer />}

        {activeTab === "flask" && <FlaskArchitectureCode />}
      </main>
    </div>
  );
}
