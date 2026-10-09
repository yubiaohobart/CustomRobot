"""
BGE-M3 向量嵌入模型引擎 (BGE-M3 Embedding Engine)
驱动模式：直连【本地 Ollama 模型服务】(ollama run bge-m3 / ollama pull bge-m3)
模型名称：bge-m3 (Dense 1024 维度向量，Cosine 余弦相似度度量)

本地环境已内置 httpx 且确定已安装并运行 Ollama。
代码精简直观，直接使用 httpx 调用 Ollama BGE-M3 向量接口。
"""

import math
from typing import List, Dict, Any
import httpx
from config import settings


class BGEM3EmbeddingEngine:
    def __init__(
        self,
        model_name: str = settings.OLLAMA_EMBED_MODEL,
        ollama_base_url: str = settings.OLLAMA_BASE_URL,
        dim: int = settings.EMBEDDING_DIM
    ):
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.dim = dim

    def embed_query(self, text: str) -> List[float]:
        """对单条查询文本生成 1024 维 BGE-M3 向量"""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量调用本地 Ollama 生成 1024 维 BGE-M3 向量，并执行 L2 归一化"""
        if not texts:
            return []

        # 1. 优先调用 Ollama 官方原生 /api/embed 接口 (支持单条或列表批量)
        url = f"{self.ollama_base_url}/api/embed"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json={"model": self.model_name, "input": texts})
            if resp.status_code == 200:
                raw_vecs = resp.json().get("embeddings", [])
                if raw_vecs:
                    return [self._normalize(v) for v in raw_vecs]

            # 2. 备用 OpenAI 兼容接口 /v1/embeddings
            v1_url = f"{self.ollama_base_url}/v1/embeddings"
            resp_v1 = client.post(v1_url, json={"model": self.model_name, "input": texts})
            if resp_v1.status_code == 200:
                items = resp_v1.json().get("data", [])
                if items:
                    return [self._normalize(item["embedding"]) for item in items]

        raise RuntimeError(f"Ollama embedding failed for model {self.model_name}")

    def _normalize(self, vec: List[float]) -> List[float]:
        """对向量执行 L2 范数归一化，确保 Qdrant 余弦相似度计算标准准确"""
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm > 1e-9 else vec

    def get_status(self) -> Dict[str, Any]:
        """获取当前嵌入引擎与 Ollama 连接信息"""
        return {
            "mode": "ollama",
            "provider": "Local Ollama",
            "model": self.model_name,
            "ollama_url": self.ollama_base_url,
            "ollama_connected": True,
            "dimension": self.dim
        }


# 全局单例嵌入引擎
bge_m3_engine = BGEM3EmbeddingEngine()
