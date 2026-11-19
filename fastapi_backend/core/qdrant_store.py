"""
Qdrant 向量数据库驱动与知识库检索服务 (Qdrant Vector Store Service)
运行模式: 原生官方 qdrant-client 纯内存模式 (QdrantClient(":memory:"))
特性: 零外部 Docker 容器依赖、毫秒级启动、1024 维 BGE-M3 余弦距离检索
"""

import threading
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from config import settings
from core.logger import cprint
from .embedding import bge_m3_engine
from data.faq_document import get_default_faq_chunks


def _create_qdrant_client() -> QdrantClient:
    if settings.QDRANT_HOST:
        return QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
        )
    return QdrantClient(location=settings.QDRANT_LOCATION)


class QdrantKnowledgeStore:
    def __init__(
        self,
        collection_name: str = settings.QDRANT_COLLECTION,
        dim: int = settings.EMBEDDING_DIM,
    ):
        self.collection_name = collection_name
        self.dim = dim
        self._lock = threading.RLock()
        # 仅创建客户端句柄，避免模块导入期即发起 Ollama HTTP 阻塞请求
        self.client = _create_qdrant_client()

    def init_collection_with_faq(self, force_reload: bool = False) -> None:
        """
        线程安全、幂等地初始化集合，并批量将 FAQ 政策切片向量化写入 Qdrant
        """
        with self._lock:
            if self.client.collection_exists(self.collection_name):
                if force_reload:
                    self.client.delete_collection(self.collection_name)
                else:
                    return

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

            faq_chunks = get_default_faq_chunks()
            if not faq_chunks:
                return

            embed_texts = [
                f"{chunk['title']}\n{chunk['content']}\n关键词: {', '.join(chunk.get('keywords', []))}"
                for chunk in faq_chunks
            ]
            vectors = bge_m3_engine.embed_documents(embed_texts)
            points = [
                PointStruct(id=idx + 1, vector=vector, payload=chunk)
                for idx, (chunk, vector) in enumerate(zip(faq_chunks, vectors))
            ]

            self.client.upsert(collection_name=self.collection_name, points=points)
            cprint.info(
                f"[Qdrant] 成功将 {len(points)} 条 FAQ 政策切片存入向量集合 '{self.collection_name}' ({self.dim}维 Cosine)"
            )

    def _ensure_ready(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.init_collection_with_faq()

    def similarity_search(
        self,
        query: str,
        k: int = settings.TOP_K_RETRIEVAL,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """对用户提问进行 BGE-M3 向量编码，并在 Qdrant 中执行余弦相似度检索"""
        self._ensure_ready()
        query_vector = bge_m3_engine.embed_query(query)
        threshold = score_threshold if score_threshold > 0 else None

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=k,
            score_threshold=threshold,
        )

        formatted: List[Dict[str, Any]] = []
        for hit in res.points:
            payload = hit.payload or {}
            formatted.append({
                "id": hit.id,
                "score": round(float(hit.score), 4),
                "doc": payload,
                "title": payload.get("title", ""),
                "category": payload.get("category", "售后政策"),
                "content": payload.get("content", ""),
                "tags": payload.get("tags", []),
            })
        return formatted

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """分页获取当前知识库中的全部切片 Payload"""
        self._ensure_ready()
        docs: List[Dict[str, Any]] = []
        offset = None
        while True:
            scroll_res, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            docs.extend(p.payload for p in scroll_res if p.payload)
            if next_offset is None:
                break
            offset = next_offset
        return docs


# 全局单例 Qdrant 知识库实例（懒初始化集合数据，由 app lifespan 或首次检索触发加载）
qdrant_store = QdrantKnowledgeStore()
