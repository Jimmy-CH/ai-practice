# app/core/rag_pipeline.py
import os
import logging
from typing import Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.ingestion.parsers import DocumentParser
from app.ingestion.chunking import TextChunker
from app.ingestion.embedings import EmbeddingService
from app.services.llm_service import LLMService
from app.services.vector_db import VectorDBService

logger = logging.getLogger("RAG_API")


class RAGEngine:
    """RAG 引擎：编排文档入库与问答生成全流程"""

    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        self.vector_db = VectorDBService(embedding_function=self.embedding_service.embeddings)

    def ingest_document(self, file_path: str) -> int:
        """文档解析、分块与向量化入库（Chroma 1.x 写入即自动持久化）"""
        documents = self.parser.parse(file_path)
        chunks = self.chunker.split(documents)
        self.vector_db.add_documents(chunks)
        logger.info(f"文档入库完成: {os.path.basename(file_path)}，共 {len(chunks)} 个片段")
        return len(chunks)

    def ask(self, question: str, top_k: int = None) -> Dict[str, Any]:
        """执行检索与 LLM 生成，返回回答及引用来源"""
        k = top_k or settings.TOP_K
        retriever = self.vector_db.as_retriever(search_kwargs={"k": k})

        prompt = ChatPromptTemplate.from_template("""
            你是一个企业级知识库助手。请根据以下上下文回答用户的问题。
            如果上下文中没有相关信息，请明确说明"知识库中未找到相关答案"。
            回答时，请在引用的句子末尾标注来源文件名和页码，格式如 [文件名-p页码]。

            上下文: {context}
            用户问题: {question}
        """)

        def format_docs(docs):
            return "\n\n".join(
                f"[{doc.metadata.get('source', 'Unknown')}-p{doc.metadata.get('page', 0)}]\n"
                f"{doc.page_content}"
                for doc in docs
            )

        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm_service.llm
            | StrOutputParser()
        )

        # 获取原始检索文档用于结构化返回
        docs = retriever.invoke(question)
        answer = rag_chain.invoke(question)

        sources = [
            {
                "index": i + 1,
                "source": os.path.basename(doc.metadata.get("source", "Unknown")),
                "page": doc.metadata.get("page", 0),
                "snippet": doc.page_content[:100] + "...",
            }
            for i, doc in enumerate(docs)
        ]

        return {"answer": answer, "sources": sources}


# 全局单例引擎
rag_engine = RAGEngine()
