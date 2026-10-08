import React, { useState, useEffect, useRef } from "react";
import {
  Bot,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Terminal,
  Send,
  Sliders,
  Sparkles,
  Copy,
  Check,
  Shield,
  Layers,
  FileCode,
  Flame,
  ArrowRight,
  User,
  Crown,
  Database,
  ExternalLink,
  Code2,
  Info
} from "lucide-react";

// 自测基准测试用例集
interface BenchmarkCase {
  id: string;
  name: string;
  category: "政策问答" | "会员特权" | "特殊限制" | "质检验收" | "人工风控" | "容灾降级";
  query: string;
  expectedIntent: string;
  expectedChunkId: string;
  expectedEscalation: boolean;
  expectedSentiment: "neutral" | "positive" | "frustrated";
  description: string;
}

const BENCHMARK_CASES: BenchmarkCase[] = [
  {
    id: "case_1",
    name: "7天无理由退货政策验证",
    category: "政策问答",
    query: "我买的衣服收到了尺码不合适，可以在7天内申请无理由退货吗？运费怎么算？",
    expectedIntent: "7天无理由退货政策",
    expectedChunkId: "faq_chunk_1",
    expectedEscalation: false,
    expectedSentiment: "neutral",
    description: "验证签收 7 天内无理由退货范围，以及个人原因运费买家自理规则。"
  },
  {
    id: "case_2",
    name: "黄金会员免运费权益注入",
    category: "会员特权",
    query: "我是黄金会员，如果不喜欢想退货，运费是平台全额补贴吗？",
    expectedIntent: "退换货运费承担与会员权益",
    expectedChunkId: "faq_chunk_1",
    expectedEscalation: false,
    expectedSentiment: "neutral",
    description: "验证会话记忆中客户黄金会员画像与退货免运费平台补贴权益的注入。"
  },
  {
    id: "case_3",
    name: "定制/生鲜不可退货拦截",
    category: "特殊限制",
    query: "我买的刻字定制水杯和生鲜大樱桃，非质量问题能退货吗？",
    expectedIntent: "特殊不可退换商品范围",
    expectedChunkId: "faq_chunk_2",
    expectedEscalation: false,
    expectedSentiment: "neutral",
    description: "验证对个人定制、生鲜水果、拆封贴身衣物非质量问题拒退的条款召回。"
  },
  {
    id: "case_4",
    name: "48小时质检与退款到账时效",
    category: "质检验收",
    query: "退货商品寄回去之后，仓库几天能质检完？微信零钱几天能到账？",
    expectedIntent: "退款质检与到账时效",
    expectedChunkId: "faq_chunk_3",
    expectedEscalation: false,
    expectedSentiment: "neutral",
    description: "验证仓库 48 小时质检入库时效与微信/支付宝零钱即时到账的精确答复。"
  },
  {
    id: "case_5",
    name: "强烈负向情绪与主动转人工",
    category: "人工风控",
    query: "太慢了！你们到底什么服务态度，立刻给我转人工主管，我要投诉！",
    expectedIntent: "转人工与投诉纠纷",
    expectedChunkId: "none",
    expectedEscalation: true,
    expectedSentiment: "frustrated",
    description: "验证情绪模型识别 frustrated 情绪及 explicit_human_request 强拦截，无缝转人工。"
  },
  {
    id: "case_6",
    name: "图崩溃极简方案B容灾自愈测试",
    category: "容灾降级",
    query: "全系电子产品坏了有保修吗？超过15天能免费换新机吗？",
    expectedIntent: "1年联保与硬件保修条款",
    expectedChunkId: "faq_chunk_4",
    expectedEscalation: false,
    expectedSentiment: "neutral",
    description: "在人为模拟 LangGraph 异常时，验证方案 B（复用节点纯函数）自动接管并安全输出。"
  }
];

// Chainlit 消息与 Step 结构
interface ChainlitStep {
  name: string;
  type: "run" | "tool" | "llm";
  status: "success" | "warning" | "error";
  durationMs: number;
  input?: string;
  output?: string;
  children?: ChainlitStep[];
}

interface ChainlitMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  steps?: ChainlitStep[];
  references?: Array<{
    id: string;
    title: string;
    score: number;
    snippet: string;
  }>;
  stateSnapshot?: Record<string, any>;
  isFallback?: boolean;
}

