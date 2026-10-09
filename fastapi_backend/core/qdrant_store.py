"""
Qdrant 向量数据库驱动与知识库检索服务 (Qdrant Vector Store Service)
运行模式: 原生官方 qdrant-client 纯内存模式 (QdrantClient(":memory:"))
特性: 零外部 Docker 容器依赖、毫秒级启动、1024 维 BGE-M3 余弦距离检索
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from config import settings
from .embedding import bge_m3_engine
from data.faq_document import get_default_faq_chunks


class QdrantKnowledgeStore:
    def __init__(
        self,
        collection_name: str = settings.QDRANT_COLLECTION,
        dim: int = settings.EMBEDDING_DIM
    ):
        self.collection_name = collection_name
        self.dim = dim
        # 1. 初始化纯内存 Qdrant 客户端 (无需任何 Docker 或独立进程)
        self.client = QdrantClient(":memory:")
        self.init_collection_with_faq()

    def init_collection_with_faq(self, force_reload: bool = False):
        """
        初始化集合，并将 XX商城售后服务与退换货政策（2026版）切片存入 Qdrant 内存库
        """
        existing_collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing_collections:
            if force_reload:
                self.client.delete_collection(self.collection_name)
            else:
                return

        # 创建 1024 维余弦距离向量集合
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE)
        )

        # 向量化 FAQ 结构化切片并存入 Qdrant
        faq_chunks = get_default_faq_chunks()
        points = []
        for idx, chunk in enumerate(faq_chunks):
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
        print(f"[Qdrant] 成功将 {len(points)} 条 FAQ 政策切片存入内存向量集合 '{self.collection_name}' (1024维 Cosine)")

    def similarity_search(
        self,
        query: str,
        k: int = settings.TOP_K_RETRIEVAL,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        对用户提问进行 BGE-M3 向量编码，并在 Qdrant 内存库中执行余弦相似度检索
        """
        query_vector = bge_m3_engine.embed_query(query)
        threshold = score_threshold if score_threshold > 0 else None

        # 直接使用 Qdrant 官方最新标准的 query_points 接口进行向量检索
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=k,
            score_threshold=threshold
        )
        hits = res.points

        formatted = []
        for hit in hits:
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

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """获取当前知识库中的全部切片 Payload"""
        scroll_res, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        return [p.payload for p in scroll_res if p.payload]


# 全局单例 Qdrant 知识库实例
qdrant_store = QdrantKnowledgeStore()
