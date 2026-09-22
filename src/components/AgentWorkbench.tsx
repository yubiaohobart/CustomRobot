import React, { useState, useEffect, useRef } from "react";
import { 
  Headphones, 
  Bot, 
  User, 
  AlertTriangle, 
  CheckCircle2, 
  Send, 
  Sparkles, 
  Search, 
  ArrowRightLeft, 
  ShieldAlert, 
  Clock, 
  Tag, 
  FileText, 
  ChevronRight,
  RefreshCw,
  Copy,
  Zap,
  MessageSquare,
  History,
  Check,
  Forward,
  Info,
  ExternalLink,
  Layers,
  X,
  FileCheck,
  UserCheck
} from "lucide-react";
import { 
  ConversationSession, 
  ChatMessage, 
  SessionStatus, 
  TransferLog, 
  AvailableAgent,
  TransferContextSnapshot
} from "../types";

interface AgentWorkbenchProps {
  currentSessionId: string;
  onSelectSession: (id: string) => void;
}

export const AgentWorkbench: React.FC<AgentWorkbenchProps> = ({
  currentSessionId,
  onSelectSession,
}) => {
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [activeSession, setActiveSession] = useState<ConversationSession | null>(null);
  const [filterStatus, setFilterStatus] = useState<"ALL" | SessionStatus>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [agentInput, setAgentInput] = useState("");
  const [sending, setSending] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotSuggestion, setCopilotSuggestion] = useState<string | null>(null);
  const [copilotReferences, setCopilotReferences] = useState<any[]>([]);
  const [quickSearchQuery, setQuickSearchQuery] = useState("");
  const [quickSearchResults, setQuickSearchResults] = useState<any[]>([]);

  // Transfer-specific states
  const [rightTab, setRightTab] = useState<"dossier" | "profile" | "logs">("dossier");
  const [transferLogs, setTransferLogs] = useState<TransferLog[]>([]);
  const [availableAgents, setAvailableAgents] = useState<AvailableAgent[]>([]);
  const [selectedAuditLog, setSelectedAuditLog] = useState<TransferLog | null>(null);
  const [showReTransferModal, setShowReTransferModal] = useState(false);
  const [reTransferAgentId, setReTransferAgentId] = useState("");
  const [reTransferReason, setReTransferReason] = useState("问题涉及更专业的财务或技术支持，转交专职坐席协同解决");
  const [reTransferNote, setReTransferNote] = useState("");
  const [reTransferring, setReTransferring] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
        
        // Update active session if selected
        if (currentSessionId) {
          const current = data.sessions.find((s: ConversationSession) => s.id === currentSessionId);
          if (current) setActiveSession(current);
        } else if (data.sessions.length > 0) {
          setActiveSession(data.sessions[0]);
          onSelectSession(data.sessions[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTransferData = async () => {
    try {
      const [resLogs, resAgents] = await Promise.all([
        fetch("/api/transfer-logs"),
        fetch("/api/agents"),
      ]);
      if (resLogs.ok) {
        const data = await resLogs.json();
        setTransferLogs(data.transferLogs || []);
      }
      if (resAgents.ok) {
        const data = await resAgents.json();
        setAvailableAgents(data.agents || []);
        if (data.agents?.length > 0 && !reTransferAgentId) {
          setReTransferAgentId(data.agents[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSessions();
    fetchTransferData();
    const interval = setInterval(() => {
      fetchSessions();
      fetchTransferData();
    }, 3000);
    return () => clearInterval(interval);
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeSession?.messages]);

  // When active session changes, automatically switch to dossier tab if it was transferred
  useEffect(() => {
    if (activeSession?.latestTransfer) {
      setRightTab("dossier");
    }
  }, [activeSession?.id]);

  const handleTakeover = async () => {
    if (!activeSession) return;
    try {
      const res = await fetch(`/api/sessions/${activeSession.id}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "takeover", agentName: "人工坐席 #108 - 陈主管" }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data.session);
        fetchSessions();
        showToast("已成功接管会话，现在您可以直接与客户沟通");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleHandback = async () => {
    if (!activeSession) return;
    try {
      const res = await fetch(`/api/sessions/${activeSession.id}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "release" }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data.session);
        fetchSessions();
        showToast("人工介入已结束，会话已无缝交还给智能客服(AI Agent)托管");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendHumanMessage = async (customText?: string) => {
    const text = (customText || agentInput).trim();
    if (!text || !activeSession || sending) return;

    setSending(true);
    try {
      const res = await fetch(`/api/sessions/${activeSession.id}/human-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          agentName: activeSession.assignedAgent || "人工客服 #108 - 陈主管",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data.session);
        setAgentInput("");
        setCopilotSuggestion(null);
        fetchSessions();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
    }
  };

  const handleExecuteReTransfer = async () => {
    if (!activeSession || !reTransferAgentId || reTransferring) return;
    setReTransferring(true);
    try {
      const res = await fetch(`/api/sessions/${activeSession.id}/transfer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetAgentId: reTransferAgentId,
          reason: reTransferReason,
          operatorNote: reTransferNote,
          triggerType: "manual_dispatch",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data.session);
        setShowReTransferModal(false);
        fetchSessions();
        fetchTransferData();
        showToast(`已成功将完整上下文改派流转至：${data.transferLog?.assignedAgentName}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setReTransferring(false);
    }
  };

  const handleGenerateCopilot = async () => {
    if (!activeSession) return;
    setCopilotLoading(true);
    try {
      const res = await fetch("/api/generate-suggestion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: activeSession.id }),
      });
      if (res.ok) {
        const data = await res.json();
        setCopilotSuggestion(data.suggestion);
        setCopilotReferences(data.references || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCopilotLoading(false);
    }
  };

  const handleGenerateAwarenessGreeting = () => {
    if (!activeSession) return;
    const latest = activeSession.latestTransfer?.contextSnapshot;
    const customer = activeSession.userName;
    const intent = activeSession.customerProfile.intent;
    const orderId = activeSession.customerProfile.orderId;
    
    let greeting = `您好，${customer}！我是为您接入的值班客服主管。我已完整阅读了您方才的沟通记录与记忆，关于您咨询的【${intent}】`;
    if (orderId) {
      greeting += `（关联单号：${orderId}）`;
    }
    greeting += `，我已经为您核实了后台系统状态并接管推进，请您放心，无需重复说明！`;
    
    setAgentInput(greeting);
    showToast("已自动根据交接单生成全知情接入问候语");
  };

  const handleQuickKnowledgeSearch = async (q: string) => {
    setQuickSearchQuery(q);
    if (!q.trim()) {
      setQuickSearchResults([]);
      return;
    }
    try {
      const res = await fetch("/api/knowledge/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, topK: 3 }),
      });
      if (res.ok) {
        const data = await res.json();
        setQuickSearchResults(data.results || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const cannedResponses = [
    "您好，我是值班客服主管，已为您全面接入跟进，请您放心！",
    "非常抱歉给您带来不便！我已经联系仓库质检加急开辟特批通道，预计今天下午完成退款原路退回。",
    "企业增值税专用发票开具需要提供公司税号与开户行账号，我已在工单中为您登记并启动3日顺丰包邮流程。",
    "该物流件已为您联系顺丰区域调度升级为【红标特快】，承诺在今晚21:00前由专车单独送达。",
    "感谢您的耐心等待，若您后续还有任何其他疑问，可随时联系我为您专属服务！"
  ];

  // Filtering
  const filteredSessions = sessions.filter((s) => {
    if (filterStatus !== "ALL" && s.status !== filterStatus) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        s.userName.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.customerProfile.intent.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const needsInterventionCount = sessions.filter((s) => s.status === "NEEDS_INTERVENTION").length;
  const humanServingCount = sessions.filter((s) => s.status === "HUMAN_INTERVENED").length;

  const currentSnapshot: TransferContextSnapshot | undefined = activeSession?.latestTransfer?.contextSnapshot;
  const activeTargetAgent = availableAgents.find((a) => a.id === reTransferAgentId) || availableAgents[0];

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full overflow-hidden bg-slate-100 relative">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="absolute top-4 right-8 z-50 flex items-center gap-2 px-4 py-2.5 bg-slate-900/95 text-white text-xs rounded-xl shadow-lg border border-slate-700 animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* 1. Left Session List Sidebar */}
      <div className="w-80 h-full bg-white border-r border-slate-200 flex flex-col shrink-0">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Headphones className="w-5 h-5 text-amber-600" />
              <h2 className="text-sm font-bold text-slate-800">客服座席介入工作台</h2>
            </div>
            <button
              onClick={() => {
                fetchSessions();
                fetchTransferData();
              }}
              title="刷新会话"
              className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-2">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="搜索客户名 / 订单 / 意图..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500"
            />
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-1 overflow-x-auto text-[11px] pt-1">
            <button
              onClick={() => setFilterStatus("ALL")}
              className={`px-2 py-1 rounded-md whitespace-nowrap font-medium transition-colors cursor-pointer ${
                filterStatus === "ALL" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              全部 ({sessions.length})
            </button>
            <button
              onClick={() => setFilterStatus("NEEDS_INTERVENTION")}
              className={`px-2 py-1 rounded-md whitespace-nowrap font-medium flex items-center gap-1 transition-colors cursor-pointer ${
                filterStatus === "NEEDS_INTERVENTION"
                  ? "bg-rose-600 text-white"
                  : "bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200"
              }`}
            >
              <AlertTriangle className="w-3 h-3" />
              待介入 ({needsInterventionCount})
            </button>
            <button
              onClick={() => setFilterStatus("HUMAN_INTERVENED")}
              className={`px-2 py-1 rounded-md whitespace-nowrap font-medium transition-colors cursor-pointer ${
                filterStatus === "HUMAN_INTERVENED" ? "bg-amber-600 text-white" : "bg-amber-50 text-amber-700 hover:bg-amber-100"
              }`}
            >
              人工中 ({humanServingCount})
            </button>
            <button
              onClick={() => setFilterStatus("AI_HANDLING")}
              className={`px-2 py-1 rounded-md whitespace-nowrap font-medium transition-colors cursor-pointer ${
                filterStatus === "AI_HANDLING" ? "bg-blue-600 text-white" : "bg-blue-50 text-blue-700 hover:bg-blue-100"
              }`}
            >
              AI托管
            </button>
          </div>
        </div>

        {/* Session Items */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {filteredSessions.map((s) => {
            const isSelected = activeSession?.id === s.id;
            const isNeedIntervention = s.status === "NEEDS_INTERVENTION";
            const isHumanServing = s.status === "HUMAN_INTERVENED";
            const lastMsg = s.messages[s.messages.length - 1];
            const hasTransfer = Boolean(s.latestTransfer || (s.transferLogs && s.transferLogs.length > 0));

            return (
              <div
                key={s.id}
                onClick={() => {
                  setActiveSession(s);
                  onSelectSession(s.id);
                  setCopilotSuggestion(null);
                }}
                className={`p-3.5 cursor-pointer transition-colors relative ${
                  isSelected ? "bg-blue-50/80 border-l-4 border-blue-600" : "hover:bg-slate-50"
                }`}
              >
                {/* Title & Badge */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-800 text-xs">{s.userName}</span>
                    <span className="text-[10px] text-slate-400">({s.customerProfile.vipLevel})</span>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                    isNeedIntervention 
                      ? "bg-rose-100 text-rose-800 animate-pulse border border-rose-200" 
                      : isHumanServing
                      ? "bg-amber-100 text-amber-800 border border-amber-200"
                      : "bg-blue-50 text-blue-700"
                  }`}>
                    {isNeedIntervention ? "待介入" : isHumanServing ? "人工处理" : "AI托管"}
                  </span>
                </div>

                {/* Transfer badge indicator if applicable */}
                {hasTransfer && (
                  <div className="mb-1.5 flex items-center gap-1 text-[10px] text-amber-700 font-medium">
                    <FileCheck className="w-3 h-3 text-amber-600 shrink-0" />
                    <span className="truncate">
                      已转接: {s.latestTransfer?.assignedAgentName || s.assignedAgent || "人工客服"}
                    </span>
                  </div>
                )}

                {/* Last Message Snippet */}
                <p className="text-[11px] text-slate-500 line-clamp-1 mb-1.5">
                  {lastMsg ? `${lastMsg.role === "user" ? "用户" : "客服"}: ${lastMsg.content}` : "新会话"}
                </p>

                {/* Footer tags */}
                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <span className="truncate max-w-[120px]">{s.customerProfile.intent}</span>
                  <span>{lastMsg?.timestamp || s.createdAt}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Middle Main Chat Interface */}
      <div className="flex-1 h-full flex flex-col bg-white overflow-hidden min-w-0">
        {activeSession ? (
          <>
            {/* Chat Top Header */}
            <div className="p-4 border-b border-slate-200 bg-white flex items-center justify-between shrink-0 shadow-2xs">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-slate-800">{activeSession.userName}</h2>
                  <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                    会话: {activeSession.id}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    activeSession.status === "NEEDS_INTERVENTION"
                      ? "bg-rose-100 text-rose-800 border border-rose-200 animate-pulse"
                      : activeSession.status === "HUMAN_INTERVENED"
                      ? "bg-amber-100 text-amber-800 border border-amber-200"
                      : "bg-emerald-100 text-emerald-800"
                  }`}>
                    {activeSession.status === "NEEDS_INTERVENTION"
                      ? "🚨 触发人工介入预警"
                      : activeSession.status === "HUMAN_INTERVENED"
                      ? `🎧 人工接管中 (${activeSession.assignedAgent || "人工坐席"})`
                      : "🤖 AI 自动问答中"}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  情绪指标: <strong className={activeSession.customerProfile.sentiment === "frustrated" ? "text-rose-600" : "text-emerald-600"}>
                    {activeSession.customerProfile.sentiment === "frustrated" ? "急躁/不满" : "平和"}
                  </strong> • 紧急度: {activeSession.customerProfile.urgency} • 会话轮数: {activeSession.metrics.totalTurns}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                {activeSession.status === "HUMAN_INTERVENED" ? (
                  <>
                    <button
                      id="btn-retransfer"
                      onClick={() => setShowReTransferModal(true)}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-300 transition-colors cursor-pointer"
                    >
                      <Forward className="w-3.5 h-3.5 text-amber-600" />
                      <span>转交其他坐席</span>
                    </button>

                    <button
                      id="btn-agent-handback"
                      onClick={handleHandback}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg border border-slate-300 transition-colors cursor-pointer"
                    >
                      <ArrowRightLeft className="w-3.5 h-3.5 text-blue-600" />
                      <span>结束人工并转回AI托管</span>
                    </button>
                  </>
                ) : (
                  <button
                    id="btn-agent-takeover"
                    onClick={handleTakeover}
                    className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-xs transition-colors cursor-pointer"
                  >
                    <Headphones className="w-3.5 h-3.5" />
                    <span>立即介入接管会话</span>
                  </button>
                )}
              </div>
            </div>

            {/* Seamless Transfer Context Notification Banner */}
            {activeSession.latestTransfer && (
              <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-200 flex items-center justify-between text-xs shrink-0">
                <div className="flex items-center gap-2 text-amber-900">
                  <div className="w-6 h-6 rounded-full bg-amber-200 flex items-center justify-center shrink-0">
                    <FileCheck className="w-3.5 h-3.5 text-amber-800" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <strong className="font-bold">无缝移交上下文已全量接入</strong>
                      <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded border border-amber-300">
                        {activeSession.latestTransfer.triggerType === "ai_fallback" ? "智能客服自动无法回答" : "用户主动要求转接"}
                      </span>
                      <span className="text-amber-700 text-[11px] font-mono">
                        流水号: {activeSession.latestTransfer.id}
                      </span>
                    </div>
                    <div className="text-[11px] text-amber-800 mt-0.5">
                      转接原因: <span className="font-medium">{activeSession.latestTransfer.reason}</span>
                      {activeSession.latestTransfer.operatorNote && (
                        <span className="ml-2 text-amber-700">| 附言: {activeSession.latestTransfer.operatorNote}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={handleGenerateAwarenessGreeting}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-amber-900 bg-white hover:bg-amber-100 border border-amber-300 rounded-md transition-colors cursor-pointer shadow-2xs"
                  >
                    <Sparkles className="w-3 h-3 text-amber-600" />
                    <span>智能生成知情问候</span>
                  </button>
                  <button
                    onClick={() => setRightTab("dossier")}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-md transition-colors cursor-pointer"
                  >
                    <FileText className="w-3 h-3" />
                    <span>查看完整交接单</span>
                  </button>
                </div>
              </div>
            )}

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50/60">
              {activeSession.messages.map((msg) => {
                const isUser = msg.role === "user";
                const isHumanAgent = msg.role === "human_agent";
                const isSystem = msg.role === "system";

                if (isSystem) {
                  return (
                    <div key={msg.id} className="flex justify-center my-2">
                      <span className="px-3 py-1 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-full">
                        {msg.content} ({msg.timestamp})
                      </span>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 max-w-2xl ${isUser ? "mr-auto" : "ml-auto flex-row-reverse"}`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold shadow-xs shrink-0 ${
                      isUser ? "bg-slate-700 text-white" : isHumanAgent ? "bg-amber-600 text-white" : "bg-blue-600 text-white"
                    }`}>
                      {isUser ? <User className="w-4 h-4" /> : isHumanAgent ? <Headphones className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>

                    <div className={`flex flex-col ${isUser ? "items-start" : "items-end"} max-w-[85%]`}>
                      <div className="flex items-center gap-2 mb-1 text-[11px] text-slate-400">
                        <span>{isUser ? activeSession.userName : isHumanAgent ? (activeSession.assignedAgent || "人工客服") : "智能客服 (AI)"}</span>
                        <span>{msg.timestamp}</span>
                        {msg.confidenceScore && (
                          <span className="text-[10px] bg-slate-200 px-1 rounded">
                            置信度: {(msg.confidenceScore * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>

                      <div className={`p-3.5 rounded-xl text-xs leading-relaxed ${
                        isUser
                          ? "bg-white text-slate-800 border border-slate-200 shadow-xs"
                          : isHumanAgent
                          ? "bg-amber-600 text-white shadow-xs"
                          : "bg-blue-50 text-blue-950 border border-blue-100"
                      }`}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            {/* AI Copilot Suggestion Box */}
            <div className="px-6 py-2 bg-gradient-to-r from-blue-50/70 to-indigo-50/70 border-t border-blue-100 shrink-0">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-800">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  <span>AI 智能话术辅助 (Copilot Suggestion)</span>
                </div>
                <button
                  id="btn-generate-copilot"
                  onClick={handleGenerateCopilot}
                  disabled={copilotLoading}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-700 bg-white hover:bg-blue-50 border border-blue-200 rounded-md transition-colors cursor-pointer"
                >
                  <Zap className="w-3 h-3 text-amber-500" />
                  <span>{copilotLoading ? "结合知识库生成中..." : "生成推荐回复"}</span>
                </button>
              </div>

              {copilotSuggestion ? (
                <div className="p-2.5 bg-white rounded-lg border border-blue-200 text-xs shadow-xs">
                  <p className="text-slate-800 leading-relaxed mb-2 font-sans">{copilotSuggestion}</p>
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => setAgentInput(copilotSuggestion)}
                      className="px-2.5 py-1 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded cursor-pointer"
                    >
                      填入编辑框
                    </button>
                    <button
                      onClick={() => handleSendHumanMessage(copilotSuggestion)}
                      className="px-3 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded cursor-pointer"
                    >
                      直接采用发送
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-slate-500">
                  点击【生成推荐回复】，系统将根据当前会话记忆与向量知识库，为您拟定高情商、合规的专业客服话术。
                </p>
              )}
            </div>

            {/* Canned Quick Responses Bar */}
            <div className="px-6 py-2 bg-white border-t border-slate-200 flex items-center gap-2 overflow-x-auto text-xs scrollbar-none shrink-0">
              <span className="text-slate-400 whitespace-nowrap text-[11px]">快捷常用语:</span>
              {cannedResponses.map((cr, idx) => (
                <button
                  key={idx}
                  onClick={() => setAgentInput(cr)}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md whitespace-nowrap transition-colors cursor-pointer text-xs"
                >
                  {cr.slice(0, 18)}...
                </button>
              ))}
            </div>

            {/* Message Input Form */}
            <div className="p-4 bg-white border-t border-slate-200 shrink-0">
              <div className="flex gap-2">
                <textarea
                  id="agent-chat-input"
                  rows={2}
                  value={agentInput}
                  onChange={(e) => setAgentInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      handleSendHumanMessage();
                    }
                  }}
                  placeholder={
                    activeSession.status === "HUMAN_INTERVENED"
                      ? "以【人工客服坐席】身份向客户发送消息（按 Ctrl+Enter 快速发送）..."
                      : "温馨提示：当前处于AI托管状态，发送消息将自动激活人工接管..."
                  }
                  className="flex-1 p-2.5 bg-slate-50 focus:bg-white text-xs text-slate-800 rounded-xl border border-slate-200 focus:outline-hidden focus:border-amber-500 focus:ring-2 focus:ring-amber-100 resize-none transition-all"
                />
                <button
                  id="btn-agent-send"
                  onClick={() => handleSendHumanMessage()}
                  disabled={sending || !agentInput.trim()}
                  className="px-5 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-semibold text-xs rounded-xl flex flex-col items-center justify-center gap-1 transition-colors shadow-xs cursor-pointer disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  <span>发送回复</span>
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-xs">
            <MessageSquare className="w-10 h-10 mb-2 text-slate-300" />
            <p>请从左侧列表选择一个客户会话进行实时监控或接管介入</p>
          </div>
        )}
      </div>

      {/* 3. Right Inspection Panel (Customer 360, Context Dossier, Audit Logs) */}
      <div className="w-96 h-full bg-white border-l border-slate-200 flex flex-col shrink-0 overflow-hidden">
        {/* Right Panel Navigation Tabs */}
        <div className="p-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
          <div className="flex gap-1">
            <button
              onClick={() => setRightTab("dossier")}
              className={`flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                rightTab === "dossier" 
                  ? "bg-amber-600 text-white shadow-xs" 
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              <FileCheck className="w-3.5 h-3.5" />
              <span>交接单快照</span>
            </button>

            <button
              onClick={() => setRightTab("profile")}
              className={`flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                rightTab === "profile" 
                  ? "bg-blue-600 text-white shadow-xs" 
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              <Tag className="w-3.5 h-3.5" />
              <span>客户画像/检索</span>
            </button>

            <button
              onClick={() => setRightTab("logs")}
              className={`flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                rightTab === "logs" 
                  ? "bg-slate-800 text-white shadow-xs" 
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>转接流水 ({transferLogs.length})</span>
            </button>
          </div>
        </div>

        {/* Panel Tab Contents */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
          {/* TAB 1: Transfer Context Dossier Snapshot */}
          {rightTab === "dossier" && (
            <div className="space-y-4">
              {activeSession?.latestTransfer ? (
                <>
                  {/* Summary Card */}
                  <div className="p-3.5 bg-gradient-to-br from-amber-50 to-orange-50/50 rounded-xl border border-amber-200 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-amber-900 text-xs flex items-center gap-1.5">
                        <FileCheck className="w-4 h-4 text-amber-600" />
                        <span>无缝转接上下文交接单</span>
                      </span>
                      <span className="px-1.5 py-0.5 bg-amber-200/80 text-amber-900 font-mono text-[10px] rounded font-semibold">
                        {activeSession.latestTransfer.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-700 bg-white p-2.5 rounded-lg border border-amber-100">
                      <div>
                        <span className="text-slate-400">流水编号:</span>
                        <div className="font-mono text-slate-800 font-semibold truncate">{activeSession.latestTransfer.id}</div>
                      </div>
                      <div>
                        <span className="text-slate-400">移交时间:</span>
                        <div className="text-slate-800">{activeSession.latestTransfer.transferredAt}</div>
                      </div>
                      <div>
                        <span className="text-slate-400">接收坐席:</span>
                        <div className="font-semibold text-slate-900">{activeSession.latestTransfer.assignedAgentName}</div>
                      </div>
                      <div>
                        <span className="text-slate-400">归属科室:</span>
                        <div className="text-slate-800">{activeSession.latestTransfer.assignedDepartment}</div>
                      </div>
                    </div>

                    <div className="text-[11px] text-slate-700">
                      <span className="text-slate-400">转接原因说明:</span>
                      <p className="mt-0.5 p-2 bg-white rounded border border-amber-100 font-medium text-slate-800">
                        {activeSession.latestTransfer.reason}
                      </p>
                    </div>

                    {activeSession.latestTransfer.operatorNote && (
                      <div className="text-[11px] text-slate-700">
                        <span className="text-slate-400">交接附言:</span>
                        <p className="mt-0.5 p-2 bg-amber-100/50 rounded border border-amber-200 text-amber-900 font-sans">
                          {activeSession.latestTransfer.operatorNote}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Complete Context Package Snapshot Breakdown */}
                  {currentSnapshot && (
                    <div className="space-y-3">
                      {/* Customer Questions History Snapshot */}
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 text-[11px] flex items-center gap-1">
                            <User className="w-3.5 h-3.5 text-blue-600" />
                            <span>用户提问历史清单 ({currentSnapshot.userQuestions.length} 条)</span>
                          </span>
                          <span className="text-[10px] text-blue-600 font-mono">已全量冻结</span>
                        </div>

                        <div className="space-y-1.5">
                          {currentSnapshot.userQuestions.map((q, idx) => (
                            <div key={idx} className="p-2 bg-white rounded-lg border border-slate-100 text-[11px] text-slate-800 flex gap-1.5">
                              <span className="text-blue-600 font-mono font-bold shrink-0">#{idx + 1}</span>
                              <span className="leading-snug">{q}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* AI Answers History Snapshot */}
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 text-[11px] flex items-center gap-1">
                            <Bot className="w-3.5 h-3.5 text-indigo-600" />
                            <span>转接前智能客服最后回答</span>
                          </span>
                          {currentSnapshot.confidenceScore && (
                            <span className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-mono">
                              置信度: {(currentSnapshot.confidenceScore * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>

                        <p className="p-2.5 bg-white rounded-lg border border-slate-100 text-[11px] text-slate-700 leading-relaxed">
                          {currentSnapshot.lastAiResponse || "尚未生成完整回答即触发无缝转接"}
                        </p>
                      </div>

                      {/* Session Memory Summary Snapshot */}
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 text-[11px] flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5 text-emerald-600" />
                            <span>冻结的长期会话记忆 (MemorySaver)</span>
                          </span>
                          <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded font-mono">
                            Snapshot
                          </span>
                        </div>

                        <p className="p-2.5 bg-white rounded-lg border border-slate-100 text-[11px] text-slate-700 leading-relaxed font-sans">
                          {currentSnapshot.summaryMemory || "新会话建立，尚无长文记忆摘要。"}
                        </p>
                      </div>

                      {/* Fast Action */}
                      <button
                        onClick={handleGenerateAwarenessGreeting}
                        className="w-full py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-semibold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>将交接单智能转化为客服回复话术</span>
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div className="p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center space-y-2">
                  <FileText className="w-8 h-8 mx-auto text-slate-300" />
                  <div className="font-semibold text-slate-700 text-xs">当前会话尚未发生转接</div>
                  <p className="text-[11px] text-slate-400">
                    当客户要求转接人工或智能客服识别低置信度时，系统将生成完整上下文快照并在此展示。
                  </p>
                  <button
                    onClick={() => setShowReTransferModal(true)}
                    className="mt-2 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                  >
                    立即手动转接至专席
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Customer 360 & Vector Knowledge Lookup */}
          {rightTab === "profile" && (
            <div className="space-y-4">
              {activeSession ? (
                <>
                  {/* Profile Card */}
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 text-sm">{activeSession.customerProfile.name}</span>
                      <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                        {activeSession.customerProfile.vipLevel}
                      </span>
                    </div>
                    <div className="space-y-1.5 text-[11px] text-slate-600">
                      <div className="flex justify-between">
                        <span className="text-slate-400">联系电话:</span>
                        <span>{activeSession.customerProfile.phone || "138****8888"}</span>
                      </div>
                      {activeSession.customerProfile.orderId && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">关联订单号:</span>
                          <span className="font-mono text-blue-600 font-semibold">{activeSession.customerProfile.orderId}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span className="text-slate-400">主要诉求:</span>
                        <span className="font-medium text-slate-800">{activeSession.customerProfile.intent}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">情绪指标:</span>
                        <span className={activeSession.customerProfile.sentiment === "frustrated" ? "text-rose-600 font-bold" : "text-emerald-600 font-semibold"}>
                          {activeSession.customerProfile.sentiment === "frustrated" ? "急躁/不满 (重点关注)" : "平稳"}
                        </span>
                      </div>
                    </div>
                    <div className="pt-1 flex flex-wrap gap-1">
                      {activeSession.customerProfile.tags.map((t, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-slate-200/80 text-slate-700 text-[10px] rounded">
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Long-term Memory Summary */}
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-semibold text-slate-700">
                      <span className="flex items-center gap-1">
                        <FileText className="w-3.5 h-3.5 text-blue-600" />
                        会话记忆摘要 (Memory)
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-100 leading-relaxed font-sans">
                      {activeSession.summaryMemory || "新会话建立，尚无记忆积累。"}
                    </p>
                  </div>

                  {/* Quick Vector Knowledge Query */}
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5">
                    <div className="text-[11px] font-semibold text-slate-700 flex items-center gap-1">
                      <Search className="w-3.5 h-3.5 text-indigo-600" />
                      知识库即时向量检索
                    </div>
                    <div className="flex gap-1.5">
                      <input
                        type="text"
                        value={quickSearchQuery}
                        onChange={(e) => setQuickSearchQuery(e.target.value)}
                        placeholder="输入关键词或政策问题..."
                        className="flex-1 px-2.5 py-1 text-xs bg-white border border-slate-200 rounded-lg focus:outline-hidden"
                      />
                      <button
                        onClick={() => handleQuickKnowledgeSearch(quickSearchQuery)}
                        className="px-2.5 py-1 bg-indigo-600 text-white text-xs rounded-lg cursor-pointer hover:bg-indigo-700"
                      >
                        检索
                      </button>
                    </div>

                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {quickSearchResults.map((r: any, idx: number) => (
                        <div key={idx} className="p-2 bg-white rounded border border-slate-200 text-[11px]">
                          <div className="flex justify-between font-semibold text-slate-800 mb-1">
                            <span>{r.doc.title}</span>
                            <span className="text-indigo-600 text-[10px]">{(r.score * 100).toFixed(0)}%</span>
                          </div>
                          <p className="text-slate-600 text-[10px] line-clamp-2">{r.doc.content}</p>
                          <button
                            onClick={() => setAgentInput(agentInput + "\n" + r.doc.content)}
                            className="mt-1 text-[10px] text-blue-600 hover:underline cursor-pointer"
                          >
                            + 插入到输入框
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-slate-400">暂无选中的客户会话</p>
              )}
            </div>
          )}

          {/* TAB 3: Global Transfer Audit Logs */}
          {rightTab === "logs" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500 pb-1 border-b border-slate-200">
                <span>全渠道转接流水审计日志</span>
                <span className="font-mono text-[10px]">共 {transferLogs.length} 条</span>
              </div>

              {transferLogs.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-xs">
                  暂无转接日志记录
                </div>
              ) : (
                <div className="space-y-2.5">
                  {transferLogs.map((log) => {
                    const isForCurrent = log.sessionId === activeSession?.id;
                    return (
                      <div
                        key={log.id}
                        onClick={() => {
                          if (log.sessionId !== activeSession?.id) {
                            onSelectSession(log.sessionId);
                          }
                          setRightTab("dossier");
                        }}
                        className={`p-3 rounded-xl border transition-all cursor-pointer ${
                          isForCurrent 
                            ? "bg-amber-50/70 border-amber-300 ring-1 ring-amber-200" 
                            : "bg-white border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-800 text-xs">{log.customerName}</span>
                            <span className="text-[10px] text-slate-400 font-mono">({log.vipLevel})</span>
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            log.triggerType === "ai_fallback" 
                              ? "bg-rose-50 text-rose-700 border border-rose-200" 
                              : "bg-blue-50 text-blue-700 border border-blue-200"
                          }`}>
                            {log.triggerType === "ai_fallback" ? "无法回答" : "主动转人工"}
                          </span>
                        </div>

                        <div className="text-[11px] text-slate-600 mb-1 leading-snug">
                          {log.reason}
                        </div>

                        <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                          <div className="flex items-center gap-1">
                            <UserCheck className="w-3 h-3 text-slate-500" />
                            <span>{log.assignedAgentName} ({log.assignedDepartment})</span>
                          </div>
                          <span className="font-mono">{log.transferredAt}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Re-Transfer Modal (Forward to Colleague) */}
      {showReTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Forward className="w-5 h-5 text-amber-600" />
                <div>
                  <h3 className="font-bold text-slate-800 text-sm">流转改派其他专职坐席 (Re-Transfer)</h3>
                  <p className="text-[11px] text-slate-500">将包含提问历史、客服答复与记忆的完整上下文交接单转派给同事</p>
                </div>
              </div>
              <button
                onClick={() => setShowReTransferModal(false)}
                className="p-1 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              {/* Select Agent */}
              <div className="space-y-2">
                <label className="font-semibold text-slate-700">选择接收坐席：</label>
                <div className="grid grid-cols-2 gap-2 max-h-44 overflow-y-auto">
                  {availableAgents.map((agent) => (
                    <div
                      key={agent.id}
                      onClick={() => setReTransferAgentId(agent.id)}
                      className={`p-2.5 rounded-xl border cursor-pointer transition-all ${
                        reTransferAgentId === agent.id 
                          ? "bg-amber-50 border-amber-400 ring-2 ring-amber-200" 
                          : "bg-white border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-slate-800">{agent.name}</span>
                        <span className="text-[10px] text-slate-500">{agent.department}</span>
                      </div>
                      <div className="text-[10px] text-slate-400">{agent.title}</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {agent.specialties.slice(0, 2).map((s, idx) => (
                          <span key={idx} className="px-1 bg-slate-100 text-slate-600 text-[9px] rounded">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Transfer Reason */}
              <div className="space-y-1">
                <label className="font-semibold text-slate-700">改派流转原因：</label>
                <input
                  type="text"
                  value={reTransferReason}
                  onChange={(e) => setReTransferReason(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                />
              </div>

              {/* Transfer Note */}
              <div className="space-y-1">
                <label className="font-semibold text-slate-700">交接附言与重点提醒（写入审计快照）：</label>
                <textarea
                  rows={2}
                  value={reTransferNote}
                  onChange={(e) => setReTransferNote(e.target.value)}
                  placeholder="如：客户已核对顺丰单号，请直接协助办理增值税专票重开"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs resize-none"
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-2">
              <button
                onClick={() => setShowReTransferModal(false)}
                className="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-xl cursor-pointer text-xs"
              >
                取消
              </button>
              <button
                onClick={handleExecuteReTransfer}
                disabled={reTransferring}
                className="px-5 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-bold rounded-xl shadow-xs cursor-pointer text-xs flex items-center gap-1.5"
              >
                {reTransferring ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>正在交接流转...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>确认无缝流转</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
