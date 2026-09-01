# tests/test_rag_pipeline.py
"""RAGEngine 入库流程回归测试：不再调用已移除的 persist()"""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

# 注意：RAGEngine 在模块级 import 会触发全局单例 rag_engine 的真实构造
# （OpenAIEmbeddings / Chroma 等），从而破坏 test_endpoints.py 的 mock 隔离，
# 因此这里延迟到测试函数内 import。


def test_ingest_document_does_not_call_persist(tmp_path, monkeypatch):
    """回归：ingest_document 完整流程（解析→分块→入库）不再调用 persist()"""
    from app.core.rag_pipeline import RAGEngine

    monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", str(tmp_path / "chroma"))
    fake_embedding = DeterministicFakeEmbedding(size=8)

    with patch("app.ingestion.embedings.OpenAIEmbeddings", return_value=fake_embedding), \
         patch("app.services.llm_service.ChatOpenAI"):
        engine = RAGEngine()

    doc_file = tmp_path / "guide.txt"
    doc_file.write_text("RAG 测试文档：公司年假政策。", encoding="utf-8")

    chunk_count = engine.ingest_document(str(doc_file))
    assert chunk_count >= 1

    # 入库后应能通过向量库检索到（无需手动 persist）
    docs = engine.vector_db.similarity_search("RAG 测试文档", k=1)
    assert len(docs) >= 1


def test_ingest_document_flow_uses_expected_components(tmp_path):
    """验证 ingest_document 只依赖 parse → split → add_documents 链路"""
    from app.core.rag_pipeline import RAGEngine

    parser = MagicMock()
    chunker = MagicMock()
    vdb = MagicMock()
    parser.parse.return_value = [Document(page_content="原始文档")]
    chunker.split.return_value = [Document(page_content="块1"), Document(page_content="块2")]

    with patch("app.core.rag_pipeline.DocumentParser", return_value=parser), \
         patch("app.core.rag_pipeline.TextChunker", return_value=chunker), \
         patch("app.core.rag_pipeline.EmbeddingService"), \
         patch("app.core.rag_pipeline.LLMService"), \
         patch("app.core.rag_pipeline.VectorDBService", return_value=vdb):
        engine = RAGEngine()

    file_path = str(tmp_path / "doc.pdf")
    result = engine.ingest_document(file_path)

    assert result == 2
    parser.parse.assert_called_once_with(file_path)
    chunker.split.assert_called_once()
    vdb.add_documents.assert_called_once_with(chunker.split.return_value)
    # persist 已从服务层移除，不应被调用（调用将抛 AttributeError）
    vdb.persist.assert_not_called()
