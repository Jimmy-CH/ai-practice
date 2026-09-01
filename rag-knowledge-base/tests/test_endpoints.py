# tests/test_endpoints.py
"""API 端点测试"""
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# redis 可能未安装，提前 mock
sys.modules.setdefault("redis", MagicMock())

# mock app.core.cache，避免模块级 SemanticCache() 实例化时连接 Redis
_mock_cache_module = MagicMock()
_mock_cache_module.semantic_cache = MagicMock()
_mock_cache_module.semantic_cache.get.return_value = None  # 缓存未命中
sys.modules["app.core.cache"] = _mock_cache_module


@pytest.fixture(scope="module")
def mock_services():
    """全局 mock 外部依赖"""
    with patch("app.ingestion.embedings.OpenAIEmbeddings") as mock_emb, \
         patch("app.services.llm_service.ChatOpenAI") as mock_llm, \
         patch("app.services.vector_db.Chroma") as mock_chroma:

        mock_emb.return_value = MagicMock()
        mock_llm.return_value = MagicMock()
        mock_chroma.return_value = MagicMock()

        yield {
            "embeddings": mock_emb,
            "llm": mock_llm,
            "chroma": mock_chroma,
        }


@pytest.fixture(scope="module")
def client(mock_services):
    """创建测试客户端"""
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        """健康检查应返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestUploadEndpoint:
    def test_upload_txt(self, client, tmp_path):
        """上传 TXT 文件应返回 200"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("测试内容", encoding="utf-8")

        with open(txt_file, "rb") as f:
            resp = client.post("/upload", files={"file": ("test.txt", f, "text/plain")})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert data["filename"] == "test.txt"

    def test_upload_unsupported_format(self, client, tmp_path):
        """上传不支持的格式应返回 400"""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b,c", encoding="utf-8")

        with open(csv_file, "rb") as f:
            resp = client.post("/upload", files={"file": ("data.csv", f, "text/csv")})

        assert resp.status_code == 400


class TestAskEndpoint:
    def test_ask_missing_question(self, client):
        """空问题应返回 422（Pydantic 校验失败）"""
        resp = client.post("/v1/ask", json={"question": ""})
        assert resp.status_code == 422

    def test_ask_missing_field(self, client):
        """缺少 question 字段应返回 422"""
        resp = client.post("/v1/ask", json={})
        assert resp.status_code == 422

    def test_ask_success(self, client, mock_services):
        """正常问答应返回 200"""
        mock_rag = MagicMock()
        mock_rag.ask.return_value = {
            "answer": "这是一个测试回答。",
            "sources": [
                {
                    "index": 1,
                    "source": "test.pdf",
                    "page": 1,
                    "snippet": "测试摘要...",
                }
            ],
        }

        with patch("app.api.endpoints.rag_engine", mock_rag):
            resp = client.post("/v1/ask", json={"question": "测试问题"})

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert "latency_ms" in data
