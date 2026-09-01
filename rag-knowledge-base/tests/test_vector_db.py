# tests/test_vector_db.py
"""VectorDBService 回归测试：Chroma 1.x 自动持久化，不再依赖已移除的 persist()"""
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from app.services.vector_db import VectorDBService


@pytest.fixture
def embedding():
    """确定性假 Embedding：相同文本 → 相同向量，无需真实 OpenAI key"""
    return DeterministicFakeEmbedding(size=8)


@pytest.fixture
def chroma_path(tmp_path, monkeypatch):
    """将向量库持久化目录指向临时目录，避免污染项目 chroma_db"""
    path = str(tmp_path / "chroma")
    monkeypatch.setattr("app.config.settings.VECTOR_DB_PATH", path)
    return path


def test_store_has_no_persist_method():
    """回归：langchain-chroma 1.x 已移除 persist()，服务层也不应再暴露该方法"""
    from langchain_chroma import Chroma

    assert not hasattr(Chroma, "persist")
    assert not hasattr(VectorDBService, "persist")


def test_add_and_search(embedding, chroma_path):
    """真实 Chroma 实例：写入后可检索到对应文档"""
    db = VectorDBService(embedding_function=embedding)
    db.add_documents(
        [
            Document(
                page_content="RAG 测试文档 ABC",
                metadata={"source": "a.txt", "page": 1},
            )
        ]
    )

    docs = db.similarity_search("RAG 测试文档 ABC", k=1)
    assert len(docs) == 1
    assert docs[0].metadata["source"] == "a.txt"


def test_automatic_persistence(embedding, chroma_path):
    """回归：写入后无需调用 persist()，重新打开实例（模拟重启）仍可检索到数据"""
    db1 = VectorDBService(embedding_function=embedding)
    db1.add_documents(
        [
            Document(
                page_content="RAG 测试文档 ABC",
                metadata={"source": "a.txt", "page": 1},
            )
        ]
    )

    # 模拟服务重启：使用同一持久化目录重新实例化
    db2 = VectorDBService(embedding_function=embedding)
    docs = db2.similarity_search("RAG 测试文档 ABC", k=1)
    assert len(docs) == 1
    assert docs[0].page_content == "RAG 测试文档 ABC"
