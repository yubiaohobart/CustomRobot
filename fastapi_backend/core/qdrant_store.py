"""
Qdrant 向量数据库驱动与知识库检索服务 (Qdrant Vector Store Service)
运行模式: 原生官方 qdrant-client 纯内存模式 (QdrantClient(":memory:"))
特性: 零外部 Docker 容器依赖、毫秒级启动、1024 维 BGE-M3 余弦距离检索
"""

import threading
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    PointIdsList,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from config import settings
from core.logger import cprint
from .embedding import bge_m3_engine, build_sparse_vector
from data.faq_document import get_default_faq_chunks


def _create_qdrant_client() -> QdrantClient:
    if settings.QDRANT_HOST:
        return QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
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
        self._ready = False
        # 仅创建客户端句柄，避免模块导入期即发起 Ollama HTTP 阻塞请求
        self.client = _create_qdrant_client()

    @staticmethod
    def _build_embed_text(chunk: Dict[str, Any]) -> str:
        keywords = ", ".join(chunk.get("keywords", []))
        return f"{chunk['content']}\n关键词: {keywords}" if keywords else chunk["content"]

    def _has_hybrid_schema(self) -> bool:
        """检查已存在集合是否具备 dense + sparse(IDF) 混合向量结构"""
        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        sparse_vectors = info.config.params.sparse_vectors
        return (
            isinstance(vectors, dict)
            and "dense" in vectors
            and isinstance(sparse_vectors, dict)
            and "sparse" in sparse_vectors
        )

    def _scroll_points(self, with_payload: Any = True) -> List[Any]:
        """统一分页拉取集合中的 Point 记录"""
        points: List[Any] = []
        offset = None
        while True:
            scroll_res, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=with_payload,
                with_vectors=False,
            )
            points.extend(scroll_res)
            if next_offset is None:
                break
            offset = next_offset
        return points

    def _build_points(self, chunks: List[Dict[str, Any]], batch_size: int = 32) -> List[PointStruct]:
        """批量计算 Dense + Sparse 混合向量并组装 Qdrant PointStruct"""
        points: List[PointStruct] = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embed_texts = [self._build_embed_text(chunk) for chunk in batch]
            dense_vectors = bge_m3_engine.embed_documents(embed_texts)
            for chunk, dense_vec, text in zip(batch, dense_vectors, embed_texts):
                sp_idx, sp_val = build_sparse_vector(text)
                points.append(
                    PointStruct(
                        id=chunk["id"],
                        vector={
                            "dense": dense_vec,
                            "sparse": SparseVector(indices=sp_idx, values=sp_val),
                        },
                        payload=chunk,
                    )
                )
        return points

    def _create_hybrid_collection(self) -> None:
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={"dense": VectorParams(size=self.dim, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )

    def init_collection_with_faq(self, force_reload: bool = False) -> None:
        """
        线程安全、幂等且支持内容哈希增量的混合向量知识库同步：
        - 若集合已存在通过界面上传的企业文档（非 builtin_faq），重启时自动保留
        - 自动检测并升级旧版单向量集合为 dense + sparse(IDF) 结构
        - 仅对新增或变更切片重算向量，清理已下线切片
        """
        with self._lock:
            if self.client.collection_exists(self.collection_name):
                if force_reload or not self._has_hybrid_schema():
                    self.client.delete_collection(self.collection_name)

            if not self.client.collection_exists(self.collection_name):
                self._create_hybrid_collection()

            existing_points = self._scroll_points(with_payload=["content_hash", "source"])
            if not force_reload and any(
                (p.payload or {}).get("source", "builtin_faq") != "builtin_faq"
                for p in existing_points
            ):
                self._ready = True
                cprint.info(
                    f"[Qdrant] 检测到已上传的企业知识库 '{self.collection_name}' ({len(existing_points)} 条切片)，保留当前索引"
                )
                return

            faq_chunks = get_default_faq_chunks()
            existing_hashes = {
                p.id: (p.payload or {}).get("content_hash")
                for p in existing_points
            }

            desired_ids = {chunk["id"] for chunk in faq_chunks}
            stale_ids = [pid for pid in existing_hashes if pid not in desired_ids]
            changed_chunks = [
                chunk
                for chunk in faq_chunks
                if existing_hashes.get(chunk["id"]) != chunk.get("content_hash")
            ]

            if stale_ids:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=PointIdsList(points=stale_ids),
                )

            if changed_chunks:
                points = self._build_points(changed_chunks)
                self.client.upsert(collection_name=self.collection_name, points=points)

            self._ready = True
            if stale_ids or changed_chunks:
                cprint.info(
                    f"[Qdrant] 混合检索知识库同步完成 '{self.collection_name}': "
                    f"新增/更新 {len(changed_chunks)} 条，清理失效 {len(stale_ids)} 条，当前总计 {len(faq_chunks)} 条"
                )
            else:
                cprint.info(
                    f"[Qdrant] 混合检索知识库 '{self.collection_name}' 内容哈希一致 ({len(faq_chunks)} 条)，跳过重复向量化"
                )

    def replace_collection_with_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """先完成新文档切片向量计算，再清空旧集合并重建 Hybrid 索引（避免编码失败导致丢库）"""
        if not chunks:
            raise ValueError("待入库切片不能为空")

        with self._lock:
            points = self._build_points(chunks)
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            self._create_hybrid_collection()

            upsert_batch = 64
            for i in range(0, len(points), upsert_batch):
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points[i : i + upsert_batch],
                )

            self._ready = True
            cprint.info(
                f"[Qdrant] 已清空并重建知识库 '{self.collection_name}'，最新写入 {len(points)} 条混合向量切片"
            )
            return len(points)

    def _ensure_ready(self) -> None:
        if not self._ready:
            self.init_collection_with_faq()

    @staticmethod
    def _dense_cosine(query_vec: List[float], hit: Any) -> float:
        vectors = hit.vector
        if isinstance(vectors, dict):
            doc_vec = vectors.get("dense")
            if isinstance(doc_vec, list) and len(doc_vec) == len(query_vec):
                return round(sum(q * d for q, d in zip(query_vec, doc_vec)), 4)
        return round(float(hit.score), 4)

    def similarity_search(
        self,
        query: str,
        k: int = settings.TOP_K_RETRIEVAL,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """基于 Dense + Sparse(IDF) 的 Hybrid RRF 混合检索"""
        self._ensure_ready()
        dense_vec = bge_m3_engine.embed_query(query)
        sp_idx, sp_val = build_sparse_vector(query)

        recall_limit = max(k * 3, settings.HYBRID_PREFETCH_LIMIT)
        prefetch = [Prefetch(query=dense_vec, using="dense", limit=recall_limit)]
        if sp_idx:
            prefetch.append(
                Prefetch(
                    query=SparseVector(indices=sp_idx, values=sp_val),
                    using="sparse",
                    limit=recall_limit,
                )
            )

        res = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF),
            limit=k,
            with_payload=True,
            with_vectors=["dense"],
        )
        hits = res.points
        if not hits:
            return []

        results = [
            {
                "id": hit.id,
                "score": self._dense_cosine(dense_vec, hit),
                "doc": hit.payload or {},
            }
            for hit in hits
        ]

        if score_threshold > 0:
            results = [item for item in results if item["score"] >= score_threshold]
        return results

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """获取当前知识库中的全部切片 Payload"""
        self._ensure_ready()
        return [p.payload for p in self._scroll_points(with_payload=True) if p.payload]


# 全局单例 Qdrant 知识库实例（懒初始化集合数据，由 app lifespan 或首次检索触发加载）
qdrant_store = QdrantKnowledgeStore()
