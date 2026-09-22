import React, { useState } from "react";
import { 
  GitBranch, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Database, 
  Brain, 
  ShieldCheck, 
  Headphones, 
  ArrowRight, 
  FileCode, 
  Layers,
  Sparkles,
  Zap
} from "lucide-react";

interface NodeDetail {
  id: string;
  name: string;
  type: "router" | "rag" | "memory" | "llm" | "guardrail" | "human" | "checkpoint";
  description: string;
  inputs: string[];
  outputs: string[];
  pythonCode: string;
}

const NODES_DATA: NodeDetail[] = [
  {
    id: "query_analysis",
    name: "1. 语义意图与情感初筛节点 (Query Analyzer)",
    type: "router",
    description: "接收用户输入，提取关键词并判断是否带有强烈的情绪倾向（如急躁、愤怒、投诉）或显式'转人工'指令。",
    inputs: ["user_message: str", "session_id: str"],
    outputs: ["intent: str", "sentiment: str", "explicit_human_request: bool"],
    pythonCode: `def analyze_query_node(state: AgentState) -> dict:
    msg = state["user_message"].lower()
    explicit = any(k in msg for k in ["转人工", "投诉", "主管"])
    sentiment = "frustrated" if explicit or "差评" in msg else "neutral"
    return {
        "intent": classify_intent(msg),
        "sentiment": sentiment,
        "explicit_human_request": explicit
    }`
  },
  {
    id: "vector_retrieval",
    name: "2. 向量检索与知识抽取节点 (Qdrant + BGE-M3)",
    type: "rag",
    description: "调用本地 Ollama (bge-m3 1024维) 将用户问题编码为稠密向量，在 Qdrant 纯内存集合中计算余弦相似度，召回 Top-K 售后知识切片与分数。",
    inputs: ["user_message: str", "top_k: int = 3"],
    outputs: ["retrieved_docs: List[Document]", "top_similarity_score: float"],
    pythonCode: `def qdrant_retrieve_node(state: AgentState) -> dict:
    query = state["user_message"]
    # 本地 Ollama (bge-m3) 编码 + Qdrant 纯内存检索
    hits = qdrant_store.similarity_search(query, k=3)
    top_score = hits[0]["score"] if hits else 0.0
    return {
        "retrieved_docs": [h["doc"] for h in hits],
        "top_similarity_score": float(top_score)
    }`
  },
  {
    id: "memory_synthesis",
    name: "3. 会话长期记忆与上下文融合节点 (Memory Synthesizer)",
    type: "memory",
    description: "从 MemorySaver 与会话存储提取前序滑动对话历史与压缩摘要，将客户画像（VIP等级/订单）、历史问答与检索到的向量知识组装为强化 Prompt。",
    inputs: ["session_id: str", "retrieved_docs: List", "user_profile: dict"],
    outputs: ["assembled_prompt: str", "customer_profile: dict"],
    pythonCode: `def memory_synthesis_node(state: AgentState) -> dict:
    summary = state.get("summary_memory", "")
    profile = state.get("user_profile", {})
    context = assemble_rag_context(state["retrieved_docs"], summary, profile)
    return {"assembled_prompt": context}`
  },
  {
    id: "llm_generate",
    name: "4. 大模型生成推理节点 (DeepSeek Generator)",
    type: "llm",
    description: "调用 DeepSeek (deepseek-chat) 执行多源融合推理，结合商城售后合规条款生成准确、有同理心、有依据的解答文本。",
    inputs: ["assembled_prompt: str", "system_prompt: str"],
    outputs: ["generated_response: str", "generation_latency_ms: int"],
    pythonCode: `async def deepseek_generate_node(state: AgentState) -> dict:
    response = await deepseek_client.generate_response(
        user_message=state["user_message"],
        retrieved_docs=state["retrieved_docs"],
        summary_memory=state.get("summary_memory", ""),
        user_profile=state.get("user_profile")
    )
    return {
        "generated_response": response,
        "escalated_to_human": False
    }`
  },
  {
    id: "guardrail_eval",
    name: "5. 质量护栏与人工介入决策节点 (Guardrail & Escalation)",
    type: "guardrail",
    description: "条件分支路由器。检查置信度是否低于 0.55、客户是否要求转人工或情绪是否负向。若满足任一条件，触发人工接入队列；否则直接投递 AI 回复。",
    inputs: ["top_similarity_score: float", "sentiment: str", "explicit_human_request: bool"],
    outputs: ["route_decision: 'human_escalation' | 'deliver_response'"],
    pythonCode: `def route_decision_edge(state: AgentState) -> str:
    if state.get("explicit_human_request") or state["sentiment"] == "frustrated":
        return "human_escalation"
    if state.get("top_similarity_score", 0) < 0.55:
        return "human_escalation"
    return "deliver_response"`
  },
  {
    id: "human_escalation",
    name: "6. 人工客服介入与抢占节点 (Human Intervention Node)",
    type: "human",
    description: "挂起会话自动应答，向客服主管监控座席推送紧急警报工单，保存中断状态以待人工客服在线接管回复。",
    inputs: ["session_id: str", "escalation_reason: str"],
    outputs: ["session_status: 'NEEDS_INTERVENTION'", "notified_agents: List"],
    pythonCode: `def human_escalation_node(state: AgentState) -> dict:
    # 挂起AI并打上待人工接入标签
    session_manager.mark_needs_intervention(
        state["session_id"],
        reason="Low confidence or customer frustration"
    )
    # 推送 WebSocket 广播到人工座席工作台
    notify_agent_workbench(state["session_id"])
    return {"escalated_to_human": True}`
  },
  {
    id: "checkpoint_memory",
    name: "7. 状态快照固化节点 (LangGraph Checkpointer)",
    type: "checkpoint",
    description: "将当前轮次的所有状态、意图标签、记忆摘要更新保存到 Checkpoint 存储器，支持会话无损恢复与回溯。",
    inputs: ["AgentState: complete dict"],
    outputs: ["checkpoint_id: str", "persisted_at: str"],
    pythonCode: `def checkpoint_state_node(state: AgentState) -> dict:
    cp_id = checkpointer.put(
        config={"configurable": {"thread_id": state["session_id"]}},
        checkpoint=state
    )
    return {"checkpoint_id": cp_id}`
  }
];

