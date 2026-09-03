# app/ingestion/embeddings.py
# 注意：必须先 import app.config 以触发 HF_ENDPOINT 等环境变量的设置，
# 然后再 import langchain_huggingface（它会加载 huggingface_hub）。
from app.config import settings
from langchain_huggingface import HuggingFaceEmbeddings


class EmbeddingService:
    """Embedding 服务封装，使用本地 HuggingFace 模型（无需 API Key）"""

    def __init__(self):
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """获取底层 LangChain Embeddings 实例"""
        return self._embeddings

    def embed_query(self, text: str) -> list:
        """将单条文本转换为向量"""
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list) -> list:
        """将多条文本批量转换为向量"""
        return self._embeddings.embed_documents(texts)
