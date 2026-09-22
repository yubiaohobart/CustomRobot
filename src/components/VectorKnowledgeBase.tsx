import React, { useState, useEffect } from "react";
import { 
  Database, 
  Search, 
  Plus, 
  Trash2, 
  Sparkles, 
  Tag, 
  FileText, 
  CheckCircle2, 
  Sliders, 
  Clock, 
  AlertCircle 
} from "lucide-react";
import { KnowledgeDoc, SearchResult } from "../types";

export const VectorKnowledgeBase: React.FC = () => {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>("ALL");

  // Search tester state
  const [testQuery, setTestQuery] = useState("退换货运费谁来出？需要几天到账？");
  const [testMinScore, setTestMinScore] = useState<number>(0.3);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLatency, setSearchLatency] = useState<number | null>(null);

  // Add doc form state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<KnowledgeDoc["category"]>("售后政策");
  const [newContent, setNewContent] = useState("");
  const [newTags, setNewTags] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchDocs = async () => {
    try {
      const res = await fetch("/api/knowledge");
      if (res.ok) {
        const data = await res.json();
        setDocs(data.docs || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleTestSearch = async () => {
    if (!testQuery.trim()) return;
    setSearching(true);
    try {
      const res = await fetch("/api/knowledge/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: testQuery,
          topK: 4,
          minScore: testMinScore,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
        setSearchLatency(data.latencyMs);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSearching(false);
    }
  };

  const handleAddDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;
    setAdding(true);

    try {
      const tagsArray = newTags
        .split(/[,，\s]+/)
        .map((t) => t.trim())
        .filter(Boolean);

      const res = await fetch("/api/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          category: newCategory,
          content: newContent,
          tags: tagsArray,
        }),
      });

      if (res.ok) {
        setShowAddModal(false);
        setNewTitle("");
        setNewContent("");
        setNewTags("");
        fetchDocs();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteDoc = async (id: string) => {
    if (!window.confirm("确定删除此条知识库条目吗？")) return;
    try {
      const res = await fetch(`/api/knowledge/${id}`, { method: "DELETE" });
      if (res.ok) {
        fetchDocs();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const categories = ["ALL", "售后政策", "特殊规则", "账务与退款", "维修保修"];

  const filteredDocs = activeCategory === "ALL" 
    ? docs 
    : docs.filter((d) => d.category === activeCategory);

  return (
    <div className="flex-1 h-[calc(100vh-4.5rem)] overflow-y-auto bg-slate-50 p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-indigo-600" />
            <h1 className="text-xl font-bold text-slate-900">Qdrant 向量数据库与本地 Ollama (BGE-M3) 知识库中枢</h1>
            <span className="px-2 py-0.5 text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
              纯内存模式 (In-Memory) · 无需 Docker
            </span>
            <span className="px-2 py-0.5 text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200 rounded-md">
              本地 Ollama (bge-m3:1024维)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            采用纯内存 (Memory :memory:) 嵌入式向量计算，无需使用 Docker 部署独立容器，开箱即用。由本地 Ollama 驱动的 BGE-M3 (1024维密集向量) 与 Qdrant 余弦相似度构建的高性能 RAG 检索体系，默认加载《XX商城售后服务与退换货政策（2026版）》
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors shadow-xs cursor-pointer self-start"
        >
          <Plus className="w-4 h-4" />
          新增知识文档分块
        </button>
      </div>

      {/* Vector Search Diagnostic Tester */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <h2 className="text-sm font-bold text-slate-900">向量语义相似度检索测试台 (Vector Search Sandbox)</h2>
          </div>
          {searchLatency !== null && (
            <span className="text-xs text-indigo-600 font-mono bg-indigo-50 px-2 py-0.5 rounded">
              耗时: {searchLatency}ms • 召回: {searchResults.length} 条
            </span>
          )}
        </div>

        <div className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
            <input
              type="text"
              value={testQuery}
              onChange={(e) => setTestQuery(e.target.value)}
              placeholder="输入任何客户日常口语化提问进行向量匹配验证..."
              className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-50 focus:bg-white text-slate-800 rounded-xl border border-slate-200 focus:outline-hidden focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto">
            <span className="text-xs text-slate-500 whitespace-nowrap">阈值: {testMinScore}</span>
            <input
              type="range"
              min="0.1"
              max="0.8"
              step="0.05"
              value={testMinScore}
              onChange={(e) => setTestMinScore(parseFloat(e.target.value))}
              className="w-24 accent-indigo-600"
            />
            <button
              onClick={handleTestSearch}
              disabled={searching || !testQuery.trim()}
              className="flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 rounded-xl transition-colors cursor-pointer"
            >
              <span>{searching ? "检索中..." : "测试向量召回"}</span>
            </button>
          </div>
        </div>

        {/* Search Results Display */}
        {searchResults.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100 space-y-2.5">
            <div className="text-xs font-semibold text-slate-700">余弦相似度召回结果 (Top Ranked Chunks):</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {searchResults.map((res, i) => (
                <div key={i} className="p-3 bg-indigo-50/50 rounded-xl border border-indigo-100 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">{res.doc.title}</span>
                    <span className="px-2 py-0.5 bg-indigo-600 text-white font-mono text-[10px] rounded-full">
                      {(res.score * 100).toFixed(1)}% 匹配度
                    </span>
                  </div>
                  <p className="text-slate-600 leading-relaxed text-[11px] line-clamp-3">{res.doc.content}</p>
                  <div className="pt-1 flex items-center justify-between text-[10px] text-slate-400">
                    <span>分类: {res.doc.category}</span>
                    <span>文档ID: {res.doc.id}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Category Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setActiveCategory(c)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors whitespace-nowrap cursor-pointer ${
              activeCategory === c
                ? "bg-indigo-600 text-white shadow-xs"
                : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
            }`}
          >
            {c === "ALL" ? `全部知识 (${docs.length})` : c}
          </button>
        ))}
      </div>

      {/* Knowledge Documents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredDocs.map((doc) => (
          <div
            key={doc.id}
            className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] rounded-md font-medium border border-slate-200">
                  {doc.category}
                </span>
                <span className="text-[10px] font-mono text-slate-400">{doc.id}</span>
              </div>
              <h3 className="text-sm font-bold text-slate-800 mb-2 leading-snug">{doc.title}</h3>
              <p className="text-xs text-slate-600 leading-relaxed line-clamp-4">{doc.content}</p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <div className="flex flex-wrap gap-1">
                {doc.tags.slice(0, 3).map((t, idx) => (
                  <span key={idx} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] rounded">
                    #{t}
                  </span>
                ))}
              </div>
              <button
                onClick={() => handleDeleteDoc(doc.id)}
                title="删除条目"
                className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Document Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 p-6">
            <h2 className="text-base font-bold text-slate-900 mb-4">新增向量知识库文档</h2>
            <form onSubmit={handleAddDoc} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">文档标题 / 政策名称</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="例如：生鲜商品售后退款特殊约定"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-hidden focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">所属服务分类</label>
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as any)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-hidden"
                >
                  <option value="售后政策">售后政策</option>
                  <option value="账单发票">账单发票</option>
                  <option value="配送物流">配送物流</option>
                  <option value="账户安全">账户安全</option>
                  <option value="VIP服务">VIP服务</option>
                  <option value="产品使用">产品使用</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">检索关键词标签 (以逗号分隔)</label>
                <input
                  type="text"
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  placeholder="例如：生鲜, 损耗, 24小时, 坏果包赔"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">知识条目详细内容 (用于向量分块与RAG生成)</label>
                <textarea
                  rows={4}
                  required
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="请详细录入业务标准流程、时效要求与售后细则..."
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-hidden resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={adding}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl cursor-pointer disabled:opacity-50"
                >
                  {adding ? "向量化中..." : "保存并向量化"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
