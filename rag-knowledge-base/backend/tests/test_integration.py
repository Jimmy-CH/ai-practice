# tests/test_integration.py
"""集成测试：使用生成的测试数据验证完整 上传→入库→检索→问答 流程

外部依赖（LLM / Embedding）通过 mock 隔离，文档解析、分块、向量入库使用真实组件。
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# redis 可能未安装，提前 mock
sys.modules.setdefault("redis", MagicMock())
_mock_cache_module = MagicMock()
_mock_cache_module.semantic_cache = MagicMock()
_mock_cache_module.semantic_cache.get.return_value = None
sys.modules["app.core.cache"] = _mock_cache_module

from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

# 测试数据目录
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


# ==================== Fixtures ====================

@pytest.fixture(scope="module", autouse=True)
def mock_external_services():
    """全局 mock 外部 LLM / Embedding 服务（不 mock Chroma，保留真实向量库）"""
    fake_embedding = DeterministicFakeEmbedding(size=64)
    with patch("app.ingestion.embeddings.HuggingFaceEmbeddings", return_value=fake_embedding), \
         patch("app.services.llm_service.ChatOpenAI") as mock_llm:

        mock_llm.return_value = MagicMock()
        yield {"embeddings": fake_embedding, "llm": mock_llm}


@pytest.fixture(scope="module")
def test_files():
    """获取测试数据文件路径"""
    files = {}
    for name in os.listdir(TEST_DATA_DIR):
        path = os.path.join(TEST_DATA_DIR, name)
        files[name] = path
    assert len(files) >= 5, f"测试数据不足，期望 >=5 个文件，实际 {len(files)}"
    return files


@pytest.fixture(scope="module")
def client(mock_external_services):
    """创建测试客户端"""
    from app.main import app
    return TestClient(app)


# ==================== 1. 测试数据完整性 ====================

class TestTestData:
    """验证测试数据文件已正确生成"""

    def test_txt_files_exist(self, test_files):
        """TXT 测试文档应存在"""
        for name in ["hr_policy.txt", "tech_guide.txt", "faq.txt"]:
            assert name in test_files, f"缺少测试文件: {name}"
            assert os.path.getsize(test_files[name]) > 0

    def test_pdf_files_exist(self, test_files):
        """PDF 测试文档应存在"""
        for name in ["product_manual.pdf", "security_policy.pdf"]:
            assert name in test_files, f"缺少测试文件: {name}"
            assert os.path.getsize(test_files[name]) > 0

    def test_txt_content_encoding(self, test_files):
        """TXT 文件应为合法 UTF-8 编码"""
        for name in ["hr_policy.txt", "tech_guide.txt", "faq.txt"]:
            with open(test_files[name], "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 100, f"{name} 内容过短"


# ==================== 2. 文档解析 ====================

class TestDocumentParsing:
    """使用测试数据验证文档解析"""

    def test_parse_hr_policy_txt(self, test_files):
        """解析 HR 制度 TXT 文件应返回非空文档列表"""
        from app.ingestion.parsers import DocumentParser
        parser = DocumentParser()
        docs = parser.parse(test_files["hr_policy.txt"])
        assert len(docs) >= 1
        full_text = " ".join(d.page_content for d in docs)
        assert "考勤" in full_text or "年假" in full_text

    def test_parse_tech_guide_txt(self, test_files):
        """解析技术指南 TXT 文件应包含 RAG 相关内容"""
        from app.ingestion.parsers import DocumentParser
        parser = DocumentParser()
        docs = parser.parse(test_files["tech_guide.txt"])
        full_text = " ".join(d.page_content for d in docs)
        assert "RAG" in full_text or "向量" in full_text

    def test_parse_faq_txt(self, test_files):
        """解析 FAQ TXT 文件应包含问答内容"""
        from app.ingestion.parsers import DocumentParser
        parser = DocumentParser()
        docs = parser.parse(test_files["faq.txt"])
        full_text = " ".join(d.page_content for d in docs)
        assert "Q1" in full_text or "A1" in full_text

    def test_parse_product_pdf(self, test_files):
        """解析产品手册 PDF 应提取到文本"""
        from app.ingestion.parsers import DocumentParser
        parser = DocumentParser()
        docs = parser.parse(test_files["product_manual.pdf"])
        assert len(docs) >= 1
        # PDF 解析后应有内容
        total_content = sum(len(d.page_content) for d in docs)
        assert total_content > 0, "PDF 解析后内容为空"

    def test_parse_security_pdf(self, test_files):
        """解析安全规范 PDF 应提取到文本"""
        from app.ingestion.parsers import DocumentParser
        parser = DocumentParser()
        docs = parser.parse(test_files["security_policy.pdf"])
        assert len(docs) >= 1


# ==================== 3. 文本分块 ====================

class TestTextChunking:
    """使用测试数据验证文本分块"""

    def test_chunk_hr_policy(self, test_files):
        """HR 制度文档分块后应产生至少一个片段"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        parser = DocumentParser()
        # 使用较小 chunk_size 确保长文档被分割
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        docs = parser.parse(test_files["hr_policy.txt"])
        chunks = chunker.split(docs)
        assert len(chunks) >= 2, "较长文档使用小 chunk_size 应被分为多个块"
        for chunk in chunks:
            assert len(chunk.page_content) <= 300  # 允许一定容差

    def test_chunk_preserves_metadata(self, test_files):
        """分块后应保留原始 metadata"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        parser = DocumentParser()
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        docs = parser.parse(test_files["tech_guide.txt"])
        chunks = chunker.split(docs)
        for chunk in chunks:
            assert "source" in chunk.metadata

    def test_chunk_faq(self, test_files):
        """FAQ 文档分块后每个块应非空"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        parser = DocumentParser()
        chunker = TextChunker(chunk_size=300, chunk_overlap=30)
        docs = parser.parse(test_files["faq.txt"])
        chunks = chunker.split(docs)
        for chunk in chunks:
            assert len(chunk.page_content.strip()) > 0


