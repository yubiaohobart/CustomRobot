import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Bot,
  User,
  Headphones,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Package,
  Truck,
  ArrowRightLeft,
  Clock,
  Zap,
  ShieldCheck,
  Tag,
  ChevronRight,
  Smile,
  ShieldAlert,
  Volume2
} from "lucide-react";
import { ConversationSession, ChatMessage, OrderData } from "../types";

export const DualChatView: React.FC = () => {
  const [selectedSessionId, setSelectedSessionId] = useState("session_user_001");
  const [session, setSession] = useState<ConversationSession | null>(null);
  const [sessionsList, setSessionsList] = useState<ConversationSession[]>([]);

  // Customer Side State
  const [customerInput, setCustomerInput] = useState("");
  const [customerLoading, setCustomerLoading] = useState(false);
  const [customerTyping, setCustomerTyping] = useState(false);
  const [agentTypingNotice, setAgentTypingNotice] = useState<string | null>(null);

  // Agent Side State
  const [agentInput, setAgentInput] = useState("");
  const [agentSending, setAgentSending] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotDraft, setCopilotDraft] = useState<string | null>(null);
  const [customerTypingNotice, setCustomerTypingNotice] = useState<string | null>(null);

  // Live Toast & WebSocket
  const [toast, setToast] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const customerMessagesEndRef = useRef<HTMLDivElement>(null);
  const agentMessagesEndRef = useRef<HTMLDivElement>(null);

  const showToast = (text: string) => {
    setToast(text);
    setTimeout(() => setToast(null), 3500);
  };

  // Fetch Session Data
  const loadSession = async (sid = selectedSessionId) => {
    try {
      const res = await fetch(`/api/sessions/${sid}`);
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
      }
    } catch (e) {
      console.error("loadSession error:", e);
    }
  };

  const loadAllSessions = async () => {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessionsList(data.sessions || []);
      }
    } catch (e) {
      console.error("loadAllSessions error:", e);
    }
  };

  useEffect(() => {
    loadSession();
    loadAllSessions();
    const interval = setInterval(() => {
      loadSession();
      loadAllSessions();
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedSessionId]);

  // WebSocket Live Connection
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let ws: WebSocket;
    let agentTypingTimeout: any = null;
    let customerTypingTimeout: any = null;

    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({
          type: "join",
          sessionId: selectedSessionId,
          role: "dual_observer",
          name: "同屏双向观测台"
        }));
      };

      ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.type === "message:new" && payload.sessionId === selectedSessionId) {
            setSession((prev) => {
              if (!prev) return payload.session;
              const exists = prev.messages.some((m) => m.id === payload.message.id);
              if (exists) return prev;
              return {
                ...prev,
                messages: [...prev.messages, payload.message],
                status: payload.session?.status || prev.status,
                assignedAgent: payload.session?.assignedAgent || prev.assignedAgent
              };
            });
            if (payload.message.role === "human_agent") {
              showToast(`🎧 人工坐席【${payload.message.agentName || "陈浩"}】已回复客户`);
            } else if (payload.message.role === "user") {
              showToast(`👤 收到客户【${session?.customerProfile?.name || "客户"}】新提问`);
            }
          } else if (payload.type === "session:update" && (payload.sessionId === selectedSessionId || payload.session?.id === selectedSessionId)) {
            setSession(payload.session);
          } else if (payload.type === "typing" && payload.sessionId === selectedSessionId) {
            if (payload.sender === "agent") {
              setAgentTypingNotice(payload.isTyping ? "人工坐席正在输入..." : null);
              clearTimeout(agentTypingTimeout);
              if (payload.isTyping) agentTypingTimeout = setTimeout(() => setAgentTypingNotice(null), 3500);
            } else if (payload.sender === "customer") {
              setCustomerTypingNotice(payload.isTyping ? "客户正在输入..." : null);
              clearTimeout(customerTypingTimeout);
              if (payload.isTyping) customerTypingTimeout = setTimeout(() => setCustomerTypingNotice(null), 3500);
            }
          }
        } catch (e) {
          // ignore
        }
      };
    } catch (e) {
      // fallback
    }

    return () => {
      if (wsRef.current) wsRef.current.close();
      clearTimeout(agentTypingTimeout);
      clearTimeout(customerTypingTimeout);
    };
  }, [selectedSessionId]);

  useEffect(() => {
    customerMessagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    agentMessagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages]);

  // Customer Send Action
  const handleCustomerSend = async (customText?: string) => {
    const text = (customText || customerInput).trim();
    if (!text || customerLoading) return;

    setCustomerInput("");
    setCustomerLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: selectedSessionId,
          message: text,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.session) {
          setSession(data.session);
        } else {
          await loadSession();
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCustomerLoading(false);
    }
  };

  // Agent Send Action
  const handleAgentSend = async (customText?: string) => {
    const text = (customText || agentInput).trim();
    if (!text || agentSending) return;

    setAgentSending(true);
    try {
      const res = await fetch(`/api/sessions/${selectedSessionId}/human-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          agentName: session?.assignedAgent || "陈浩 (高级售后督导)",
          agentId: session?.assignedAgentId || "agent_101",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        setAgentInput("");
        setCopilotDraft(null);
        showToast("已成功向客户发送人工答复！");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAgentSending(false);
    }
  };

  // Customer Requests Human
  const handleCustomerRequestHuman = async () => {
    try {
      const res = await fetch(`/api/sessions/${selectedSessionId}/transfer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetAgentId: "agent_101",
          reason: "客户在界面中一键申请人工坐席 1 对 1 服务",
          triggerType: "user_requested"
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        showToast("已成功接通人工坐席【陈浩】！");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Agent Takeover Action
  const handleAgentTakeover = async () => {
    try {
      const res = await fetch(`/api/sessions/${selectedSessionId}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "takeover", agentName: "陈浩 (高级售后督导)", agentId: "agent_101" }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        showToast("坐席【陈浩】已主动接入并接管会话！");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Agent Release Action (Hand back to AI)
  const handleAgentRelease = async () => {
    try {
      const res = await fetch(`/api/sessions/${selectedSessionId}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "release" }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data.session);
        showToast("会话已交还 AI 智能客服托管");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Agent Copilot Suggestion
  const handleGenerateCopilot = async () => {
    setCopilotLoading(true);
    try {
      const res = await fetch("/api/generate-suggestion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: selectedSessionId }),
      });
      if (res.ok) {
        const data = await res.json();
        setCopilotDraft(data.suggestion);
        setAgentInput(data.suggestion);
        showToast("✨ AI 副驾驶已自动生成专业售后话术草稿！");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCopilotLoading(false);
    }
  };

  const isHumanActive = session?.status === "HUMAN_INTERVENED";
  const needsHuman = session?.status === "NEEDS_INTERVENTION";

  const cannedResponses = [
    { label: "黄金免邮", text: "王女士您好！已为您核验会员权益：您是黄金会员，享有平台全额补贴的专属“退货免运费”权益，无需您垫付任何运费，我马上为您生成免邮寄回面单！" },
    { label: "48h退款时效", text: "您好！仓库收到商品后48小时内质检入库，合格后系统原路退回：支付宝/微信零钱实时到账，银行卡1-3个工作日到账。已为您标记加急审核！" },
    { label: "顺丰上门", text: "已为您预约顺丰速运明天上午9:00-11:00上门取件，快递员会携带专用包装上门，请保持手机畅通！" },
    { label: "定制破损先行赔付", text: "张先生您好！定制商品虽非质量问题不支持7天无理由退款，但针对运输碎裂破损，商城提供全额包赔与极速拍照补发，您无需担忧！" },
  ];

  const quickCustomerPrompts = [
    "我想申请退货，退货运费谁出？",
    "人工客服，马上帮我转接人工处理！",
    "我退货回去后大概几天能收到退款？",
    "帮我查一下扫地机器人顺丰到哪了？",
  ];

  return (
    <div className="flex flex-col h-full w-full bg-slate-100 overflow-hidden font-sans">
      {/* Toast Notification */}
      {toast && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-xl shadow-xl border border-slate-700 animate-in fade-in slide-in-from-top-2">
          <Volume2 className="w-4 h-4 text-amber-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Top Banner Toolbar */}
      <div className="h-13 bg-white border-b border-slate-200 px-5 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg text-xs font-bold shadow-xs">
            <ArrowRightLeft className="w-3.5 h-3.5" />
            <span>客户 ⟷ 人工客服 同屏实时双向对话</span>
          </div>
          <span className="text-xs text-slate-500 hidden md:inline">
            左侧模拟真实客户终端 • 右侧为专属人工客服坐席 • WebSocket 毫秒级双向同步
          </span>
        </div>

        {/* Switch Session */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">体验会话:</span>
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            className="px-3 py-1 text-xs bg-slate-50 hover:bg-slate-100 text-slate-800 font-medium rounded-lg border border-slate-200 focus:outline-hidden cursor-pointer"
          >
            <option value="session_user_001">王女士 (黄金会员 - 扫地机器人退换争议)</option>
            <option value="session_user_002">张先生 (普通会员 - 定制紫砂壶退款咨询)</option>
            <option value="session_user_003">刘总 (钻石VIP - 4K投影仪售后质检中)</option>
            <option value="session_guest_new">新访客会话 (空白全新会话)</option>
          </select>
          <button
            onClick={() => {
              loadSession();
              showToast("已刷新当前会话状态");
            }}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            title="刷新数据"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Split Screen Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* ============================================================== */}
        {/* LEFT COLUMN: CUSTOMER CHAT CLIENT (客户侧对话端) */}
        {/* ============================================================== */}
        <div className="w-1/2 flex flex-col h-full border-r border-slate-300 bg-white">
          {/* Customer Header */}
          <div className="px-5 py-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50/40 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                <User className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-slate-900">
                    客户体验视窗 · {session?.customerProfile?.name || "客户"}
                  </span>
                  <span className="px-2 py-0.2 bg-blue-100 text-blue-800 text-[10px] font-bold rounded-full">
                    {session?.customerProfile?.vipLevel || "黄金会员"}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                  <span>订单: {session?.customerProfile?.orderId || "ORD-2026-88992"}</span>
                  <span>•</span>
                  <span>模拟消费者在商城的移动端/网页客服界面</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {!isHumanActive ? (
                <button
                  onClick={handleCustomerRequestHuman}
                  className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-semibold rounded-lg shadow-xs transition-all cursor-pointer animate-pulse"
                >
                  <Headphones className="w-3.5 h-3.5" />
                  <span>呼叫人工客服</span>
                </button>
              ) : (
                <span className="flex items-center gap-1 px-2.5 py-1 bg-amber-100 border border-amber-300 text-amber-900 text-xs font-bold rounded-lg">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                  <span>人工【{session?.assignedAgent || "陈浩"}】专属服务中</span>
                </span>
              )}
            </div>
          </div>

          {/* Customer Service Banner */}
          {isHumanActive ? (
            <div className="bg-amber-500 text-white px-4 py-2 flex items-center justify-between text-xs font-medium shadow-2xs">
              <div className="flex items-center gap-2">
                <Headphones className="w-4 h-4 text-amber-100" />
                <span>
                  您好，售后高级督导<strong>【{session?.assignedAgent || "陈浩"}】</strong>已为您接入，全权处理售后争议与退款
                </span>
              </div>
              <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded text-white font-mono">
                1对1 在线直通
              </span>
            </div>
          ) : needsHuman ? (
            <div className="bg-rose-500 text-white px-4 py-2 flex items-center justify-between text-xs font-medium shadow-2xs">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-100 animate-bounce" />
                <span>
                  已发起人工转接，客服专员正从工作台快速接入，请稍候...
                </span>
              </div>
              <button
                onClick={handleAgentTakeover}
                className="text-[10px] bg-white text-rose-800 font-bold px-2 py-0.5 rounded hover:bg-rose-100 transition-colors cursor-pointer"
              >
                工作台快速接听
              </button>
            </div>
          ) : (
            <div className="bg-blue-50 border-b border-blue-100 text-blue-800 px-4 py-1.5 flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-1">
                <Bot className="w-3.5 h-3.5 text-blue-600" />
                <span>智能客服 (LangGraph + Qdrant 知识库) 自主接待中</span>
              </span>
              <span className="text-blue-600">随时可输入“转人工”</span>
            </div>
          )}

          {/* Customer Messages Flow */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-50/70">
            {session?.messages?.map((msg: ChatMessage) => {
              const isUser = msg.role === "user";
              const isHumanAgent = msg.role === "human_agent";
              const isSystem = msg.role === "system";

              if (isSystem) {
                return (
                  <div key={msg.id} className="flex justify-center my-2">
                    <span className="px-3 py-1 bg-amber-50 border border-amber-200 text-amber-800 rounded-full text-[11px] font-medium flex items-center gap-1 shadow-2xs">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                      {msg.content}
                    </span>
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  className={`flex gap-2.5 max-w-[88%] ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
                >
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-semibold flex-shrink-0 shadow-2xs ${
                      isUser
                        ? "bg-blue-600 text-white"
                        : isHumanAgent
                        ? "bg-amber-600 text-white"
                        : "bg-indigo-600 text-white"
                    }`}
                  >
                    {isUser ? (
                      <User className="w-3.5 h-3.5" />
                    ) : isHumanAgent ? (
                      <Headphones className="w-3.5 h-3.5" />
                    ) : (
                      <Bot className="w-3.5 h-3.5" />
                    )}
                  </div>

                  <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-1.5 mb-0.5 text-[10px] text-slate-400">
                      <span>
                        {isUser
                          ? "我 (客户)"
                          : isHumanAgent
                          ? `人工客服 · ${session?.assignedAgent || "陈浩"}`
                          : "IntelliServe AI"}
                      </span>
                      <span>{msg.timestamp}</span>
                      {isHumanAgent && (
                        <span className="px-1.5 py-0.2 bg-amber-100 text-amber-800 font-bold rounded text-[9px]">
                          人工专席回复
                        </span>
                      )}
                    </div>

                    <div
                      className={`p-3 rounded-2xl text-xs leading-relaxed shadow-2xs ${
                        isUser
                          ? "bg-blue-600 text-white rounded-tr-xs"
                          : isHumanAgent
                          ? "bg-amber-50 text-slate-900 border border-amber-300 rounded-tl-xs"
                          : "bg-white text-slate-800 border border-slate-200 rounded-tl-xs"
                      }`}
                    >
                      {isHumanAgent && (
                        <div className="flex items-center gap-1 text-[11px] font-bold text-amber-900 mb-1 border-b border-amber-200/70 pb-1">
                          <Headphones className="w-3 h-3 text-amber-600" />
                          <span>人工客服专员实时解答:</span>
                        </div>
                      )}
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Agent Typing Animation on Customer side */}
            {agentTypingNotice && (
              <div className="flex gap-2 mr-auto items-center text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-full w-fit">
                <Headphones className="w-3.5 h-3.5 animate-bounce" />
                <span>{agentTypingNotice}</span>
              </div>
            )}

            {customerLoading && (
              <div className="flex gap-2 mr-auto items-center text-xs text-slate-500 bg-white border border-slate-200 px-3 py-1.5 rounded-full w-fit">
                <Bot className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                <span>智能引擎正在检索政策中...</span>
              </div>
            )}

            <div ref={customerMessagesEndRef} />
          </div>

          {/* Quick Customer Prompts */}
          <div className="px-4 py-2 border-t border-slate-100 bg-white flex items-center gap-1.5 overflow-x-auto text-[11px]">
            <span className="text-slate-400 whitespace-nowrap">快捷提问:</span>
            {quickCustomerPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleCustomerSend(p)}
                className="px-2 py-0.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md whitespace-nowrap transition-colors cursor-pointer"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Customer Input Box */}
          <div className="p-3 border-t border-slate-200 bg-white">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleCustomerSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={customerInput}
                onChange={(e) => {
                  setCustomerInput(e.target.value);
                  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(
                      JSON.stringify({
                        type: "typing",
                        sessionId: selectedSessionId,
                        sender: "customer",
                        isTyping: e.target.value.length > 0
                      })
                    );
                  }
                }}
                placeholder={isHumanActive ? "人工客服已接听，请输入您的需求..." : "请输入您想咨询的问题（输入【转人工】可呼叫人工客服）..."}
                className="flex-1 px-3.5 py-2 text-xs bg-slate-100 focus:bg-white text-slate-800 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 transition-all"
              />
              <button
                type="submit"
                disabled={customerLoading || !customerInput.trim()}
                className="flex items-center gap-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-xl transition-colors cursor-pointer disabled:cursor-not-allowed shadow-xs"
              >
                <span>发送</span>
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>

        {/* ============================================================== */}
        {/* RIGHT COLUMN: HUMAN AGENT WORKBENCH (人工客服工作台视窗) */}
        {/* ============================================================== */}
        <div className="w-1/2 flex flex-col h-full bg-slate-50">
          {/* Agent Top Header */}
          <div className="px-5 py-3 border-b border-slate-200 bg-gradient-to-r from-amber-50 to-orange-50/50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-amber-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                <Headphones className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-slate-900">
                    人工客服坐席工作台 · {session?.assignedAgent || "陈浩"}
                  </span>
                  <span className="px-2 py-0.2 bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold rounded-full">
                    工号: {session?.assignedAgentId || "agent_101"} (高级督导)
                  </span>
                </div>
                <div className="text-[11px] text-slate-500">
                  当前对接客户: <strong>{session?.customerProfile?.name || "王女士"}</strong> (
                  {session?.customerProfile?.vipLevel || "黄金会员"})
                </div>
              </div>
            </div>

            {/* Quick Agent Actions */}
            <div className="flex items-center gap-2">
              {!isHumanActive ? (
                <button
                  onClick={handleAgentTakeover}
                  className="flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-lg shadow-xs transition-all cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>立即接入接管</span>
                </button>
              ) : (
                <button
                  onClick={handleAgentRelease}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-medium rounded-lg transition-colors cursor-pointer"
                >
                  <Bot className="w-3.5 h-3.5 text-blue-600" />
                  <span>交还AI托管</span>
                </button>
              )}
            </div>
          </div>

          {/* Customer Snapshot Dossier (客户背景档案) */}
          <div className="px-4 py-2.5 bg-white border-b border-slate-200 text-xs">
            <div className="flex items-center justify-between text-[11px] mb-1.5">
              <span className="font-bold text-slate-700 flex items-center gap-1">
                <Package className="w-3.5 h-3.5 text-blue-600" />
                关联订单: <span className="font-mono text-blue-900">{session?.customerProfile?.orderId || "ORD-2026-88992"}</span>
              </span>
              <span className="px-2 py-0.2 bg-emerald-50 text-emerald-700 font-semibold rounded border border-emerald-200">
                支持7天退货 (黄金会员免运费)
              </span>
            </div>
            <div className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-200/80 leading-relaxed">
              <strong className="text-slate-800">上下文备忘: </strong>
              {session?.summaryMemory || "客户咨询7天无理由退货运费及退款到账时效。"}
            </div>
          </div>

          {/* Agent View Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-100/60">
            {session?.messages?.map((msg: ChatMessage) => {
              const isUser = msg.role === "user";
              const isHumanAgent = msg.role === "human_agent";
              const isSystem = msg.role === "system";

              if (isSystem) {
                return (
                  <div key={msg.id} className="flex justify-center my-1.5">
                    <span className="px-3 py-0.5 bg-slate-200/90 text-slate-700 rounded-full text-[10px] font-mono">
                      {msg.content}
                    </span>
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  className={`flex gap-2 max-w-[88%] ${isHumanAgent ? "ml-auto flex-row-reverse" : "mr-auto"}`}
                >
                  <div
                    className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                      isHumanAgent
                        ? "bg-amber-600 text-white"
                        : isUser
                        ? "bg-blue-600 text-white"
                        : "bg-slate-600 text-white"
                    }`}
                  >
                    {isHumanAgent ? "坐" : isUser ? "客" : "AI"}
                  </div>

                  <div className={`flex flex-col ${isHumanAgent ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-1.5 mb-0.5 text-[10px] text-slate-400">
                      <span>{isHumanAgent ? "我 (人工坐席)" : isUser ? `客户 (${session?.customerProfile?.name || "王女士"})` : "智能客服 (AI)"}</span>
                      <span>{msg.timestamp}</span>
                    </div>

                    <div
                      className={`p-2.5 rounded-xl text-xs leading-relaxed shadow-2xs ${
                        isHumanAgent
                          ? "bg-amber-600 text-white rounded-tr-xs"
                          : isUser
                          ? "bg-white text-slate-900 border border-slate-200 rounded-tl-xs font-medium"
                          : "bg-slate-200/80 text-slate-700 rounded-tl-xs text-[11px]"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Customer Typing Notice on Agent Side */}
            {customerTypingNotice && (
              <div className="flex gap-2 mr-auto items-center text-xs text-blue-700 bg-blue-50 border border-blue-200 px-3 py-1 rounded-full w-fit animate-pulse">
                <User className="w-3.5 h-3.5" />
                <span>{customerTypingNotice}</span>
              </div>
            )}

            <div ref={agentMessagesEndRef} />
          </div>

          {/* AI Copilot Suggestion Box (副驾驶话术推荐) */}
          <div className="px-4 py-2 bg-gradient-to-r from-indigo-50 to-purple-50 border-t border-indigo-100 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-indigo-900 font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>智能副驾驶 Copilot:</span>
              <span className="text-[11px] font-normal text-indigo-700 hidden lg:inline">
                结合客户画像与2026售后规则自动草拟
              </span>
            </div>
            <button
              onClick={handleGenerateCopilot}
              disabled={copilotLoading}
              className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold rounded-md shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
            >
              <Zap className="w-3 h-3" />
              <span>{copilotLoading ? "生成中..." : "生成推荐拟答"}</span>
            </button>
          </div>

          {/* Canned Responses Pills (快捷话术) */}
          <div className="px-4 py-1.5 bg-white border-t border-slate-200 flex items-center gap-1.5 overflow-x-auto text-xs">
            <span className="text-slate-400 text-[10px] whitespace-nowrap">常用话术:</span>
            {cannedResponses.map((item, idx) => (
              <button
                key={idx}
                onClick={() => setAgentInput(item.text)}
                title={item.text}
                className="px-2 py-0.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded text-[11px] whitespace-nowrap cursor-pointer transition-colors"
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Agent Input Box */}
          <div className="p-3 border-t border-slate-200 bg-white">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAgentSend();
              }}
              className="flex items-center gap-2"
            >
              <textarea
                rows={2}
                value={agentInput}
                onChange={(e) => {
                  setAgentInput(e.target.value);
                  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(
                      JSON.stringify({
                        type: "typing",
                        sessionId: selectedSessionId,
                        sender: "agent",
                        name: session?.assignedAgent || "陈浩",
                        isTyping: e.target.value.length > 0
                      })
                    );
                  }
                }}
                placeholder="人工坐席回复输入框（回车或点击右侧按钮直接发送至客户视窗）..."
                className="flex-1 px-3 py-2 text-xs bg-slate-50 focus:bg-white text-slate-800 rounded-xl border border-slate-200 focus:outline-hidden focus:border-amber-500 resize-none transition-all"
              />
              <button
                type="submit"
                disabled={agentSending || !agentInput.trim()}
                className="h-full px-4 py-3 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white text-xs font-bold rounded-xl transition-colors cursor-pointer disabled:cursor-not-allowed shadow-xs flex flex-col items-center justify-center gap-1"
              >
                <Send className="w-4 h-4" />
                <span>发送</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
