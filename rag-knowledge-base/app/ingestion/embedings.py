# app/ingestion/embedings.py
from langchain_openai import OpenAIEmbeddings
from app.config import settings


class EmbeddingService:
    """Embedding 服务封装，提供 OpenAI Embedding 模型的统一访问接口"""

    def __init__(self):
        self._embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """获取底层 LangChain Embeddings 实例"""
        return self._embeddings

    def embed_query(self, text: str) -> list:
        """将单条文本转换为向量"""
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list) -> list:
        """将多条文本批量转换为向量"""
        return self._embeddings.embed_documents(texts)