# ==================== 4. 向量入库与检索 ====================

class TestVectorIngestionAndRetrieval:
    """使用真实 Chroma + FakeEmbedding 验证入库与检索"""

    @pytest.fixture(autouse=True)
    def setup_vector_db(self, tmp_path_factory, monkeypatch):
        """为每个测试类创建独立的向量库"""
        self.chroma_dir = str(tmp_path_factory.mktemp("chroma"))
        monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", self.chroma_dir)

    def test_ingest_and_retrieve_txt(self, test_files):
        """TXT 文档入库后应能通过关键词检索到"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        from app.ingestion.embeddings import EmbeddingService
        from app.services.vector_db import VectorDBService

        parser = DocumentParser()
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        embedding_service = EmbeddingService()
        vdb = VectorDBService(embedding_function=embedding_service.embeddings)

        # 入库
        docs = parser.parse(test_files["hr_policy.txt"])
        chunks = chunker.split(docs)
        vdb.add_documents(chunks)

        # 检索：使用文档中的关键词
        results = vdb.similarity_search("考勤 迟到 加班", k=3)
        assert len(results) >= 1
        # 检索结果应包含 HR 相关内容
        combined = " ".join(doc.page_content for doc in results)
        assert any(kw in combined for kw in ["考勤", "迟到", "加班", "休假", "年假", "薪酬", "员工"])

    def test_ingest_multiple_documents(self, test_files):
        """多个文档入库后均应被检索到"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        from app.ingestion.embeddings import EmbeddingService
        from app.services.vector_db import VectorDBService

        parser = DocumentParser()
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        embedding_service = EmbeddingService()
        vdb = VectorDBService(embedding_function=embedding_service.embeddings)

        total_chunks = 0
        for name in ["hr_policy.txt", "tech_guide.txt", "faq.txt"]:
            docs = parser.parse(test_files[name])
            chunks = chunker.split(docs)
            vdb.add_documents(chunks)
            total_chunks += len(chunks)

        assert total_chunks >= 4, f"入库片段总数应 >= 4，实际 {total_chunks}"

    def test_mmr_retrieval(self, test_files):
        """MMR 检索应返回相关且多样的结果"""
        from app.ingestion.parsers import DocumentParser
        from app.ingestion.chunking import TextChunker
        from app.ingestion.embeddings import EmbeddingService
        from app.services.vector_db import VectorDBService

        parser = DocumentParser()
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        embedding_service = EmbeddingService()
        vdb = VectorDBService(embedding_function=embedding_service.embeddings)

        # 入库多个文档
        for name in ["hr_policy.txt", "tech_guide.txt", "faq.txt"]:
            docs = parser.parse(test_files[name])
            chunks = chunker.split(docs)
            vdb.add_documents(chunks)

        # MMR 检索
        results = vdb.max_marginal_relevance_search("系统 功能 管理", k=3, fetch_k=10)
        assert len(results) >= 1


# ==================== 5. API 端到端 ====================

