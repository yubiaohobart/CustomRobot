from typing import Any

__all__ = [
    "bge_m3_engine",
    "BGEM3EmbeddingEngine",
    "qdrant_store",
    "QdrantKnowledgeStore",
    "deepseek_client",
    "DeepSeekLLMClient",
    "OpenAICompatibleLLMClient",
    "ModelCapabilities",
    "PromptContext",
    "LLMResult",
]


def __getattr__(name: str) -> Any:
    if name in ("bge_m3_engine", "BGEM3EmbeddingEngine"):
        from . import embedding
        return getattr(embedding, name)
    if name in ("qdrant_store", "QdrantKnowledgeStore"):
        from . import qdrant_store
        return getattr(qdrant_store, name)
    if name in (
        "deepseek_client",
        "DeepSeekLLMClient",
        "OpenAICompatibleLLMClient",
        "ModelCapabilities",
        "PromptContext",
        "LLMResult",
    ):
        from . import llm
        return getattr(llm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