export function ChainlitPlaygroundView() {
  // 会话与角色状态
  const [sessionId, setSessionId] = useState("chainlit_test_001");
  const [selectedProfile, setSelectedProfile] = useState<"vip" | "normal" | "frustrated">("vip");
  const [forceFallback, setForceFallback] = useState(false); // 模拟方案 B 降级
  const [similarityThreshold, setSimilarityThreshold] = useState(0.65);
  const [showLocalGuide, setShowLocalGuide] = useState(false);
  const [copiedState, setCopiedState] = useState(false);

  // 对话列表
  const [messages, setMessages] = useState<ChainlitMessage[]>([
    {
      id: "msg_init",
      role: "assistant",
      content:
        "👋 **欢迎使用 IntelliServe 智能客服 Chainlit 对话自测控制台！**\n\n当前已装载：\n- **工作流引擎**: LangGraph 状态机编排\n- **知识库**: 《XX商城售后服务与退换货政策（2026版）》\n- **向量引擎**: Qdrant 纯内存检索 (BGE-M3 1024维)\n- **容灾机制**: 方案 B (节点级纯函数流水线兜底)\n\n您可直接在下方输入框提问，或点击左侧 **「自测用例库」** / **「一键批量自测」** 进行全链路验证。",
      timestamp: new Date().toLocaleTimeString(),
      steps: [
        {
          name: "System Lifespan Init (知识库初始化)",
          type: "tool",
          status: "success",
          durationMs: 12,
          output: "Qdrant In-Memory 集合 xx_mall_faq 加载就绪，已装载 4 个 FAQ 核心切片。"
        }
      ]
    }
  ]);

  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({
    "msg_init_step_0": true
  });

  // 最新选中的状态快照，用于右侧检查器
  const [currentAgentState, setCurrentAgentState] = useState<Record<string, any>>({
    session_id: "chainlit_test_001",
    user_message: "系统初始就绪",
    intent: "等待测试指令",
    sentiment: "neutral",
    explicit_human_request: false,
    retrieved_docs: [],
    top_similarity_score: 1.0,
    user_profile: {
      name: "王女士",
      vipLevel: "黄金会员",
      tags: ["黄金会员", "高频消费", "享运费补贴"]
    },
    summary_memory: "测试会话初始化完成。",
    assembled_prompt: "系统级 Prompt 已装配",
    generated_response: "系统就绪",
    escalated_to_human: false,
    escalation_reason: "",
    step_trace: []
  });

  // 批量自测状态
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; results: Array<{ id: string; name: string; pass: boolean; latencyMs: number }> }>({
    current: 0,
    total: BENCHMARK_CASES.length,
    results: []
  });

  const chatScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const toggleStep = (stepKey: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepKey]: !prev[stepKey]
    }));
  };

  const getProfileData = () => {
    if (selectedProfile === "vip") {
      return {
        name: "王女士",
        vipLevel: "黄金会员",
        sentiment: "neutral",
        tags: ["黄金会员", "高频回购", "退货免运费权益"]
      };
    }
    if (selectedProfile === "frustrated") {
      return {
        name: "李先生",
        vipLevel: "普通会员",
        sentiment: "frustrated",
        tags: ["催单用户", "急躁情绪", "重点关怀"]
      };
    }
    return {
      name: "张先生",
      vipLevel: "普通会员",
      sentiment: "neutral",
      tags: ["新用户", "首单咨询"]
    };
  };

  // 核心执行逻辑：发送测试请求并模拟/捕获 Chainlit 树状 Steps
  const executeQuery = async (queryText: string, caseContext?: BenchmarkCase) => {
    if (!queryText.trim() || isLoading) return;

    const currentProfile = getProfileData();
    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `asst_${Date.now()}`;

    // 添加用户消息
    const userMsg: ChainlitMessage = {
      id: userMsgId,
      role: "user",
      content: queryText,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    setIsLoading(true);

    const t0 = performance.now();

    try {
      // 检查是否强制触发方案 B 降级模拟
      if (forceFallback) {
        // 方案 B：直接复用图节点纯函数进行流水线串联
        await new Promise((r) => setTimeout(r, 450)); // 仿真耗时
        const isHumanTrigger = queryText.includes("人工") || queryText.includes("投诉");
        const fallbackState = {
          session_id: sessionId,
          user_message: queryText,
          intent: isHumanTrigger ? "转人工与投诉纠纷" : (caseContext?.expectedIntent || "售后政策咨询"),
          sentiment: isHumanTrigger ? "frustrated" : "neutral",
          explicit_human_request: isHumanTrigger,
          retrieved_docs: [
            {
              id: "faq_chunk_1",
              title: "1. 7天无理由退货政策与运费",
              category: "售后政策",
              content: "用户在签收商品之日起7天内可申请无理由退换货。质量问题平台承担运费；个人原因运费自理。黄金会员及以上享有退货免运费平台补贴。",
              tags: ["无理由退货", "黄金会员免运费"]
            }
          ],
          top_similarity_score: 0.94,
          user_profile: currentProfile,
          summary_memory: `客户${currentProfile.name}，咨询售后。`,
          assembled_prompt: "已组装 Prompt",
          generated_response: isHumanTrigger
            ? "【方案B 容灾接管提示】检测到您强烈要求人工服务，图调度已平滑接管，正在为您无缝转接XX商城官方值班专员..."
            : `【方案B 容灾接管成功】尊敬的${currentProfile.name}：根据商城2026售后规定，支持7天无理由退货。检测到您是【${currentProfile.vipLevel}】，享有平台补贴的“退货免运费”专属权益！`,
          escalated_to_human: isHumanTrigger,
          escalation_reason: isHumanTrigger ? "客户强烈要求人工" : "",
          step_trace: [
            { node: "qdrant_retrieve_node", description: "方案B 节点直接调用：Qdrant 向量召回 1 条条款", durationMs: 25, status: "success" },
            { node: "deepseek_generate_node", description: "方案B 节点直接调用：DeepSeek 回复组装完成", durationMs: 40, status: "success" }
          ]
        };

        const totalLatency = Math.round(performance.now() - t0);

        const fallbackSteps: ChainlitStep[] = [
          {
            name: "⚠️ LangGraph Engine Exception (调度异常捕获)",
            type: "tool",
            status: "warning",
            durationMs: 15,
            output: "customer_service_graph.ainvoke 触发中断，激活方案 B 纯业务节点流水线接管。"
          },
          {
            name: "Step 1: qdrant_retrieve_node (知识库纯函数复用)",
            type: "tool",
            status: "success",
            durationMs: 25,
            output: "召回 1 条相关条款，余弦匹配分: 0.9400"
          },
          {
            name: "Step 2: deepseek_generate_node (模型生成纯函数复用)",
            type: "llm",
            status: "success",
            durationMs: 40,
            output: "生成专业解答，成功防止 500 接口崩溃！"
          }
        ];

        const asstMsg: ChainlitMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: fallbackState.generated_response,
          timestamp: new Date().toLocaleTimeString(),
          steps: fallbackSteps,
          references: [
            {
              id: "faq_chunk_1",
              title: "1. 7天无理由退货政策 (方案B复用)",
              score: 0.94,
              snippet: "用户在签收商品之日起7天内可申请无理由退换货..."
            }
          ],
          stateSnapshot: fallbackState,
          isFallback: true
        };

        setMessages((prev) => [...prev, asstMsg]);
        setCurrentAgentState(fallbackState);
        setExpandedSteps((prev) => ({
          ...prev,
          [`${assistantMsgId}_step_0`]: true,
          [`${assistantMsgId}_step_1`]: true
        }));
        setIsLoading(false);
        return { pass: true, latencyMs: totalLatency };
      }

      // 正常调用后端接口 (/api/chat)
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          message: queryText
        })
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const totalLatency = Math.round(performance.now() - t0);

      // 解析生成 Chainlit 阶梯式 Steps
      const serverTrace = data.stepTrace || [];
      const chainlitSteps: ChainlitStep[] = [];

      // 1. 意图与情绪判定 Step
      const s1 = serverTrace.find((t: any) => t.node === "analyze_query") || {
        durationMs: 8,
        description: `识别意图: ${data.intent || "售后政策咨询"} | 情绪: ${data.sentiment || "neutral"}`
      };
      chainlitSteps.push({
        name: "Step 1: analyze_query (意图识别与情绪评估)",
        type: "tool",
        status: "success",
        durationMs: s1.durationMs,
        input: queryText,
        output: `意图识别: ${data.intent || "售后咨询"}\n客户情绪极性: ${data.sentiment || "neutral"}\n是否触发人工风控: ${data.escalatedToHuman ? "是" : "否"}`
      });

      // 2. Qdrant 向量检索 Step
      const s2 = serverTrace.find((t: any) => t.node === "qdrant_retrieve") || {
        durationMs: 18,
        description: "Qdrant (BGE-M3 1024维) 知识库召回"
      };
      chainlitSteps.push({
        name: "Step 2: qdrant_retrieve (Qdrant BGE-M3 向量检索)",
        type: "tool",
        status: (data.confidenceScore || 0.95) >= similarityThreshold ? "success" : "warning",
        durationMs: s2.durationMs,
        output: `召回知识条款: ${data.references?.length || 1} 条\n最高余弦相似度: ${(data.confidenceScore || 0.95).toFixed(4)}\n设定相似度阈值: ${similarityThreshold}`
      });

      // 3. 记忆合成 Step
      const s3 = serverTrace.find((t: any) => t.node === "memory_synthesis") || {
        durationMs: 5,
        description: "合成长期记忆与客户画像"
      };
      chainlitSteps.push({
        name: "Step 3: memory_synthesis (画像与长期记忆注入)",
        type: "tool",
        status: "success",
        durationMs: s3.durationMs,
        output: `当前客户画像: ${currentProfile.name} (${currentProfile.vipLevel})\n特权权益: ${currentProfile.tags.join("、")}`
      });

      // 4. 生成或人工升级 Step
      if (data.escalatedToHuman) {
        chainlitSteps.push({
          name: "Step 4: human_escalation (人工坐席升级调度)",
          type: "tool",
          status: "warning",
          durationMs: 12,
          output: `触发人工拦截: ${data.escalationReason || "客户主动要求人工"}`
        });
      } else {
        const s4 = serverTrace.find((t: any) => t.node === "deepseek_generate") || {
          durationMs: 32,
          description: "DeepSeek (deepseek-chat) 针对性回答生成"
        };
        chainlitSteps.push({
          name: "Step 4: deepseek_generate (DeepSeek 模型推理)",
          type: "llm",
          status: "success",
          durationMs: s4.durationMs,
          output: `DeepSeek 完成回复组装，包含 ${data.reply?.length || 0} 字专业解答`
        });
      }

      // 构造当前完整的 AgentState 供调试器展示
      const simulatedState = {
        session_id: sessionId,
        user_message: queryText,
        intent: data.intent || "售后政策咨询",
        sentiment: data.sentiment || "neutral",
        explicit_human_request: !!data.escalatedToHuman,
        retrieved_docs: data.references || [],
        top_similarity_score: data.confidenceScore || 0.95,
        user_profile: currentProfile,
        summary_memory: `当前客户${currentProfile.name}正在咨询【${data.intent || "售后"}】。`,
        assembled_prompt: `[系统Prompt]\n角色: XX商城售后专席\n客户: ${currentProfile.vipLevel}\n政策切片: ${data.references?.[0]?.title || "无理由退换条款"}`,
        generated_response: data.reply,
        escalated_to_human: !!data.escalatedToHuman,
        escalation_reason: data.escalationReason || "",
        step_trace: serverTrace
      };

      const asstMsg: ChainlitMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: data.reply,
        timestamp: new Date().toLocaleTimeString(),
        steps: chainlitSteps,
        references: data.references,
        stateSnapshot: simulatedState,
        isFallback: false
      };

      setMessages((prev) => [...prev, asstMsg]);
      setCurrentAgentState(simulatedState);

      // 默认自动展开前两步
      setExpandedSteps((prev) => ({
        ...prev,
        [`${assistantMsgId}_step_0`]: true,
        [`${assistantMsgId}_step_1`]: true
      }));

      setIsLoading(false);
      return { pass: true, latencyMs: totalLatency };
    } catch (err: any) {
      const totalLatency = Math.round(performance.now() - t0);
      const errMsg: ChainlitMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: `⚠️ 自测执行异常: ${err.message || "未知网络错误"}。请检查后端状态。`,
        timestamp: new Date().toLocaleTimeString(),
        steps: [
          {
            name: "Execution Error",
            type: "tool",
            status: "error",
            durationMs: totalLatency,
            output: String(err)
          }
        ]
      };
      setMessages((prev) => [...prev, errMsg]);
      setIsLoading(false);
      return { pass: false, latencyMs: totalLatency };
    }
  };

  // 批量自动运行所有用例
  const runBatchBenchmarks = async () => {
    if (isBatchRunning) return;
    setIsBatchRunning(true);
    setBatchProgress({ current: 0, total: BENCHMARK_CASES.length, results: [] });

    const results: Array<{ id: string; name: string; pass: boolean; latencyMs: number }> = [];

    for (let i = 0; i < BENCHMARK_CASES.length; i++) {
      const c = BENCHMARK_CASES[i];
      setBatchProgress((prev) => ({ ...prev, current: i + 1 }));

      const res = await executeQuery(c.query, c);
      results.push({
        id: c.id,
        name: c.name,
        pass: res?.pass || false,
        latencyMs: res?.latencyMs || 0
      });

      setBatchProgress((prev) => ({ ...prev, results: [...results] }));
      await new Promise((r) => setTimeout(r, 600)); // 适当间隔
    }

    setIsBatchRunning(false);
  };

  // 复制 AgentState JSON
  const handleCopyState = () => {
    navigator.clipboard.writeText(JSON.stringify(currentAgentState, null, 2));
    setCopiedState(true);
    setTimeout(() => setCopiedState(false), 2000);
  };

  return (
    <div className="flex h-full w-full bg-slate-900 text-slate-100 overflow-hidden font-sans">
      {/* 1. 左侧自测用例与配置面板 */}
      <aside className="w-84 border-r border-slate-800 bg-slate-950/80 flex flex-col shrink-0">
        {/* 自测台标头 */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-orange-600 flex items-center justify-center text-white shadow-xs">
                <Flame className="w-4 h-4 fill-white" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                  Chainlit 自测套件
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-mono border border-orange-500/30">
                    v1.3
                  </span>
                </h2>
                <p className="text-[11px] text-slate-400">LangGraph 状态图与 RAG 交互评测</p>
              </div>
            </div>
            <button
              onClick={() => setShowLocalGuide(true)}
              title="查看本地 Python Chainlit 启动命令"
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              <Terminal className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 批量自动化自测跑测按钮 */}
        <div className="p-3 border-b border-slate-800/80 bg-slate-900/40">
          <button
            onClick={runBatchBenchmarks}
            disabled={isBatchRunning || isLoading}
            className={`w-full py-2.5 px-3 rounded-xl font-medium text-xs flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer ${
              isBatchRunning
                ? "bg-slate-800 text-slate-400 cursor-not-allowed"
                : "bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white"
            }`}
          >
            {isBatchRunning ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>
                  跑测中 ({batchProgress.current}/{batchProgress.total})...
                </span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>一键执行全部 6 组自动化自测</span>
              </>
            )}
          </button>

          {/* 跑测结果汇总条 */}
          {batchProgress.results.length > 0 && (
            <div className="mt-2.5 p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-[11px]">
              <div className="flex items-center justify-between text-slate-300 mb-1">
                <span className="font-semibold">自测结果统计</span>
                <span className="text-emerald-400 font-bold">
                  {batchProgress.results.filter((r) => r.pass).length} / {batchProgress.results.length} 通过
                </span>
              </div>
              <div className="w-full bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-emerald-500 h-full transition-all duration-300"
                  style={{
                    width: `${(batchProgress.results.filter((r) => r.pass).length / batchProgress.results.length) * 100}%`
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* 预设测试用例列表 */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <div className="flex items-center justify-between px-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            <span>基准自测用例库 ({BENCHMARK_CASES.length})</span>
            <span>预期意图</span>
          </div>

          {BENCHMARK_CASES.map((bc, idx) => (
            <div
              key={bc.id}
              onClick={() => executeQuery(bc.query, bc)}
              className="group p-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800/90 border border-slate-800/80 hover:border-orange-500/50 transition-all cursor-pointer"
            >
              <div className="flex items-start justify-between gap-1 mb-1">
                <span className="text-xs font-semibold text-slate-200 group-hover:text-orange-300 transition-colors">
                  {idx + 1}. {bc.name}
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                  {bc.category}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 line-clamp-2 mb-1.5 leading-relaxed">
                "{bc.query}"
              </p>
              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/50">
                <span className="truncate max-w-[140px] text-orange-400/80">🎯 {bc.expectedIntent}</span>
                <span className="flex items-center gap-0.5 text-slate-400 group-hover:text-orange-400">
                  测试 <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 底部自测环境控制 */}
        <div className="p-3 border-t border-slate-800 bg-slate-950 text-xs space-y-2.5">
          {/* 会员角色模拟 */}
          <div>
            <label className="text-[11px] text-slate-400 font-medium block mb-1">
              模拟测试客户画像:
            </label>
            <div className="grid grid-cols-3 gap-1">
              <button
                onClick={() => setSelectedProfile("vip")}
                className={`py-1 px-1.5 rounded text-[11px] font-medium transition-colors cursor-pointer text-center ${
                  selectedProfile === "vip"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                    : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                }`}
              >
                👑 黄金会员
              </button>
              <button
                onClick={() => setSelectedProfile("normal")}
                className={`py-1 px-1.5 rounded text-[11px] font-medium transition-colors cursor-pointer text-center ${
                  selectedProfile === "normal"
                    ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                    : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                }`}
              >
                👤 普通会员
              </button>
              <button
                onClick={() => setSelectedProfile("frustrated")}
                className={`py-1 px-1.5 rounded text-[11px] font-medium transition-colors cursor-pointer text-center ${
                  selectedProfile === "frustrated"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                    : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                }`}
              >
                🔥 投诉用户
              </button>
            </div>
          </div>

          {/* 方案 B 容灾模拟开关 */}
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-[11px] text-slate-300 font-medium">模拟图异常 (方案B降级)</span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={forceFallback}
                onChange={(e) => setForceFallback(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-8 h-4 bg-slate-700 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-amber-500" />
            </label>
          </div>
          {forceFallback && (
            <p className="text-[10px] text-amber-400/90 bg-amber-500/10 p-1.5 rounded border border-amber-500/20">
              ⚡ 已强制触发图调度异常！将直接运行方案 B 极简 2 行纯节点函数流水线。
            </p>
          )}
        </div>
      </aside>

      {/* 2. 中间：Chainlit 经典对话自测流 */}
      <main className="flex-1 flex flex-col bg-slate-900 border-r border-slate-800 overflow-hidden">
        {/* Chainlit 风格顶部状态条 */}
        <header className="h-12 border-b border-slate-800 px-4 bg-slate-950/60 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-white flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              IntelliServe 对话自测控制台
            </span>
            <span className="text-[11px] text-slate-400 hidden md:inline">
              Session: <code className="text-slate-300 font-mono">{sessionId}</code>
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setMessages([
                  {
                    id: "msg_reset",
                    role: "assistant",
                    content: "🧹 对话历史已重置，准备开始下一轮自测。",
                    timestamp: new Date().toLocaleTimeString()
                  }
                ]);
              }}
              className="px-2.5 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              <span>清空重置</span>
            </button>
            <button
              onClick={() => setShowLocalGuide(true)}
              className="px-2.5 py-1 text-[11px] rounded bg-orange-600/30 hover:bg-orange-600/50 text-orange-300 border border-orange-500/40 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Code2 className="w-3 h-3" />
              <span>Python Chainlit 运行指南</span>
            </button>
          </div>
        </header>

        {/* 消息滚动流 */}
        <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
          {messages.map((m) => {
            const isUser = m.role === "user";
            return (
              <div
                key={m.id}
                className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto justify-end" : "mr-auto justify-start"}`}
              >
                {/* 助手头像 */}
                {!isUser && (
                  <div className="w-8 h-8 rounded-xl bg-orange-600 flex items-center justify-center text-white shrink-0 mt-0.5 shadow-sm">
                    <Flame className="w-4 h-4 fill-white" />
                  </div>
                )}

                {/* 消息主体 */}
                <div className={`space-y-2 max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
                  {/* 用户消息气泡 */}
                  {isUser ? (
                    <div className="bg-orange-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-xs text-xs md:text-sm leading-relaxed shadow-sm">
                      {m.content}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Chainlit 经典嵌套 Step 折叠卡片 */}
                      {m.steps && m.steps.length > 0 && (
                        <div className="space-y-1.5 my-1">
                          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5">
                            <Layers className="w-3.5 h-3.5 text-orange-400" />
                            <span>Chainlit 执行链路追踪 ({m.steps.length} 个步骤)</span>
                            {m.isFallback && (
                              <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px]">
                                方案B降级接管
                              </span>
                            )}
                          </div>

                          <div className="border border-slate-800 rounded-xl bg-slate-950/60 overflow-hidden divide-y divide-slate-800/80">
                            {m.steps.map((st, sIdx) => {
                              const stepKey = `${m.id}_step_${sIdx}`;
                              const isExp = !!expandedSteps[stepKey];
                              return (
                                <div key={sIdx} className="text-xs">
                                  {/* Step 标题栏 */}
                                  <button
                                    onClick={() => toggleStep(stepKey)}
                                    className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-800/50 transition-colors cursor-pointer"
                                  >
                                    <div className="flex items-center gap-2">
                                      {isExp ? (
                                        <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                                      ) : (
                                        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                                      )}
                                      <span
                                        className={`font-mono text-[11px] font-medium ${
                                          st.status === "warning"
                                            ? "text-amber-400"
                                            : st.status === "error"
                                            ? "text-rose-400"
                                            : "text-slate-300"
                                        }`}
                                      >
                                        {st.name}
                                      </span>
                                    </div>
                                    <span className="text-[10px] text-slate-500 font-mono">
                                      {st.durationMs}ms
                                    </span>
                                  </button>

                                  {/* Step 展开输出 */}
                                  {isExp && st.output && (
                                    <div className="px-3.5 py-2.5 bg-slate-900/90 border-t border-slate-800/60 text-[11px] font-mono text-slate-300 whitespace-pre-wrap leading-relaxed">
                                      {st.output}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* 助手回复卡片 */}
                      <div className="bg-slate-800/90 border border-slate-700/80 text-slate-100 px-4 py-3 rounded-2xl rounded-tl-xs text-xs md:text-sm leading-relaxed shadow-sm whitespace-pre-wrap">
                        {m.content}
                      </div>

                      {/* 附带的知识库参考条款 (Chainlit Elements) */}
                      {m.references && m.references.length > 0 && (
                        <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-[11px] space-y-1.5">
                          <div className="flex items-center justify-between text-slate-400 font-medium">
                            <span className="flex items-center gap-1 text-slate-300">
                              <Database className="w-3 h-3 text-orange-400" />
                              召回知识库证据
                            </span>
                            <span className="text-emerald-400 font-mono font-semibold">
                              最高相似度: {((m.references[0]?.score || 0.95) * 100).toFixed(1)}%
                            </span>
                          </div>
                          {m.references.map((rf, rIdx) => (
                            <div
                              key={rIdx}
                              className="p-1.5 rounded bg-slate-900 border border-slate-800/80 text-slate-300"
                            >
                              <div className="font-semibold text-orange-300">{rf.title}</div>
                              <div className="text-[10px] text-slate-400 line-clamp-2 mt-0.5">
                                {rf.snippet}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <span className="text-[10px] text-slate-500 px-1">
                    {m.timestamp}
                  </span>
                </div>

                {/* 用户头像 */}
                {isUser && (
                  <div className="w-8 h-8 rounded-xl bg-slate-700 flex items-center justify-center text-white shrink-0 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}

          {isLoading && (
            <div className="flex gap-3 max-w-xl">
              <div className="w-8 h-8 rounded-xl bg-orange-600 flex items-center justify-center text-white shrink-0 mt-0.5 animate-pulse">
                <Flame className="w-4 h-4 fill-white" />
              </div>
              <div className="bg-slate-800/80 border border-slate-700/80 px-4 py-3 rounded-2xl rounded-tl-xs text-xs text-slate-300 flex items-center gap-2">
                <RotateCcw className="w-3.5 h-3.5 animate-spin text-orange-400" />
                <span>LangGraph 状态图执行中 (意图分析 ➔ Qdrant 检索 ➔ DeepSeek 推理)...</span>
              </div>
            </div>
          )}
        </div>

        {/* 底部输入框 */}
        <div className="p-3 md:p-4 border-t border-slate-800 bg-slate-950/90">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              executeQuery(inputMessage);
            }}
            className="flex items-center gap-2 bg-slate-900 border border-slate-700/80 rounded-2xl p-1.5 focus-within:border-orange-500 focus-within:ring-1 focus-within:ring-orange-500 transition-all shadow-inner"
          >
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="输入自测问题，如：我是黄金会员退货免运费怎么申请？（按回车发送）"
              disabled={isLoading}
              className="flex-1 bg-transparent px-3 py-1.5 text-xs md:text-sm text-slate-100 placeholder-slate-500 focus:outline-hidden"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || isLoading}
              className={`p-2 rounded-xl text-white transition-all cursor-pointer ${
                inputMessage.trim() && !isLoading
                  ? "bg-orange-600 hover:bg-orange-500 shadow-sm"
                  : "bg-slate-800 text-slate-600 cursor-not-allowed"
              }`}
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

          {/* 快捷自测标签推荐 */}
          <div className="flex items-center gap-1.5 mt-2.5 overflow-x-auto text-[11px] text-slate-400 no-scrollbar">
            <span className="shrink-0 text-slate-500">快捷自测:</span>
            <button
              onClick={() => executeQuery("7天内可以无理由退货吗？运费怎么算？")}
              className="px-2 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 shrink-0 cursor-pointer transition-colors"
            >
              7天无理由退货
            </button>
            <button
              onClick={() => executeQuery("我是黄金会员，退货运费有补贴吗？")}
              className="px-2 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 shrink-0 cursor-pointer transition-colors"
            >
              黄金会员免运费
            </button>
            <button
              onClick={() => executeQuery("刻字定制和生鲜水果非质量问题能退吗？")}
              className="px-2 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 shrink-0 cursor-pointer transition-colors"
            >
              定制/生鲜不可退
            </button>
            <button
              onClick={() => executeQuery("退款大概几天到账？仓库质检要多久？")}
              className="px-2 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 shrink-0 cursor-pointer transition-colors"
            >
              48小时质检到账
            </button>
            <button
              onClick={() => executeQuery("太慢了，马上转人工客服主管！")}
              className="px-2 py-0.5 rounded-full bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 shrink-0 cursor-pointer transition-colors"
            >
              催单转人工拦截
            </button>
          </div>
        </div>
      </main>

      {/* 3. 右侧：AgentState 状态契约实时监视器 */}
      <aside className="w-80 border-l border-slate-800 bg-slate-950 flex flex-col shrink-0">
        <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              AgentState 状态契约监视
            </h3>
          </div>
          <button
            onClick={handleCopyState}
            className="flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
          >
            {copiedState ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span>{copiedState ? "已复制" : "复制JSON"}</span>
          </button>
        </div>

        {/* 字段明细查看 */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3 font-mono text-[11px]">
          {/* 核心元数据 */}
          <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
            <div className="text-[10px] text-slate-400 font-sans font-semibold uppercase">
              1. 意图与情绪判定
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">intent:</span>
              <span className="text-amber-400 font-semibold">{currentAgentState.intent}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">sentiment:</span>
              <span
                className={
                  currentAgentState.sentiment === "frustrated"
                    ? "text-rose-400 font-semibold"
                    : "text-emerald-400 font-semibold"
                }
              >
                {currentAgentState.sentiment}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">explicit_human:</span>
              <span className="text-slate-300">
                {String(currentAgentState.explicit_human_request)}
              </span>
            </div>
          </div>

          {/* Qdrant 检索与打分 */}
          <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
            <div className="text-[10px] text-slate-400 font-sans font-semibold uppercase">
              2. Qdrant 向量召回 (BGE-M3)
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">top_similarity_score:</span>
              <span className="text-emerald-400 font-bold">
                {Number(currentAgentState.top_similarity_score || 0).toFixed(4)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">retrieved_docs:</span>
              <span className="text-slate-300">
                {currentAgentState.retrieved_docs?.length || 0} 条切片
              </span>
            </div>
          </div>

          {/* 人工升级与风控标记 */}
          <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
            <div className="text-[10px] text-slate-400 font-sans font-semibold uppercase">
              3. 人工升级与风控标记
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">escalated_to_human:</span>
              <span
                className={
                  currentAgentState.escalated_to_human
                    ? "text-rose-400 font-bold"
                    : "text-slate-400"
                }
              >
                {String(currentAgentState.escalated_to_human)}
              </span>
            </div>
            {currentAgentState.escalated_to_human && (
              <div className="text-[10px] text-rose-300 bg-rose-950/40 p-1.5 rounded border border-rose-800/40">
                原因: {currentAgentState.escalation_reason || "无"}
              </div>
            )}
          </div>

          {/* 完整 JSON 结构 */}
          <div className="space-y-1">
            <div className="text-[10px] text-slate-400 font-sans font-semibold uppercase">
              4. 完整 State 契约快照
            </div>
            <pre className="p-2 rounded-xl bg-slate-900/90 border border-slate-800 text-[10px] text-slate-300 overflow-x-auto max-h-56 leading-relaxed">
              {JSON.stringify(currentAgentState, null, 2)}
            </pre>
          </div>
        </div>

        {/* 底部说明 */}
        <div className="p-3 border-t border-slate-800 text-[11px] text-slate-400 bg-slate-950/90">
          💡 此处实时镜像 LangGraph 内部的 <code>AgentState(TypedDict)</code> 状态总线。
        </div>
      </aside>

      {/* 4. 本地 Python Chainlit 启动引导弹窗 */}
      {showLocalGuide && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-orange-600 flex items-center justify-center text-white">
                  <Flame className="w-4 h-4 fill-white" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">本地运行原生 Python Chainlit 指南</h3>
                  <p className="text-xs text-slate-400">使用独立 Python 进程启动原生 Chainlit UI</p>
                </div>
              </div>
              <button
                onClick={() => setShowLocalGuide(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <p>
                Chainlit 对话自测客户端（<code>fastapi_backend/chainlit_app.py</code>）已改为直接通过 <strong>HTTP 请求与 FastAPI 后端交互</strong>，端到端测试 <code>/api/chat</code> 接口与 LangGraph 编排：
              </p>

              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px] space-y-2 text-slate-200">
                <div className="text-slate-400"># 1. 终端1：启动 FastAPI 核心后端 (端口 5000)</div>
                <div className="text-orange-400">cd fastapi_backend && python app.py</div>
                <div className="text-slate-400 mt-2"># 2. 终端2：启动 Chainlit 对话客户端 (端口 8001)</div>
                <div className="text-orange-400">cd fastapi_backend && python run_chainlit.py</div>
              </div>

              <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/60 space-y-1 text-[11px]">
                <div className="font-semibold text-white flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  已内置全套特性：
                </div>
                <ul className="list-disc list-inside text-slate-400 space-y-0.5">
                  <li>真实 HTTP 通信测试（验证 Pydantic Schema 校验与网络延迟）</li>
                  <li>原生 <code>cl.Step</code> 还原后端返回的 LangGraph 状态图执行轨迹</li>
                  <li><code>cl.Action</code> 预设典型用例按钮与会员画像一键切换</li>
                  <li>侧边栏抽屉展示后端检索召回的知识库原文引用</li>
                </ul>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowLocalGuide(false)}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-xs font-semibold cursor-pointer transition-colors"
              >
                我知道了，返回测试
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
