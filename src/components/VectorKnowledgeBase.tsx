import React, { useState, useEffect, useRef } from "react";
import {
  Database,
  Search,
  Sparkles,
  BookOpen,
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { KnowledgeDoc, SearchResult } from "../types";

export const VectorKnowledgeBase: React.FC = () => {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>("ALL");

  // Upload state
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Search tester state
  const [testQuery, setTestQuery] = useState("退换货运费谁来出？需要几天到账？");
  const [testMinScore, setTestMinScore] = useState<number>(0.3);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLatency, setSearchLatency] = useState<number | null>(null);

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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = Array.from(e.target.files || []);
    setUploadFeedback(null);
    const invalid = fileList.find((f) => !f.name.toLowerCase().endsWith(".docx"));
    if (invalid) {
      setSelectedFiles([]);
      setUploadFeedback({
        type: "error",
        text: `仅支持 .docx 格式文件，请重新选择（不支持 ${invalid.name}）`,
      });
      return;
    }
    setSelectedFiles(fileList);
  };

  const handleUploadDocx = async () => {
    if (selectedFiles.length === 0 || uploading) return;
    setUploading(true);
    setUploadFeedback(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append("files", file));

      const res = await fetch("/api/knowledge/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setUploadFeedback({
          type: "error",
          text: data.detail || "文档上传或向量化失败，请检查文件格式与 Ollama 服务状态",
        });
        return;
      }

      setUploadFeedback({
        type: "success",
        text: `已清空旧库并重建索引：导入 ${(data.files || []).join("、")}，共 ${data.chunkCount} 条切片（耗时 ${data.latencyMs}ms）`,
      });
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setActiveCategory("ALL");
      setSearchResults([]);
      await fetchDocs();
    } catch (e) {
      console.error(e);
      setUploadFeedback({
        type: "error",
        text: "网络或服务异常，上传更新失败",
      });
    } finally {
      setUploading(false);
    }
  };

  const categories = ["ALL", ...Array.from(new Set(docs.map((d) => d.category).filter(Boolean)))];

  const filteredDocs = activeCategory === "ALL" 
    ? docs 
    : docs.filter((d) => d.category === activeCategory);

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-indigo-600" />
            <h1 className="text-xl font-bold text-slate-900">Qdrant 向量数据库与本地 Ollama (BGE-M3) 知识库中枢</h1>
            <span className="px-2 py-0.5 text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
              Qdrant Hybrid (Dense + Sparse RRF)
            </span>
            <span className="px-2 py-0.5 text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200 rounded-md">
              本地 Ollama (bge-m3:1024维)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            支持上传企业 .docx 文档自动解析切片并重建 Qdrant 混合向量索引（Dense 语义 + Sparse IDF 词法融合检索）。
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-2xs">
          <BookOpen className="w-4 h-4 text-indigo-600" />
          <span>知识分块数: <strong className="text-indigo-600 font-mono">{docs.length}</strong> 篇</span>
        </div>
      </div>

      {/* Upload .docx to Rebuild Knowledge Base */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-indigo-600" />
            <h2 className="text-sm font-bold text-slate-900">上传企业文档更新索引 (.docx)</h2>
          </div>
          <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-0.5 rounded-md">
            上传成功后将自动清空旧知识库并全量重建索引（支持同时多选 .docx）
          </span>
        </div>

        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex-1 flex items-center justify-between gap-2 px-4 py-2.5 text-xs text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-xl border border-dashed border-slate-300 transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-2 truncate">
              <FileText className="w-4 h-4 text-indigo-500 shrink-0" />
              {selectedFiles.length > 0
                ? `已选择 ${selectedFiles.length} 个文件: ${selectedFiles.map((f) => f.name).join("、")}`
                : "点击选择一个或多个 .docx 文档..."}
            </span>
            <span className="text-[11px] text-indigo-600 font-medium shrink-0">浏览文件</span>
          </button>

          <button
            type="button"
            onClick={handleUploadDocx}
            disabled={uploading || selectedFiles.length === 0}
            className="flex items-center justify-center gap-1.5 px-4 py-2.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 rounded-xl transition-colors cursor-pointer whitespace-nowrap"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{uploading ? "解析与向量化重建中..." : "上传并重建知识库"}</span>
          </button>
        </div>

        {uploadFeedback && (
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs border ${
              uploadFeedback.type === "success"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-rose-50 text-rose-700 border-rose-200"
            }`}
          >
            {uploadFeedback.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span>{uploadFeedback.text}</span>
          </div>
        )}
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
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
