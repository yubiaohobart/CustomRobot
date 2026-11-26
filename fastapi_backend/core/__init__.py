from typing import Any

__all__ = [
    "bge_m3_engine",
    "BGEM3EmbeddingEngine",
    "build_sparse_vector",
    "qdrant_store",
    "QdrantKnowledgeStore",
    "deepseek_client",
    "DeepSeekLLMClient",
    "LLMResult",
    "acquire_session_lock",
    "close_session_lock_redis",
]


def __getattr__(name: str) -> Any:
    if name in ("bge_m3_engine", "BGEM3EmbeddingEngine", "build_sparse_vector"):
        from . import embedding
        return getattr(embedding, name)
    if name in ("qdrant_store", "QdrantKnowledgeStore"):
        from . import qdrant_store
        return getattr(qdrant_store, name)
    if name in ("deepseek_client", "DeepSeekLLMClient", "LLMResult"):
        from . import llm
        return getattr(llm, name)
    if name in ("acquire_session_lock", "close_session_lock_redis"):
        from . import session_lock
        return getattr(session_lock, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
