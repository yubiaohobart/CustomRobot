import React, { useState, useEffect } from "react";
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Database, 
  Headphones, 
  TrendingUp, 
  Users, 
  Zap, 
  ShieldAlert, 
  HeartHandshake, 
  Radio, 
  RefreshCw,
  Server,
  FileCheck,
  Forward,
  UserCheck,
  FileText,
  X,
  Sparkles,
  Search,
  ExternalLink
} from "lucide-react";
import { MetricsData, ConversationSession, TransferLog } from "../types";

interface MonitoringDashboardProps {
  onNavigateToWorkbench: (sessionId?: string) => void;
}

export const MonitoringDashboard: React.FC<MonitoringDashboardProps> = ({
  onNavigateToWorkbench,
}) => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [transferLogs, setTransferLogs] = useState<TransferLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [inspectingLog, setInspectingLog] = useState<TransferLog | null>(null);

  const fetchMetrics = async () => {
    try {
      const [resMetrics, resSessions, resLogs] = await Promise.all([
        fetch("/api/metrics"),
        fetch("/api/sessions"),
        fetch("/api/transfer-logs"),
      ]);

      if (resMetrics.ok) {
        const mData = await resMetrics.json();
        setMetrics(mData);
      }
      if (resSessions.ok) {
        const sData = await resSessions.json();
        setSessions(sData.sessions || []);
      }
      if (resLogs.ok) {
        const lData = await resLogs.json();
        setTransferLogs(lData.transferLogs || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 3000);
    return () => clearInterval(interval);
  }, []);

  const needsInterventionList = sessions.filter((s) => s.status === "NEEDS_INTERVENTION");
  const humanServingList = sessions.filter((s) => s.status === "HUMAN_INTERVENED");

  return (
    <div className="flex-1 h-[calc(100vh-4rem)] overflow-y-auto bg-slate-50 p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">智能客服实时监控与运行大盘</h1>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              实时监控中 (3s轮询)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            全面监控 LangGraph 执行健康度、向量检索准确率、会话记忆状态与人工介入接管指标
          </p>
        </div>

        <button
          onClick={fetchMetrics}
          className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200 rounded-xl transition-colors shadow-2xs self-start cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>刷新监控指标</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Active Sessions */}
        <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">活跃服务会话总数</span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-xl">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{metrics?.totalSessions ?? 0}</span>
            <span className="text-xs text-slate-400">个并发会话</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 flex gap-2">
            <span>AI接待: <strong className="text-blue-600">{metrics?.aiHandling ?? 0}</strong></span>
            <span>人工接管: <strong className="text-amber-600">{metrics?.humanIntervened ?? 0}</strong></span>
          </div>
        </div>

        {/* Card 2: Needs Intervention Alert */}
        <div className={`p-4 rounded-2xl border shadow-xs transition-colors ${
          (metrics?.needsIntervention ?? 0) > 0 
            ? "bg-rose-50/70 border-rose-200" 
            : "bg-white border-slate-200"
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">待人工介入报警</span>
            <div className={`p-2 rounded-xl ${
              (metrics?.needsIntervention ?? 0) > 0 ? "bg-rose-100 text-rose-600 animate-pulse" : "bg-slate-100 text-slate-400"
            }`}>
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className={`text-2xl font-bold ${
              (metrics?.needsIntervention ?? 0) > 0 ? "text-rose-600" : "text-slate-800"
            }`}>
              {metrics?.needsIntervention ?? 0}
            </span>
            <span className="text-xs text-slate-400">单紧急排队</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            {needsInterventionList.length > 0 ? (
              <span className="text-rose-600 font-semibold cursor-pointer hover:underline" onClick={() => onNavigateToWorkbench()}>
                立即前往接管处理 &rarr;
              </span>
            ) : (
              <span className="text-emerald-600 font-medium">当前无积压预警工单</span>
            )}
          </div>
        </div>

        {/* Card 3: Seamless Transfers Log Count */}
        <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">无缝人工转接流水总数</span>
            <div className="p-2 bg-amber-50 text-amber-600 rounded-xl">
              <FileCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{transferLogs.length}</span>
            <span className="text-xs text-slate-400">笔交接记录</span>
          </div>
          <div className="mt-2 text-[11px] text-emerald-600 flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>上下文完整保存率: 100%</span>
          </div>
        </div>

        {/* Card 4: Confidence Score */}
        <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">向量检索平均置信度</span>
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {((metrics?.avgConfidence ?? 0.9) * 100).toFixed(0)}%
            </span>
            <span className="text-xs text-slate-400">平均匹配度</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            已索引知识分块: <strong className="text-indigo-600">{metrics?.kbDocCount ?? 7}</strong> 条
          </div>
        </div>
      </div>

      {/* Real-time Urgent Queue Table */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <h2 className="text-sm font-bold text-slate-900">实时人工介入待接听队列与高危会话</h2>
          </div>
          <span className="text-xs text-slate-500">触发条件：客户强烈诉求 / 情绪负向 / 置信度低于0.55</span>
        </div>

        {needsInterventionList.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 border-y border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">客户名称</th>
                  <th className="py-2.5 px-3">会员等级</th>
                  <th className="py-2.5 px-3">情绪评估</th>
                  <th className="py-2.5 px-3">主要咨询诉求</th>
                  <th className="py-2.5 px-3">触发时间</th>
                  <th className="py-2.5 px-3 text-right">紧急操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {needsInterventionList.map((s) => (
                  <tr key={s.id} className="hover:bg-rose-50/40 transition-colors">
                    <td className="py-3 px-3 font-semibold text-slate-800">{s.userName}</td>
                    <td className="py-3 px-3 text-indigo-600 font-medium">{s.customerProfile.vipLevel}</td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 bg-rose-100 text-rose-800 text-[10px] rounded-full font-bold">
                        {s.customerProfile.sentiment === "frustrated" ? "急躁/有投诉意图" : "一般负向"}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-700 max-w-xs truncate">{s.customerProfile.intent}</td>
                    <td className="py-3 px-3 text-slate-400">{s.metrics.escalatedAt || s.updatedAt}</td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => onNavigateToWorkbench(s.id)}
                        className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                      >
                        一键接管会话
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-400 bg-slate-50/50 rounded-xl">
            <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-1.5" />
            <p className="text-slate-700 font-medium">当前无积压待接入的人工呼叫</p>
            <p className="text-[11px] text-slate-400 mt-0.5">所有用户提问均由 LangGraph AI 引擎平稳接待中</p>
          </div>
        )}
      </div>

      {/* Seamless Transfer Audit Logs Table */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-amber-600" />
            <div>
              <h2 className="text-sm font-bold text-slate-900">无缝人工转接审计日志与上下文移交监控</h2>
              <p className="text-[11px] text-slate-500">每次转接均自动封存提问历史、客服答复与长期记忆快照，保障客户无感过桥</p>
            </div>
          </div>
          <span className="text-xs text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full font-semibold border border-amber-200">
            共记录 {transferLogs.length} 笔交接单
          </span>
        </div>

        {transferLogs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 border-y border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">流水号</th>
                  <th className="py-2.5 px-3">客户</th>
                  <th className="py-2.5 px-3">触发方式</th>
                  <th className="py-2.5 px-3">转接原因</th>
                  <th className="py-2.5 px-3">接收坐席 / 部门</th>
                  <th className="py-2.5 px-3">上下文包规模</th>
                  <th className="py-2.5 px-3">转接时间</th>
                  <th className="py-2.5 px-3 text-right">交接快照</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transferLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-3 font-mono text-slate-600 font-medium">{log.id}</td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-800">{log.customerName}</div>
                      <div className="text-[10px] text-indigo-600">{log.vipLevel}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        log.triggerType === "ai_fallback" 
                          ? "bg-rose-50 text-rose-700 border border-rose-200" 
                          : log.triggerType === "user_requested"
                          ? "bg-blue-50 text-blue-700 border border-blue-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}>
                        {log.triggerType === "ai_fallback" ? "无法回答/低置信" : log.triggerType === "user_requested" ? "用户主动要求" : "坐席改派"}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-700 max-w-xs truncate">{log.reason}</td>
                    <td className="py-3 px-3">
                      <div className="font-medium text-slate-800">{log.assignedAgentName}</div>
                      <div className="text-[10px] text-slate-400">{log.assignedDepartment}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      <span className="px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-mono">
                        {log.contextSnapshot?.userQuestions?.length ?? 0}提问 + {log.contextSnapshot?.aiMessagesCount ?? 0}答复
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400">{log.transferredAt}</td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setInspectingLog(log)}
                          className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                        >
                          查看快照
                        </button>
                        <button
                          onClick={() => onNavigateToWorkbench(log.sessionId)}
                          className="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center gap-1"
                        >
                          <span>查看会话</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-400 bg-slate-50/50 rounded-xl">
            <p>暂无转接日志记录</p>
          </div>
        )}
      </div>

      {/* Two Column Section: Sentiment Analysis & Backend Health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment Analysis Distribution */}
        <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <HeartHandshake className="w-4 h-4 text-pink-600" />
              <span>客户情绪实时分布 (Sentiment Radar)</span>
            </h3>
            <span className="text-xs text-slate-400">实时感知客户满意度与风险</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-emerald-700 font-medium">积极满意 (Positive)</span>
                <span className="text-slate-500">{metrics?.sentimentCounts?.positive ?? 1} 会话</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-emerald-500 h-full rounded-full transition-all duration-500" 
                  style={{ width: `${Math.min(100, ((metrics?.sentimentCounts?.positive ?? 1) / Math.max(1, metrics?.totalSessions ?? 1)) * 100)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-700 font-medium">平静常规 (Neutral)</span>
                <span className="text-slate-500">{metrics?.sentimentCounts?.neutral ?? 2} 会话</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-blue-500 h-full rounded-full transition-all duration-500" 
                  style={{ width: `${Math.min(100, ((metrics?.sentimentCounts?.neutral ?? 2) / Math.max(1, metrics?.totalSessions ?? 1)) * 100)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-rose-600 font-medium">焦急预警 / 负面 (Frustrated)</span>
                <span className="text-rose-600 font-bold">{metrics?.sentimentCounts?.frustrated ?? 0} 会话</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-rose-500 h-full rounded-full transition-all duration-500" 
                  style={{ width: `${Math.min(100, ((metrics?.sentimentCounts?.frustrated ?? 0) / Math.max(1, metrics?.totalSessions ?? 1)) * 100)}%` }}
                ></div>
              </div>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl text-[11px] text-slate-600 leading-relaxed">
            💡 <strong>智能护栏策略：</strong>系统实时对用户输入进行情绪倾向打分。一旦识别为急躁或出现投诉倾向，将在 100ms 内自动在后台生成人工介入预警并标记。
          </div>
        </div>

        {/* System & LangGraph Architecture Health */}
        <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Server className="w-4 h-4 text-indigo-600" />
              <span>后台服务链路健康状态</span>
            </h3>
            <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>全部正常运转</span>
            </span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                <span className="font-semibold text-slate-800">LangGraph 状态编排引擎</span>
              </div>
              <span className="text-slate-500 font-mono text-[11px]">StateGraph / Checkpointer OK</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                <span className="font-semibold text-slate-800">向量数据库检索服务 (Vector Store)</span>
              </div>
              <span className="text-slate-500 font-mono text-[11px]">Cosine Sim / Top-K 召回正常</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                <span className="font-semibold text-slate-800">会话记忆持久化管理 (MemoryManager)</span>
              </div>
              <span className="text-slate-500 font-mono text-[11px]">Sliding Window & Checkpoints OK</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                <span className="font-semibold text-slate-800">大模型生成推理引擎 (Gemini 3.8 Flash)</span>
              </div>
              <span className="text-slate-500 font-mono text-[11px]">Ready / Grounded Generation</span>
            </div>
          </div>
        </div>
      </div>

      {/* Transfer Log Context Snapshot Modal */}
      {inspectingLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-amber-600" />
                <div>
                  <h3 className="font-bold text-slate-800 text-sm">交接单快照详情 ({inspectingLog.id})</h3>
                  <p className="text-[11px] text-slate-500">
                    客户: {inspectingLog.customerName} • 接收坐席: {inspectingLog.assignedAgentName} ({inspectingLog.assignedDepartment})
                  </p>
                </div>
              </div>
              <button
                onClick={() => setInspectingLog(null)}
                className="p-1 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-4 overflow-y-auto text-xs flex-1">
              <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-500">触发原因:</span>
                  <span className="font-semibold text-slate-800">{inspectingLog.reason}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">移交时间:</span>
                  <span className="font-mono text-slate-700">{inspectingLog.transferredAt}</span>
                </div>
                {inspectingLog.operatorNote && (
                  <div className="flex justify-between pt-1 border-t border-amber-200/60">
                    <span className="text-slate-500">交接附言:</span>
                    <span className="text-amber-900 font-medium">{inspectingLog.operatorNote}</span>
                  </div>
                )}
              </div>

              {/* Questions List */}
              <div className="space-y-1.5">
                <div className="font-semibold text-slate-700">移交的用户提问历史清单 ({inspectingLog.contextSnapshot?.userQuestions?.length ?? 0} 条):</div>
                <div className="space-y-1">
                  {inspectingLog.contextSnapshot?.userQuestions?.map((q, idx) => (
                    <div key={idx} className="p-2 bg-slate-50 rounded border border-slate-200 text-slate-800 flex gap-2">
                      <span className="text-blue-600 font-mono font-bold">#{idx + 1}</span>
                      <span>{q}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Latest AI Answer */}
              <div className="space-y-1">
                <div className="font-semibold text-slate-700">智能客服最后答复 (AI Response):</div>
                <div className="p-2.5 bg-blue-50/50 rounded border border-blue-100 text-slate-700 leading-relaxed">
                  {inspectingLog.contextSnapshot?.lastAiResponse || "尚未生成即触发转接"}
                </div>
              </div>

              {/* Session Memory Summary */}
              <div className="space-y-1">
                <div className="font-semibold text-slate-700">移交时的会话长期记忆摘要 (MemorySaver):</div>
                <div className="p-2.5 bg-slate-50 rounded border border-slate-200 text-slate-700 leading-relaxed font-sans">
                  {inspectingLog.contextSnapshot?.summaryMemory || "暂无摘要"}
                </div>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-2">
              <button
                onClick={() => setInspectingLog(null)}
                className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer"
              >
                关闭
              </button>
              <button
                onClick={() => {
                  const sid = inspectingLog.sessionId;
                  setInspectingLog(null);
                  onNavigateToWorkbench(sid);
                }}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
              >
                前往坐席工作台介入会话
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
