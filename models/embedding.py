"""
Embedding 后端
==============
优先使用智谱 embedding-2，保持与 SmartKB 的 Milvus Collection 维度一致。
"""

from typing import List

from config import DASHSCOPE_API_KEY, ZHIPUAI_API_KEY


class EmbeddingModel:
    """自动选择可用 Embedding 后端。"""

    def __init__(self):
        self._model = None
        self.backend = "unknown"
        self.model_name = "unknown"
        self.dimension = 0
        self._init_model()

    def _init_model(self):
        if self._try_zhipu():
            return
        if self._try_dashscope():
            return
        raise RuntimeError("未找到可用 Embedding 后端，请检查 ZHIPUAI_API_KEY 或 DASHSCOPE_API_KEY")

    def _try_zhipu(self) -> bool:
        if not ZHIPUAI_API_KEY:
            return False
        try:
            from langchain_openai import OpenAIEmbeddings

            model = OpenAIEmbeddings(
                model="embedding-2",
                api_key=ZHIPUAI_API_KEY,
                base_url="https://open.bigmodel.cn/api/paas/v4/",
                dimensions=1024,
                timeout=15,
            )
            test_vec = model.embed_query("AgentFlow 连接测试")
            self._model = model
            self.backend = "zhipu"
            self.model_name = "embedding-2"
            self.dimension = len(test_vec)
            return True
        except Exception as exc:
            print(f"[Embedding] 智谱不可用: {str(exc)[:120]}")
            return False

    def _try_dashscope(self) -> bool:
        if not DASHSCOPE_API_KEY:
            return False
        try:
            from langchain_community.embeddings import DashScopeEmbeddings

            model = DashScopeEmbeddings(
                model="text-embedding-v2",
                dashscope_api_key=DASHSCOPE_API_KEY,
            )
            test_vec = model.embed_query("AgentFlow 连接测试")
            self._model = model
            self.backend = "dashscope"
            self.model_name = "text-embedding-v2"
            self.dimension = len(test_vec)
            return True
        except Exception as exc:
            print(f"[Embedding] DashScope 不可用: {str(exc)[:120]}")
            return False

    def embed_query(self, text: str) -> List[float]:
        return self._model.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.embed_documents(texts)

    def test_connection(self) -> tuple[bool, str]:
        try:
            vec = self.embed_query("hello")
            return True, f"{self.backend}/{self.model_name}/{len(vec)}d"
        except Exception as exc:
            return False, str(exc)[:200]


_embedding_instance: EmbeddingModel | None = None


def get_embedding_model() -> EmbeddingModel:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingModel()
    return _embedding_instance