export const LangGraphVisualizer: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<NodeDetail>(NODES_DATA[0]);
  const [simulating, setSimulating] = useState(false);
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const [simScenario, setSimScenario] = useState<"normal" | "escalate">("escalate");

  const runSimulation = () => {
    setSimulating(true);
    setActiveStep(0);

    const steps = simScenario === "escalate" 
      ? [0, 1, 2, 3, 4, 5, 6] // triggers escalation
      : [0, 1, 2, 3, 4, 6];   // normal flow skips human escalation

    let currentIdx = 0;
    const interval = setInterval(() => {
      currentIdx++;
      if (currentIdx < steps.length) {
        setActiveStep(steps[currentIdx]);
        setSelectedNode(NODES_DATA[steps[currentIdx]]);
      } else {
        clearInterval(interval);
        setSimulating(false);
      }
    }, 900);
  };

  return (
    <div className="flex-1 h-[calc(100vh-4.5rem)] overflow-y-auto bg-slate-50 p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="w-6 h-6 text-indigo-600" />
            <h1 className="text-xl font-bold text-slate-900">LangGraph 智能客服状态图全链路编排</h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            基于 StateGraph 构建的条件分支状态机：动态路由、向量 RAG 检索、记忆合成、质量护栏与人工介入决策
          </p>
        </div>

        {/* Simulation Controls */}
        <div className="flex items-center gap-2 self-start">
          <select
            value={simScenario}
            onChange={(e) => setSimScenario(e.target.value as any)}
            className="px-3 py-1.5 bg-white border border-slate-200 text-xs text-slate-700 rounded-xl focus:outline-hidden"
          >
            <option value="escalate">模拟场景：客户投诉/低置信度（触发人工介入）</option>
            <option value="normal">模拟场景：常规知识库问答（AI直接结单）</option>
          </select>
          <button
            onClick={runSimulation}
            disabled={simulating}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{simulating ? "模拟执行中..." : "单步演练链路"}</span>
          </button>
        </div>
      </div>

      {/* StateGraph Visual Architecture Pipeline */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            状态图节点拓扑 (StateGraph Execution Topology)
          </h2>
          <span className="text-[11px] text-slate-400">点击任意节点可检查 Python 实现与 I/O 状态定义</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {NODES_DATA.map((node, index) => {
            const isSelected = selectedNode.id === node.id;
            const isActive = activeStep === index;
            const isHumanNode = node.type === "human";

            return (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between relative ${
                  isActive
                    ? "bg-amber-100 border-amber-400 ring-2 ring-amber-300 shadow-md scale-105"
                    : isSelected
                    ? "bg-indigo-50 border-indigo-300 shadow-xs"
                    : isHumanNode
                    ? "bg-rose-50/70 border-rose-200 hover:border-rose-300"
                    : "bg-slate-50 border-slate-200 hover:border-slate-300"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold text-slate-400 font-mono">STEP {index + 1}</span>
                    {isActive && (
                      <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping"></span>
                    )}
                  </div>
                  <h3 className="text-xs font-bold text-slate-800 leading-snug mb-1">
                    {node.name.split(" ")[0]}
                  </h3>
                  <p className="text-[10px] text-slate-500 line-clamp-2">
                    {node.type}
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px]">
                  <span className={`font-semibold ${isHumanNode ? "text-rose-600" : "text-indigo-600"}`}>
                    {node.type.toUpperCase()}
                  </span>
                  <ArrowRight className="w-3 h-3 text-slate-400" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Node Deep Dive Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 5 Cols: Node Metadata & I/O Schema */}
        <div className="lg:col-span-5 p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="text-[10px] uppercase font-bold text-indigo-600 tracking-wider">节点详情剖析</span>
              <h3 className="text-base font-bold text-slate-900">{selectedNode.name}</h3>
            </div>
            <span className="px-2 py-0.5 bg-slate-100 text-slate-700 text-xs font-mono rounded-md">
              Node ID: {selectedNode.id}
            </span>
          </div>

          <div>
            <span className="text-xs font-semibold text-slate-700">功能职责概述:</span>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
              {selectedNode.description}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-100">
              <span className="font-semibold text-blue-900 block mb-1">输入状态 (Input Schema):</span>
              <ul className="space-y-0.5 font-mono text-[11px] text-blue-800">
                {selectedNode.inputs.map((inp, i) => (
                  <li key={i}>&bull; {inp}</li>
                ))}
              </ul>
            </div>

            <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100">
              <span className="font-semibold text-emerald-900 block mb-1">产出状态 (Output Updates):</span>
              <ul className="space-y-0.5 font-mono text-[11px] text-emerald-800">
                {selectedNode.outputs.map((out, i) => (
                  <li key={i}>&bull; {out}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Right 7 Cols: Python / LangGraph Implementation Code */}
        <div className="lg:col-span-7 p-5 bg-slate-900 rounded-2xl border border-slate-800 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold text-slate-200">LangGraph Python 节点函数实现</span>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">graph_pipeline.py</span>
            </div>

            <pre className="text-xs font-mono text-emerald-300 bg-slate-950 p-4 rounded-xl overflow-x-auto leading-relaxed border border-slate-800">
              {selectedNode.pythonCode}
            </pre>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <span>支持与 Flask 框架的 `/api/chat` 及 `/api/intervene` 无缝互通</span>
            <span className="text-indigo-400 font-semibold">StateGraph Standard</span>
          </div>
        </div>
      </div>
    </div>
  );
};
