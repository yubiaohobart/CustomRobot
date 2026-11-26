"""
BGE-M3 向量嵌入模型引擎 (BGE-M3 Embedding Engine)
驱动模式：直连【本地 Ollama 模型服务】(ollama run bge-m3 / ollama pull bge-m3)
模型名称：bge-m3 (Dense 1024 维度向量，Cosine 余弦相似度度量)

本地环境已内置 httpx 且确定已安装并运行 Ollama。
代码精简直观，直接使用 httpx 调用 Ollama BGE-M3 向量接口。
"""

from collections import Counter
import math
import re
import threading
from typing import List, Dict, Any, Optional, Tuple
import zlib
import httpx
from config import settings

_UNIT_NUM_RE = re.compile(r"\d+(?:\.\d+)?[a-z\u4e00-\u9fff]{1,4}")
_ALNUM_RE = re.compile(r"[a-z0-9]+")
_CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")


def build_sparse_vector(text: str) -> Tuple[List[int], List[float]]:
    """
    构造适配 Qdrant Sparse(IDF) 的词法稀疏向量：
    提取数字+单位（如 15天、48小时）、英文词元及中文单字/双字切片，计算 sublinear TF 权重。
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return [], []

    tokens: List[str] = []
    tokens.extend(_UNIT_NUM_RE.findall(lowered))
    tokens.extend(_ALNUM_RE.findall(lowered))
    for span in _CJK_SPAN_RE.findall(lowered):
        tokens.extend(span)
        tokens.extend(span[i : i + 2] for i in range(len(span) - 1))

    if not tokens:
        return [], []

    buckets: Dict[int, float] = {}
    for tok, count in Counter(tokens).items():
        idx = zlib.crc32(tok.encode("utf-8")) & 0xFFFFFFFF
        buckets[idx] = buckets.get(idx, 0.0) + (1.0 + math.log(count))

    sorted_items = sorted(buckets.items())
    return [idx for idx, _ in sorted_items], [round(val, 4) for _, val in sorted_items]


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
        url = f"{self.ollama_base_url}/api/embed"
        resp = client.post(url, json={"model": self.model_name, "input": texts})
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama embedding failed ({resp.status_code}): {resp.text[:160]}")

        raw_vecs = resp.json().get("embeddings", [])
        if len(raw_vecs) != len(texts):
            raise RuntimeError(f"Ollama /api/embed 向量条数不匹配: expected={len(texts)}, actual={len(raw_vecs)}")
        return [self._validate_and_normalize(v) for v in raw_vecs]

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