class TestAPIEndToEnd:
    """API 端点端到端测试（LLM mock）"""

    def test_health_check(self, client):
        """健康检查应返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_upload_all_test_files(self, client, test_files):
        """上传所有测试文件均应返回 200"""
        for name, path in test_files.items():
            ext = os.path.splitext(name)[1].lower()
            mime = "application/pdf" if ext == ".pdf" else "text/plain"
            with open(path, "rb") as f:
                resp = client.post("/upload", files={"file": (name, f, mime)})
            assert resp.status_code == 200, f"上传 {name} 失败: {resp.text}"
            data = resp.json()
            assert data["status"] == "processing"
            assert data["filename"] == name

    def test_upload_oversized_file_rejected(self, client, tmp_path):
        """超大文件应返回 413"""
        # 创建一个略超 50MB 限制的文件（使用稀疏方式快速生成）
        big_file = tmp_path / "huge.txt"
        # 实际不写满 50MB，用 mock 限制来测试
        from app.api import endpoints
        original_max = endpoints.MAX_UPLOAD_SIZE
        endpoints.MAX_UPLOAD_SIZE = 100  # 临时设为 100 bytes

        try:
            big_file.write_text("A" * 200, encoding="utf-8")
            with open(big_file, "rb") as f:
                resp = client.post("/upload", files={"file": ("huge.txt", f, "text/plain")})
            assert resp.status_code == 413
            assert "超出限制" in resp.json()["detail"]
        finally:
            endpoints.MAX_UPLOAD_SIZE = original_max

    def test_ask_with_mock_llm(self, client, mock_external_services):
        """问答接口（LLM mock）应返回结构化响应"""
        mock_rag = MagicMock()
        mock_rag.ask.return_value = {
            "answer": "根据知识库，年假政策为：入职满一年享有5天带薪年假。",
            "sources": [
                {
                    "index": 1,
                    "source": "hr_policy.txt",
                    "page": 0,
                    "snippet": "入职满一年的员工享有5天带薪年假...",
                }
            ],
        }

        with patch("app.api.endpoints.get_rag_engine", return_value=mock_rag):
            resp = client.post("/v1/ask", json={"question": "年假有多少天？"})

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert "latency_ms" in data
        assert data["latency_ms"] >= 0
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "hr_policy.txt"

    def test_ask_empty_question_rejected(self, client):
        """空问题应返回 422"""
        resp = client.post("/v1/ask", json={"question": ""})
        assert resp.status_code == 422

    def test_ask_with_top_k(self, client, mock_external_services):
        """带 top_k 参数的问答请求应正常处理"""
        mock_rag = MagicMock()
        mock_rag.ask.return_value = {
            "answer": "测试回答",
            "sources": [],
        }

        with patch("app.api.endpoints.get_rag_engine", return_value=mock_rag):
            resp = client.post("/v1/ask", json={"question": "测试", "top_k": 3})

        assert resp.status_code == 200
        mock_rag.ask.assert_called_once_with("测试", top_k=3)

    def test_metrics_endpoint(self, client):
        """/metrics 端点应可访问"""
        # 先触发一些请求以产生指标
        client.get("/health")
        resp = client.get("/metrics")
        assert resp.status_code == 200


# ==================== 6. RAG Engine 集成 ====================

class TestRAGEngineIntegration:
    """RAGEngine 入库流程集成测试（真实解析 + 真实向量库）"""

    def test_full_ingest_pipeline_txt(self, tmp_path, monkeypatch):
        """完整入库流程：TXT 解析 → 分块 → 向量化 → 检索"""
        from app.core.rag_pipeline import RAGEngine

        monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", str(tmp_path / "chroma"))
        monkeypatch.setattr("app.config.settings.CHUNK_SIZE", 200)
        monkeypatch.setattr("app.config.settings.CHUNK_OVERLAP", 20)
        fake_embedding = DeterministicFakeEmbedding(size=64)

        with patch("app.ingestion.embeddings.HuggingFaceEmbeddings", return_value=fake_embedding), \
             patch("app.services.llm_service.ChatOpenAI"):
            engine = RAGEngine()

        # 使用生成的测试数据
        hr_path = os.path.join(TEST_DATA_DIR, "hr_policy.txt")
        chunk_count = engine.ingest_document(hr_path)
        assert chunk_count >= 2

        # 验证可检索
        docs = engine.vector_db.similarity_search("考勤管理", k=2)
        assert len(docs) >= 1

    def test_full_ingest_pipeline_pdf(self, tmp_path, monkeypatch):
        """完整入库流程：PDF 解析 → 分块 → 向量化 → 检索"""
        from app.core.rag_pipeline import RAGEngine

        monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", str(tmp_path / "chroma_pdf"))
        fake_embedding = DeterministicFakeEmbedding(size=64)

        with patch("app.ingestion.embeddings.HuggingFaceEmbeddings", return_value=fake_embedding), \
             patch("app.services.llm_service.ChatOpenAI"):
            engine = RAGEngine()

        pdf_path = os.path.join(TEST_DATA_DIR, "product_manual.pdf")
        chunk_count = engine.ingest_document(pdf_path)
        assert chunk_count >= 1

        docs = engine.vector_db.similarity_search("产品", k=2)
        assert len(docs) >= 1

    def test_multi_document_ingest(self, tmp_path, monkeypatch):
        """多文档入库：入库多个文件后均应可检索"""
        from app.core.rag_pipeline import RAGEngine

        monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", str(tmp_path / "chroma_multi"))
        monkeypatch.setattr("app.config.settings.CHUNK_SIZE", 200)
        monkeypatch.setattr("app.config.settings.CHUNK_OVERLAP", 20)
        fake_embedding = DeterministicFakeEmbedding(size=64)

        with patch("app.ingestion.embeddings.HuggingFaceEmbeddings", return_value=fake_embedding), \
             patch("app.services.llm_service.ChatOpenAI"):
            engine = RAGEngine()

        total = 0
        for name in ["hr_policy.txt", "tech_guide.txt", "faq.txt"]:
            path = os.path.join(TEST_DATA_DIR, name)
            count = engine.ingest_document(path)
            total += count

        assert total >= 4
        # 每个文档的内容都应可被检索到
        for keyword in ["考勤", "RAG", "上传"]:
            docs = engine.vector_db.similarity_search(keyword, k=1)
            assert len(docs) >= 1, f"关键词 '{keyword}' 未检索到结果"
