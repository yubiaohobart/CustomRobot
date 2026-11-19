"""
BGE-M3 向量嵌入模型引擎 (BGE-M3 Embedding Engine)
驱动模式：直连【本地 Ollama 模型服务】(ollama run bge-m3 / ollama pull bge-m3)
模型名称：bge-m3 (Dense 1024 维度向量，Cosine 余弦相似度度量)

本地环境已内置 httpx 且确定已安装并运行 Ollama。
代码精简直观，直接使用 httpx 调用 Ollama BGE-M3 向量接口。
"""

import math
import threading
from typing import List, Dict, Any, Optional
import httpx
from config import settings


class BGEM3EmbeddingEngine:
    def __init__(
        self,
        model_name: str = settings.OLLAMA_EMBED_MODEL,
        ollama_base_url: str = settings.OLLAMA_BASE_URL,
        dim: int = settings.EMBEDDING_DIM,
        timeout: float = 30.0,
    ):
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.dim = dim
        self.timeout = timeout
        self._lock = threading.RLock()
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.Client(timeout=self.timeout)
            return self._client

    def close(self) -> None:
        """关闭复用的 HTTP 客户端连接池"""
        with self._lock:
            if self._client is not None and not self._client.is_closed:
                self._client.close()
                self._client = None

    def embed_query(self, text: str) -> List[float]:
        """对单条查询文本生成 1024 维 BGE-M3 向量"""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量调用本地 Ollama 生成 1024 维 BGE-M3 向量，并执行 L2 归一化"""
        if not texts:
            return []

        client = self._get_client()
        errors: List[str] = []

        # 1. 优先调用 Ollama 官方原生 /api/embed 接口
        url = f"{self.ollama_base_url}/api/embed"
        resp = client.post(url, json={"model": self.model_name, "input": texts})
        if resp.status_code == 200:
            raw_vecs = resp.json().get("embeddings", [])
            if len(raw_vecs) == len(texts):
                return [self._validate_and_normalize(v) for v in raw_vecs]
            errors.append(f"/api/embed 返回向量条数不匹配: expected={len(texts)}, actual={len(raw_vecs)}")
        else:
            errors.append(f"/api/embed HTTP {resp.status_code}: {resp.text[:120]}")

        # 2. 备用 OpenAI 兼容接口 /v1/embeddings
        v1_url = f"{self.ollama_base_url}/v1/embeddings"
        resp_v1 = client.post(v1_url, json={"model": self.model_name, "input": texts})
        if resp_v1.status_code == 200:
            items = resp_v1.json().get("data", [])
            raw_vecs = [item.get("embedding", []) for item in items]
            if len(raw_vecs) == len(texts):
                return [self._validate_and_normalize(v) for v in raw_vecs]
            errors.append(f"/v1/embeddings 返回向量条数不匹配: expected={len(texts)}, actual={len(raw_vecs)}")
        else:
            errors.append(f"/v1/embeddings HTTP {resp_v1.status_code}: {resp_v1.text[:120]}")

        raise RuntimeError(f"Ollama embedding failed for model {self.model_name}: {'; '.join(errors)}")

    def _validate_and_normalize(self, vec: List[float]) -> List[float]:
        """校验向量维度并执行 L2 范数归一化，确保 Qdrant 余弦相似度计算准确"""
        if len(vec) != self.dim:
            raise RuntimeError(f"向量维度不匹配: expected={self.dim}, actual={len(vec)}")
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm > 1e-9 else vec

    def get_status(self, check_connection: bool = True) -> Dict[str, Any]:
        """探测本地 Ollama 服务连通性与目标模型就绪状态"""
        connected = False
        model_ready = False
        error_msg: Optional[str] = None

        if check_connection:
            try:
                client = self._get_client()
                resp = client.get(f"{self.ollama_base_url}/api/tags", timeout=2.5)
                if resp.status_code == 200:
                    connected = True
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    model_ready = any(
                        name == self.model_name or name.startswith(f"{self.model_name}:")
                        for name in models
                    )
                else:
                    error_msg = f"HTTP {resp.status_code}"
            except Exception as e:
                error_msg = str(e)

        status: Dict[str, Any] = {
            "mode": "ollama",
            "provider": "Local Ollama",
            "model": self.model_name,
            "ollama_url": self.ollama_base_url,
            "ollama_connected": connected,
            "model_ready": model_ready,
            "dimension": self.dim,
        }
        if error_msg:
            status["error"] = error_msg
        return status


# 全局单例嵌入引擎
bge_m3_engine = BGEM3EmbeddingEngine()
