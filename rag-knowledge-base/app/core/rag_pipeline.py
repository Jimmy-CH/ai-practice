# app/core/rag_pipeline.py
import os
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


class RAGEngine:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(model=settings.EMBEDDING_MODEL, openai_api_key=settings.OPENAI_API_KEY)
        self.llm = ChatOpenAI(model=settings.LLM_MODEL, openai_api_key=settings.DEEPSEEK_API_KEY, openai_api_base=settings.DEEPSEEK_BASE_URL)
        self.vectorstore = Chroma(persist_directory=settings.VECTOR_DB_PATH, embedding_function=self.embeddings)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE,
                                                       chunk_overlap=settings.CHUNK_OVERLAP)

    def ingest_document(self, file_path: str) -> int:
        """文档解析、分块与向量化入库"""
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path)

        documents = loader.load()
        chunks = self.splitter.split_documents(documents)
        self.vectorstore.add_documents(chunks)
        self.vectorstore.persist()
        return len(chunks)

    def ask(self, question: str, top_k: int = None) -> Dict[str, Any]:
        """执行混合检索与 LLM 生成，并返回引用来源"""
        k = top_k or settings.TOP_K
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": k})

        # 构造 Prompt 并要求输出引用来源
        prompt = ChatPromptTemplate.from_template("""
            你是一个企业级知识库助手。请根据以下上下文回答用户的问题。
            如果上下文中没有相关信息，请明确说明“知识库中未找到相关答案”。
            回答时，请在引用的句子末尾标注来源文件名和页码，格式如 [文件名-p页码]。

            上下文: {context}
            用户问题: {question}
        """)

        # 格式化引用来源
        def format_docs(docs):
            return "\n\n".join(
                f"[{doc.metadata.get('source', 'Unknown')}-p{doc.metadata.get('page', 0)}]\n{doc.page_content}" for doc
                in docs)

        rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}

                | prompt
                | self.llm
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
                "snippet": doc.page_content[:100] + "..."
            }
            for i, doc in enumerate(docs)
        ]

        return {"answer": answer, "sources": sources}


# 全局单例引擎
rag_engine = RAGEngine()

