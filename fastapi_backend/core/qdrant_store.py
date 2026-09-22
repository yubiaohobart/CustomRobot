"""
Qdrant 向量数据库驱动与知识库检索服务 (Qdrant Vector Store Service)
负责：
1. 集合创建 (Collection: xx_mall_faq, 1024 维度, Distance.COSINE)
2. FAQ Markdown 结构化切片入库 (Upsert Points with Payload)
3. 向量相似度 Top-K 检索与元数据过滤
"""

import os
from typing import List, Dict, Any, Optional
from config import settings
from .embedding import bge_m3_engine
from data.faq_document import get_default_faq_chunks

# 尝试导入官方 qdrant_client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    HAS_QDRANT_CLIENT = True
except ImportError:
    HAS_QDRANT_CLIENT = False
    QdrantClient = None
    qmodels = None

class QdrantKnowledgeStore:
    def __init__(
        self,
        collection_name: str = settings.QDRANT_COLLECTION,
        dim: int = settings.EMBEDDING_DIM
    ):
        self.collection_name = collection_name
        self.dim = dim
        self.client = None
        self.is_native_qdrant = False
        self._fallback_points: List[Dict[str, Any]] = []

        self._init_qdrant()
        self.init_collection_with_faq()

    def _init_qdrant(self):
        """初始化 Qdrant 实例：优先采用纯内存 (memory) 方式，无需任何 Docker 容器"""
        if HAS_QDRANT_CLIENT:
            try:
                # 默认纯内存模式 :memory: 无需 Docker 部署
                if not settings.QDRANT_HOST and (not settings.QDRANT_LOCATION or settings.QDRANT_LOCATION == ":memory:"):
                    print("[Qdrant] 启动纯内存向量数据库 (:memory:)... 零外部容器依赖，无需 Docker！")
                    self.client = QdrantClient(":memory:")
                elif settings.QDRANT_HOST:
                    print(f"[Qdrant] 连接到指定远端 Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
                    self.client = QdrantClient(
                        host=settings.QDRANT_HOST,
                        port=settings.QDRANT_PORT,
                        api_key=settings.QDRANT_API_KEY
                    )
                else:
                    print(f"[Qdrant] 使用本地文件目录模式: {settings.QDRANT_LOCATION}")
                    self.client = QdrantClient(path=settings.QDRANT_LOCATION)

                self.is_native_qdrant = True
                print("[Qdrant] Qdrant 内存向量引擎初始化就绪 (In-Memory 1024-dim Cosine)，运行良好！")
                return
            except Exception as e:
                print(f"[Qdrant Warning] 内存向量引擎初始化警告: {e}，启用内置高性能内存余弦计算引擎。")

        print("[Qdrant] 采用内置进程级高并发内存向量库 (1024 维余弦相似度，无需 Docker 部署)。")
        self.is_native_qdrant = False

    def init_collection_with_faq(self, force_reload: bool = False):
        """
        初始化集合，并将 XX商城售后服务与退换货政策（2026版）切片存入 Qdrant
        """
        faq_chunks = get_default_faq_chunks()
        
        # 1. 针对原生 QdrantClient 的集合创建与数据注入
        if self.is_native_qdrant and self.client:
            try:
                collections = self.client.get_collections().collections
                exists = any(c.name == self.collection_name for c in collections)
                
                if exists and force_reload:
                    self.client.delete_collection(self.collection_name)
                    exists = False

                if not exists:
                    print(f"[Qdrant] Creating collection '{self.collection_name}' (dim={self.dim}, distance=COSINE)...")
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE)
                    )

                # 计算切片向量并存入 Qdrant
                points = []
                for idx, chunk in enumerate(faq_chunks):
                    # 组合标题与正文进行全面向量化
                    embed_text = f"{chunk['title']}\n{chunk['content']}\n关键词: {', '.join(chunk.get('keywords', []))}"
                    vector = bge_m3_engine.embed_query(embed_text)
                    
                    points.append(
                        PointStruct(
                            id=idx + 1,
                            vector=vector,
                            payload=chunk
                        )
                    )

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                print(f"[Qdrant] Successfully upserted {len(points)} FAQ chunks into Qdrant collection '{self.collection_name}'!")
                return
            except Exception as e:
                print(f"[Qdrant Error] Failed during native Qdrant operations: {e}. Using fallback storage.")

        # 2. 轻量内置内存向量仓库（同样使用 1024 维余弦度量）
        self._fallback_points = []
        for idx, chunk in enumerate(faq_chunks):
            embed_text = f"{chunk['title']}\n{chunk['content']}\n关键词: {', '.join(chunk.get('keywords', []))}"
            vector = bge_m3_engine.embed_query(embed_text)
            self._fallback_points.append({
                "id": idx + 1,
                "vector": vector,
                "payload": chunk
            })
        print(f"[Qdrant Store] Loaded {len(self._fallback_points)} FAQ chunks into in-memory collection '{self.collection_name}'.")

    def similarity_search(
        self,
        query: str,
        k: int = settings.TOP_K_RETRIEVAL,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        使用 BGE-M3 对用户提问进行向量编码，并在 Qdrant 中执行余弦距离相似度匹配
        """
        query_vector = bge_m3_engine.embed_query(query)

        # 1. 如果原生 Qdrant 客户端可用
        if self.is_native_qdrant and self.client:
            try:
                # 兼容 qdrant-client 新旧版本的 search / query_points
                search_result = []
                if hasattr(self.client, "search"):
                    search_result = self.client.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        limit=k,
                        score_threshold=score_threshold
                    )
                elif hasattr(self.client, "query_points"):
                    res = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        limit=k
                    )
                    search_result = res.points

                formatted = []
                for hit in search_result:
                    payload = hit.payload or {}
                    formatted.append({
                        "id": hit.id,
                        "score": round(float(hit.score), 4),
                        "doc": payload,
                        "title": payload.get("title", ""),
                        "category": payload.get("category", "售后政策"),
                        "content": payload.get("content", ""),
                        "tags": payload.get("tags", [])
                    })
                return formatted
            except Exception as e:
                print(f"[Qdrant Search Error] Native search error: {e}, using internal fallback.")

        # 2. 内置余弦相似度计算
        results = []
        for item in self._fallback_points:
            doc_vec = item["vector"]
            # 计算两向量内积（两者均为 L2 归一化向量，内积即 Cosine 相似度）
            cos_sim = sum(a * b for a, b in zip(query_vector, doc_vec))
            cos_sim = max(0.0, min(1.0, cos_sim))

            # 针对强关键词匹配做精准微调提升
            q_lower = query.lower()
            payload = item["payload"]
            for kw in payload.get("keywords", []):
                if kw.lower() in q_lower:
                    cos_sim = min(0.98, cos_sim + 0.12)
                    break

            if cos_sim >= score_threshold:
                results.append({
                    "id": item["id"],
                    "score": round(float(cos_sim), 4),
                    "doc": payload,
                    "title": payload.get("title", ""),
                    "category": payload.get("category", "售后政策"),
                    "content": payload.get("content", ""),
                    "tags": payload.get("tags", [])
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """获取当前知识库中的全部切片"""
        if self.is_native_qdrant and self.client:
            try:
                scroll_res, _ = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    with_payload=True,
                    with_vectors=False
                )
                return [p.payload for p in scroll_res if p.payload]
            except Exception:
                pass
        return [item["payload"] for item in self._fallback_points]

# 全局单例 Qdrant 知识库实例
qdrant_store = QdrantKnowledgeStore()
