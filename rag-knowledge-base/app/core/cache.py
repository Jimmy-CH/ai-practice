# app/core/cache.py
import json
import logging
from typing import Optional, Dict, Any
from redis import Redis
from langchain_community.vectorstores import Redis as RedisVectorStore
from app.config import settings
from app.ingestion.embeddings import EmbeddingService

logger = logging.getLogger("RAG_API")


class SemanticCache:
    def __init__(self):
        self.redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        # 复用 EmbeddingService，避免重复创建 OpenAIEmbeddings 实例
        self._embedding_service = EmbeddingService()
        # 使用 LangChain 的 Redis 向量存储进行语义检索
        self.vector_store = RedisVectorStore.from_existing_index(
            index_name="rag_cache_index",
            embedding=self._embedding_service.embeddings,
            redis_url=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        )
        self.similarity_threshold = 0.95

    def get(self, question: str) -> Optional[Dict[str, Any]]:
        """语义检索缓存"""
        try:
            results = self.vector_store.similarity_search_with_score(question, k=1)
            if results and results[0][1] <= self.similarity_threshold:
                doc = results[0][0]
                logger.info(f"[CACHE HIT] 命中语义缓存，相似度: {results[0][1]:.4f}")
                return json.loads(doc.page_content)
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        return None

    def set(self, question: str, result: Dict[str, Any]):
        """将问答结果写入缓存"""
        try:
            self.vector_store.add_texts(
                texts=[json.dumps(result, ensure_ascii=False)],
                metadatas=[{"question": question}]
            )
            logger.info(f"[CACHE SET] 问答结果已写入缓存")
        except Exception as e:
            logger.error(f"Cache set failed: {e}")


semantic_cache = SemanticCache()

