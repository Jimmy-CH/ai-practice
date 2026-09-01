# app/services/vector_db.py
from typing import List
from langchain_core.documents import Document
from langchain_chroma import Chroma
from app.config import settings


class VectorDBService:
    """向量数据库服务封装，基于 ChromaDB 提供持久化向量存储。

    注意：Chroma 1.x 在写入时自动持久化（persist_directory 指定后无需手动
    调用 persist()，该方法已从 langchain-chroma 1.x 中移除）。
    """

    def __init__(self, embedding_function):
        self._store = Chroma(
            persist_directory=settings.VECTOR_DB_PATH,
            embedding_function=embedding_function,
        )

    @property
    def store(self) -> Chroma:
        """获取底层 LangChain Chroma 实例"""
        return self._store

    def add_documents(self, documents: List[Document]) -> List[str]:
        """将文档写入向量库，返回文档 ID 列表（Chroma 1.x 自动持久化）"""
        return self._store.add_documents(documents)

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """相似度检索，返回最相关的 k 个文档"""
        return self._store.similarity_search(query, k=k)

    def max_marginal_relevance_search(
        self, query: str, k: int = 5, fetch_k: int = 20, lambda_mult: float = 0.5
    ) -> List[Document]:
        """MMR 检索，在相关性和多样性之间取得平衡"""
        return self._store.max_marginal_relevance_search(
            query, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult
        )

    def as_retriever(self, search_type: str = "similarity", search_kwargs: dict = None):
        """转换为 LangChain Retriever 接口"""
        kwargs = search_kwargs or {}
        return self._store.as_retriever(search_type=search_type, search_kwargs=kwargs)
