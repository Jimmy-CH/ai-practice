# app/core/retrieval.py
from typing import List
from langchain_core.documents import Document
from app.services.vector_db import VectorDBService


class Retriever:
    """检索器基类"""

    def __init__(self, vector_db: VectorDBService, k: int = 5):
        self.vector_db = vector_db
        self.k = k

    def retrieve(self, query: str) -> List[Document]:
        raise NotImplementedError


class SimilarityRetriever(Retriever):
    """基于相似度（余弦距离）的检索器"""

    def retrieve(self, query: str) -> List[Document]:
        return self.vector_db.similarity_search(query, k=self.k)


class MMRRetriever(Retriever):
    """基于 MMR（最大边际相关性）的检索器，平衡相关性与多样性"""

    def __init__(self, vector_db: VectorDBService, k: int = 5,
                 fetch_k: int = 20, lambda_mult: float = 0.5):
        super().__init__(vector_db, k)
        self.fetch_k = fetch_k
        self.lambda_mult = lambda_mult

    def retrieve(self, query: str) -> List[Document]:
        return self.vector_db.max_marginal_relevance_search(
            query, k=self.k, fetch_k=self.fetch_k, lambda_mult=self.lambda_mult
        )
