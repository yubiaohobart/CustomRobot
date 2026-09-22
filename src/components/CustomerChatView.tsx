import React, { useState, useEffect, useRef } from "react";
import { 
  Send, 
  Bot, 
  User, 
  Headphones, 
  Sparkles, 
  BookOpen, 
  AlertCircle, 
  RefreshCw, 
  ShieldCheck, 
  Activity, 
  HelpCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  ArrowRightLeft,
  CheckCircle2,
  UserCheck,
  Clock,
  FileText,
  Check,
  X,
  ShieldAlert,
  Star
} from "lucide-react";
import { ChatMessage, ConversationSession, AvailableAgent, TransferTriggerType, TransferLog } from "../types";

interface CustomerChatViewProps {
  currentSessionId: string;
  onSelectSession: (id: string) => void;
  onInterventionAlert?: () => void;
}

export const CustomerChatView: React.FC<CustomerChatViewProps> = ({
  currentSessionId,
  onSelectSession,
  onInterventionAlert,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<ConversationSession | null>(null);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [expandedRefId, setExpandedRefId] = useState<string | null>(null);
  const [showMemoryPanel, setShowMemoryPanel] = useState(true);

  // Seamless Transfer State
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [availableAgents, setAvailableAgents] = useState<AvailableAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("agent_108");
  const [transferReason, setTransferReason] = useState<string>("智能客服置信度不足，无法准确回答当前诉求");
  const [transferTriggerType, setTransferTriggerType] = useState<TransferTriggerType>("ai_fallback");
  const [transferNote, setTransferNote] = useState<string>("");
  const [transferring, setTransferring] = useState(false);
  const [transferSuccessToast, setTransferSuccessToast] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchSession = async () => {
    try {
      const res = await fetch(`/api/sessions/${currentSessionId}`);
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        setMessages(data.session.messages || []);
      }
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch("/api/agents");
      if (res.ok) {
        const data = await res.json();
        setAvailableAgents(data.agents || []);
      }
    } catch (err) {
      console.error("Failed to load agents:", err);
    }
  };

  useEffect(() => {
    fetchSession();
    fetchAgents();
    const interval = setInterval(fetchSession, 3000);
    return () => clearInterval(interval);
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || loading) return;

    setInputMessage("");
    setLoading(true);

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: currentSessionId,
          message: text,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.session) {
          setSession(data.session);
          setMessages(data.session.messages || []);
        } else {
          await fetchSession();
        }
        if (data.escalatedToHuman && onInterventionAlert) {
          onInterventionAlert();
        }
      } else {
        throw new Error("Chat request failed");
      }
    } catch (err) {
      console.error("Error sending message:", err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "system",
        content: "消息发送超时或服务异常，请稍后重试或尝试刷新会话。",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearSession = async () => {
    try {
      await fetch(`/api/sessions/${currentSessionId}/clear`, { method: "POST" });
      await fetchSession();
    } catch (e) {
      console.error(e);
    }
  };

  // Open transfer modal with smart defaults
  const handleOpenTransfer = (triggerType: TransferTriggerType = "user_requested", defaultReason?: string) => {
    setTransferTriggerType(triggerType);
    if (defaultReason) {
      setTransferReason(defaultReason);
    } else if (triggerType === "ai_fallback") {
      setTransferReason("智能客服无法回答当前业务疑问，需要人工介入");
    } else {
      setTransferReason("用户主动要求转接指定人工客服处理");
    }
    
    // Choose recommended agent based on session intent
    if (session?.customerProfile.intent.includes("退款") || session?.customerProfile.intent.includes("退货")) {
      setSelectedAgentId("agent_102"); // 李雪
    } else if (session?.customerProfile.intent.includes("发票") || session?.customerProfile.intent.includes("税")) {
      setSelectedAgentId("agent_105"); // 赵林
    } else if (session?.customerProfile.intent.includes("安全") || session?.customerProfile.intent.includes("密码")) {
      setSelectedAgentId("agent_110"); // 孙浩
    } else {
      setSelectedAgentId("agent_108"); // 陈主管 (VIP)
    }

    setShowTransferModal(true);
  };

  // Execute Seamless Transfer API Call
  const handleExecuteTransfer = async () => {
    if (!session || transferring) return;
    setTransferring(true);
    try {
      const res = await fetch(`/api/sessions/${currentSessionId}/transfer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetAgentId: selectedAgentId,
          reason: transferReason,
          triggerType: transferTriggerType,
          operatorNote: transferNote,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        setMessages(data.session.messages);
        setShowTransferModal(false);
        setTransferSuccessToast(`已无缝转接至 ${data.transferLog.assignedDepartment} · ${data.transferLog.assignedAgentName}`);
        setTimeout(() => setTransferSuccessToast(null), 4000);
        if (onInterventionAlert) onInterventionAlert();
      } else {
        const errData = await res.json();
        alert(errData.error || "转接人工失败");
      }
    } catch (e) {
      console.error(e);
      alert("转接服务请求异常");
    } finally {
      setTransferring(false);
    }
  };

  const isHumanServing = session?.status === "HUMAN_INTERVENED";
  const needsIntervention = session?.status === "NEEDS_INTERVENTION";

  const quickQuestions = [
    "7天无理由退货的运费谁承担？黄金会员有免运费权益吗？",
    "哪些特殊商品不支持7天无理由退换货？定制和生鲜可以退吗？",
    "退货后质检合格退款大概几天到账？微信零钱和借记卡一样吗？",
    "电子产品全国联保多久？15天内硬件坏了能换新机吗？",
    "人工客服！处理售后争议，马上帮我转人工！",
  ];

  // Selected agent object
  const activeSelectedAgent = availableAgents.find(a => a.id === selectedAgentId) || availableAgents[0];

  return (
    <div className="flex h-[calc(100vh-4.5rem)] w-full overflow-hidden bg-slate-50 relative">
      {/* Toast Notification */}
      {transferSuccessToast && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white text-xs font-semibold rounded-xl shadow-lg border border-emerald-500 animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-200" />
          <span>{transferSuccessToast}</span>
          <span className="text-emerald-100 text-[11px]">（完整问答上下文与长期记忆已就绪）</span>
        </div>
      )}

      {/* Main Chat Box */}
      <div className="flex flex-1 flex-col h-full bg-white border-r border-slate-200">
        {/* Chat Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-white/95 backdrop-blur-xs">
          <div className="flex items-center gap-3">
            <div className={`relative flex items-center justify-center w-10 h-10 rounded-xl font-semibold shadow-xs ${
              isHumanServing 
                ? "bg-amber-500 text-white" 
                : "bg-blue-600 text-white"
            }`}>
              {isHumanServing ? <Headphones className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full"></span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-800">
                  {isHumanServing ? "人工专属客服服务中" : "IntelliServe 智能客服助手"}
                </h2>
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                  isHumanServing 
                    ? "bg-amber-100 text-amber-800 border border-amber-200" 
                    : needsIntervention
                    ? "bg-rose-100 text-rose-800 border border-rose-200 animate-pulse"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                }`}>
                  {isHumanServing 
                    ? `已由 ${session?.assignedAgent || "人工坐席"} 接管` 
                    : needsIntervention 
                    ? "待人工接入（高危预警）" 
                    : "LangGraph AI 自主接待中"}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                向量数据库知识召回 • 状态机记忆管理 • 完整上下文无缝人工介入转接
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!isHumanServing ? (
              <button
                id="btn-request-human"
                onClick={() => handleOpenTransfer("user_requested", "客户在对话中主动申请转接指定人工客服")}
                className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-amber-800 bg-gradient-to-r from-amber-50 to-orange-50 hover:from-amber-100 hover:to-orange-100 border border-amber-300 rounded-lg transition-all shadow-2xs cursor-pointer"
              >
                <Headphones className="w-3.5 h-3.5 text-amber-600" />
                <span>无缝转接人工客服</span>
              </button>
            ) : (
              <button
                id="btn-retransfer-human"
                onClick={() => handleOpenTransfer("manual_dispatch", "改派/二次转交指定人工坐席")}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors cursor-pointer"
              >
                <ArrowRightLeft className="w-3.5 h-3.5 text-slate-500" />
                <span>转接其他坐席</span>
              </button>
            )}

            <button
              id="btn-toggle-memory"
              onClick={() => setShowMemoryPanel(!showMemoryPanel)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer"
            >
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              {showMemoryPanel ? "收起记忆" : "查看记忆"}
            </button>

            <button
              id="btn-clear-chat"
              onClick={handleClearSession}
              title="清空会话历史"
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50/50">
          {/* Welcome Banner */}
          <div className="mx-auto max-w-2xl p-4 bg-white rounded-xl border border-slate-200/80 shadow-xs">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-slate-800">您好！我是企业智能客服助手</h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                  已连接企业高维向量知识库与 LangGraph 会话记忆管理系统。当遇到复杂个性化问题或智能客服无法解答时，系统提供<strong>无缝人工介入接口</strong>，将全部用户提问、客服回答及会话记忆同步移交指定坐席，无需您重复描述。
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="text-xs text-slate-400 self-center mr-1">快捷测试：</span>
                  {quickQuestions.slice(0, 3).map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(q)}
                      className="px-2.5 py-1 text-xs text-blue-700 bg-blue-50/80 hover:bg-blue-100/90 rounded-md border border-blue-100 transition-colors cursor-pointer"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Messages */}
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            const isHumanAgent = msg.role === "human_agent";
            const isSystem = msg.role === "system";

            if (isSystem) {
              const isTransferNotice = msg.content.includes("转接");
              return (
                <div key={msg.id} className="flex justify-center my-3">
                  <div className={`flex items-center gap-2 px-4 py-2 text-xs rounded-xl shadow-2xs border ${
                    isTransferNotice
                      ? "bg-amber-50/95 border-amber-300 text-amber-900"
                      : "bg-slate-100 border-slate-200 text-slate-700"
                  }`}>
                    {isTransferNotice ? (
                      <UserCheck className="w-4 h-4 text-amber-600 flex-shrink-0" />
                    ) : (
                      <ShieldCheck className="w-4 h-4 text-slate-500 flex-shrink-0" />
                    )}
                    <div className="leading-tight">
                      <span className="font-medium">{msg.content}</span>
                      <span className="text-amber-600 text-[10px] ml-2 font-mono">{msg.timestamp}</span>
                    </div>
                  </div>
                </div>
              );
            }

            // Low confidence check (< 0.65) or explicit transfer indicator
            const isLowConfidence = msg.role === "assistant" && msg.confidenceScore !== undefined && msg.confidenceScore < 0.65;

            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
              >
                {/* Avatar */}
                <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold shadow-xs ${
                  isUser 
                    ? "bg-slate-700 text-white" 
                    : isHumanAgent
                    ? "bg-amber-600 text-white"
                    : "bg-blue-600 text-white"
                }`}>
                  {isUser ? <User className="w-4 h-4" /> : isHumanAgent ? <Headphones className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Bubble Container */}
                <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} max-w-[85%]`}>
                  {/* Sender Tag */}
                  <div className="flex items-center gap-2 mb-1 text-[11px] text-slate-400">
                    <span>
                      {isUser 
                        ? "您" 
                        : isHumanAgent 
                        ? (session?.assignedAgent || "人工专属客服")
                        : "IntelliServe AI"}
                    </span>
                    <span>{msg.timestamp}</span>
                    {msg.confidenceScore !== undefined && !isUser && (
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${
                        msg.confidenceScore >= 0.75 
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200" 
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}>
                        置信度: {(msg.confidenceScore * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>

                  {/* Message Bubble */}
                  <div className={`p-4 rounded-2xl text-sm leading-relaxed ${
                    isUser
                      ? "bg-blue-600 text-white rounded-tr-xs"
                      : isHumanAgent
                      ? "bg-amber-50/90 text-slate-800 border border-amber-200/80 rounded-tl-xs shadow-xs"
                      : "bg-white text-slate-800 border border-slate-200/90 rounded-tl-xs shadow-xs"
                  }`}>
                    {isHumanAgent && (
                      <div className="flex items-center gap-1.5 text-xs text-amber-800 font-semibold mb-1.5 pb-1.5 border-b border-amber-200/60">
                        <Headphones className="w-3.5 h-3.5" />
                        <span>人工客服专员实时回复：</span>
                      </div>
                    )}
                    <p className="whitespace-pre-wrap">{msg.content}</p>

                    {/* Reference Sources Accordion (RAG hits) */}
                    {msg.references && msg.references.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-100">
                        <button
                          onClick={() => setExpandedRefId(expandedRefId === msg.id ? null : msg.id)}
                          className="flex items-center justify-between w-full text-xs text-blue-700 hover:text-blue-800 font-medium cursor-pointer"
                        >
                          <span className="flex items-center gap-1">
                            <BookOpen className="w-3.5 h-3.5" />
                            参考企业知识库条目 ({msg.references.length}条相关文档)
                          </span>
                          {expandedRefId === msg.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        {expandedRefId === msg.id && (
                          <div className="mt-2 space-y-1.5">
                            {msg.references.map((ref) => (
                              <div key={ref.id} className="p-2 bg-blue-50/60 rounded-lg text-xs border border-blue-100">
                                <div className="flex items-center justify-between font-medium text-blue-900">
                                  <span>{ref.title}</span>
                                  <span className="text-[10px] text-blue-600 bg-blue-100/80 px-1.5 py-0.5 rounded">
                                    相似度: {(ref.score * 100).toFixed(0)}%
                                  </span>
                                </div>
                                <p className="text-[11px] text-slate-600 mt-1 line-clamp-2">{ref.snippet}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Low Confidence or AI Fallback Human Transfer Prompt Card */}
                    {isLowConfidence && !isHumanServing && (
                      <div className="mt-3 p-3 bg-amber-50/80 border border-amber-200 rounded-xl space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                          <span>智能客服置信度不足（无法完全解答您的诉求）</span>
                        </div>
                        <p className="text-[11px] text-amber-700 leading-normal">
                          该问题可能需要人工核验或系统特批。系统支持将当前会话的全部历史问答与记忆，一键无缝转接给指定业务专员。
                        </p>
                        <button
                          onClick={() => handleOpenTransfer("ai_fallback", "智能客服置信度偏低，未能充分解答用户提问")}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer shadow-2xs"
                        >
                          <Headphones className="w-3.5 h-3.5" />
                          <span>一键无缝转接指定人工客服</span>
                        </button>
                      </div>
                    )}

                    {/* LangGraph Trace Inspector Toggle */}
                    {msg.stepTrace && msg.stepTrace.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <button
                          onClick={() => setExpandedTraceId(expandedTraceId === msg.id ? null : msg.id)}
                          className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-700 cursor-pointer"
                        >
                          <Activity className="w-3 h-3 text-indigo-500" />
                          <span>查看 LangGraph 执行流图与节点链路</span>
                          {expandedTraceId === msg.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        {expandedTraceId === msg.id && (
                          <div className="mt-2 p-2.5 bg-slate-900 text-slate-200 rounded-lg text-xs space-y-1.5 font-mono">
                            <div className="text-[11px] text-slate-400 font-sans font-medium flex items-center justify-between">
                              <span>LangGraph Pipeline State Transitions</span>
                              <span className="text-emerald-400">STATE_NORMAL</span>
                            </div>
                            {msg.stepTrace.map((st, sIdx) => (
                              <div key={sIdx} className="flex items-start gap-2 text-[11px] border-l-2 border-indigo-500 pl-2 py-0.5">
                                <span className="text-indigo-300 font-semibold">{st.node}</span>
                                <span className="text-slate-300 flex-1">{st.description}</span>
                                <span className="text-slate-400 text-[10px]">{st.durationMs}ms</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex gap-3 max-w-xl mr-auto">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
                <Bot className="w-4 h-4 animate-bounce" />
              </div>
              <div className="p-3 bg-white border border-slate-200 rounded-2xl rounded-tl-xs shadow-xs text-xs text-slate-600 flex items-center gap-2">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
                </div>
                <span>LangGraph 正在执行向量召回与融合推理...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompts Bar */}
        <div className="px-6 py-2 bg-white border-t border-slate-100 flex items-center gap-2 overflow-x-auto text-xs scrollbar-none">
          <span className="text-slate-400 whitespace-nowrap text-xs">快捷问答测试:</span>
          {quickQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(q)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full whitespace-nowrap transition-colors cursor-pointer text-xs"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-white border-t border-slate-200">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              id="customer-chat-input"
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={isHumanServing ? "已接通人工坐席，客服正在查看您的上下文背景，可直接在此发送..." : "请输入您想咨询的问题（例如：申请退款、补开发票、物流查询）..."}
              className="flex-1 px-4 py-3 bg-slate-100 hover:bg-slate-100/80 focus:bg-white text-sm text-slate-800 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
            />
            <button
              id="btn-send-message"
              type="submit"
              disabled={loading || !inputMessage.trim()}
              className="flex items-center justify-center gap-1.5 px-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-sm font-medium rounded-xl transition-colors shadow-xs cursor-pointer disabled:cursor-not-allowed"
            >
              <span>发送</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>支持中英文提问 • 输入【转人工】可唤起专属人工坐席转接</span>
            <span>当前会话 ID: {currentSessionId}</span>
          </div>
        </div>
      </div>

      {/* Right Collapsible Memory & LangGraph State Panel */}
      {showMemoryPanel && (
        <div className="w-80 h-full border-l border-slate-200 bg-white flex flex-col overflow-y-auto">
          <div className="p-4 border-b border-slate-200 bg-slate-50">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-blue-600" />
                会话状态与记忆监控
              </h3>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
          </div>

          <div className="p-4 space-y-4 text-xs">
            {/* Session Status Card */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <div className="text-slate-500 text-[11px]">当前服务模式</div>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-800 text-sm">
                  {isHumanServing ? "人工客服接管中" : needsIntervention ? "待人工介入介入" : "智能客服 (AI Agent)"}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  isHumanServing ? "bg-amber-100 text-amber-800" : needsIntervention ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"
                }`}>
                  {session?.status}
                </span>
              </div>
              {session?.assignedAgent && (
                <div className="text-[11px] text-amber-800 bg-amber-50 p-2 rounded-lg border border-amber-200/70">
                  <div>接管坐席: <strong className="font-semibold">{session.assignedAgent}</strong></div>
                  {session.latestTransfer && (
                    <div className="mt-1 text-[10px] text-amber-700">
                      转接时间: {session.latestTransfer.transferredAt} (流水号: {session.latestTransfer.id})
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Customer Profile Card */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <div className="text-slate-500 text-[11px]">用户画像与标签提取</div>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-500">客户身份:</span>
                  <span className="font-medium text-slate-800">{session?.customerProfile.name || "普通访客"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">会员等级:</span>
                  <span className="text-indigo-600 font-semibold">{session?.customerProfile.vipLevel || "普通会员"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">情绪指标:</span>
                  <span className={`font-semibold capitalize ${
                    session?.customerProfile.sentiment === "frustrated" ? "text-rose-600" : "text-emerald-600"
                  }`}>
                    {session?.customerProfile.sentiment === "frustrated" ? "焦急 / 负向 (需关注)" : "平稳 / 积极"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">识别主意图:</span>
                  <span className="text-slate-700 font-medium">{session?.customerProfile.intent || "常规查询"}</span>
                </div>
              </div>
              <div className="pt-2 flex flex-wrap gap-1">
                {session?.customerProfile.tags.map((tag, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-blue-100/70 text-blue-700 text-[10px] rounded">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>

            {/* Dynamic Conversation Summary (LangGraph Memory) */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">会话长期记忆摘要 (MemorySaver)</span>
                <span className="text-[10px] text-blue-600 font-mono">Auto-Summary</span>
              </div>
              <p className="text-[11px] text-slate-700 bg-white p-2.5 rounded-lg border border-slate-100 leading-relaxed font-sans">
                {session?.summaryMemory || "新会话建立，尚无摘要。"}
              </p>
            </div>

            {/* LangGraph Checkpoints History */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <div className="text-slate-500 text-[11px]">LangGraph 检查点快照 (Checkpoints)</div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {session?.checkpoints && session.checkpoints.length > 0 ? (
                  session.checkpoints.map((cp, idx) => (
                    <div key={idx} className="p-2 bg-white rounded border border-slate-100 text-[10px] font-mono">
                      <div className="flex justify-between text-slate-400 mb-0.5">
                        <span className="text-indigo-600 font-semibold">{cp.node}</span>
                        <span>{cp.timestamp}</span>
                      </div>
                      <div className="text-slate-600 truncate">
                        {JSON.stringify(cp.stateData)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-400 text-[10px] py-1">暂无持久化检查点数据</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ================= SEAMLESS HUMAN INTERVENTION TRANSFER MODAL ================= */}
      {showTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-white/20 rounded-xl">
                  <Headphones className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-base font-bold tracking-tight">无缝人工介入转接 (Seamless Transfer)</h3>
                  <p className="text-xs text-amber-100">
                    完整问答上下文、会话记忆与客户画像将全量移交指定人工坐席，客户免重复表述
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowTransferModal(false)}
                className="p-1 text-white/80 hover:text-white rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs">
              {/* Trigger Type & Reason */}
              <div className="space-y-2">
                <label className="text-slate-700 font-bold text-xs flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-amber-600" />
                  <span>转接原因与触发机制</span>
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setTransferTriggerType("ai_fallback");
                      setTransferReason("智能客服无法回答当前业务疑问 / 置信度不足");
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      transferTriggerType === "ai_fallback"
                        ? "bg-amber-50 border-amber-400 text-amber-900 ring-2 ring-amber-200"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <div className="font-semibold text-xs mb-0.5">智能客服无法解答</div>
                    <div className="text-[10px] text-slate-500">置信度不足或超出知识库范围</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setTransferTriggerType("user_requested");
                      setTransferReason("客户主动要求转接指定人工客服");
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      transferTriggerType === "user_requested"
                        ? "bg-amber-50 border-amber-400 text-amber-900 ring-2 ring-amber-200"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <div className="font-semibold text-xs mb-0.5">用户主动要求</div>
                    <div className="text-[10px] text-slate-500">客户显式输入转人工或呼叫</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setTransferTriggerType("sentiment_alert");
                      setTransferReason("客户情绪焦急，申请资深主管特批处理");
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      transferTriggerType === "sentiment_alert"
                        ? "bg-amber-50 border-amber-400 text-amber-900 ring-2 ring-amber-200"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <div className="font-semibold text-xs mb-0.5">高危争议/情绪关怀</div>
                    <div className="text-[10px] text-slate-500">投诉预警或需要资深权限</div>
                  </button>
                </div>

                <input
                  type="text"
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  placeholder="转接详细说明（例如：退款超期质检催办、专票重开资质审核）"
                  className="w-full px-3 py-2 bg-slate-50 text-slate-800 rounded-lg border border-slate-200 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-amber-500 text-xs"
                />
              </div>

              {/* Target Agent Selection */}
              <div className="space-y-2">
                <label className="text-slate-700 font-bold text-xs flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-blue-600" />
                    <span>指定人工客服坐席</span>
                  </span>
                  <span className="text-[11px] text-slate-400 font-normal">系统已根据客户意图智能推荐最佳坐席</span>
                </label>
                
                <div className="grid grid-cols-2 gap-2.5">
                  {availableAgents.map((agent) => {
                    const isSelected = selectedAgentId === agent.id;
                    return (
                      <div
                        key={agent.id}
                        onClick={() => setSelectedAgentId(agent.id)}
                        className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                          isSelected 
                            ? "bg-amber-50/70 border-amber-400 ring-2 ring-amber-300/60 shadow-xs" 
                            : "bg-white border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-amber-600 text-white font-bold flex items-center justify-center text-xs shadow-2xs">
                              {agent.name.slice(0, 1)}
                            </div>
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="font-bold text-slate-800 text-xs">{agent.name}</span>
                                <span className="text-[10px] text-slate-500">({agent.title})</span>
                              </div>
                              <div className="text-[10px] text-slate-400">{agent.department}</div>
                            </div>
                          </div>

                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            agent.status === "IDLE" 
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200" 
                              : "bg-amber-50 text-amber-700 border border-amber-200"
                          }`}>
                            {agent.status === "IDLE" ? "空闲" : "忙碌中(2单)"}
                          </span>
                        </div>

                        <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap gap-1">
                          {agent.specialties.slice(0, 2).map((sp, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 bg-slate-100 text-slate-600 text-[10px] rounded">
                              {sp}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Transferred Context Snapshot Dossier Preview */}
              <div className="p-3.5 bg-blue-50/60 rounded-xl border border-blue-100 space-y-2">
                <div className="flex items-center justify-between text-blue-900 font-semibold text-xs">
                  <span className="flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-blue-600" />
                    <span>完整移交上下文数据包预览 (Context Package)</span>
                  </span>
                  <span className="text-[10px] text-blue-600 font-mono bg-blue-100 px-2 py-0.5 rounded-full">
                    全量同步 • 免重复表述
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-blue-100">
                  <div>
                    <span className="text-slate-400">客户信息：</span>
                    <strong className="text-slate-800">{session?.userName} ({session?.customerProfile.vipLevel})</strong>
                  </div>
                  <div>
                    <span className="text-slate-400">当前意图：</span>
                    <strong className="text-slate-800">{session?.customerProfile.intent}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400">移交提问：</span>
                    <span className="text-indigo-600 font-semibold">
                      已打包全部 {messages.filter(m => m.role === "user").length} 条用户提问
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">长期记忆：</span>
                    <span className="text-slate-700 truncate inline-block max-w-[150px]">
                      {session?.summaryMemory ? session.summaryMemory.slice(0, 25) + "..." : "会话建立初期"}
                    </span>
                  </div>
                </div>

                <p className="text-[10px] text-blue-700 leading-normal">
                  📌 <strong>无缝保障机制：</strong>点击转接后，上述提问历史、客服回答及长期记忆将一并注入到该坐席的【上下文交接单】中，系统并在审计日志记录转接流水号。
                </p>
              </div>

              {/* Optional Operator Note */}
              <div className="space-y-1">
                <label className="text-slate-600 text-xs">客户特别交接附言（可选）：</label>
                <input
                  type="text"
                  value={transferNote}
                  onChange={(e) => setTransferNote(e.target.value)}
                  placeholder="例如：客户希望10分钟内收到退款凭证，顺丰包裹已签收。"
                  className="w-full px-3 py-2 bg-slate-50 text-slate-800 rounded-lg border border-slate-200 focus:bg-white focus:outline-hidden text-xs"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="text-slate-500 text-xs">
                接收坐席: <strong className="text-slate-800">{activeSelectedAgent?.name}</strong> ({activeSelectedAgent?.department})
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowTransferModal(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleExecuteTransfer}
                  disabled={transferring}
                  className="flex items-center gap-1.5 px-5 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 rounded-xl transition-all shadow-xs cursor-pointer"
                >
                  {transferring ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>正在全量同步上下文并移交...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>确认无缝转接</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
