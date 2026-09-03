# tests/test_schemas.py
"""Pydantic Schema 测试"""
import pytest
from pydantic import ValidationError
from app.api.schemas import AskRequest, AskResponse, SourceItem, UploadResponse, HealthResponse


class TestAskRequest:
    def test_valid_request(self):
        """合法请求应通过验证"""
        req = AskRequest(question="什么是 RAG？")
        assert req.question == "什么是 RAG？"
        assert req.top_k is None

    def test_valid_request_with_top_k(self):
        """带 top_k 的合法请求"""
        req = AskRequest(question="测试", top_k=3)
        assert req.top_k == 3

    def test_empty_question_rejected(self):
        """空问题应被拒绝"""
        with pytest.raises(ValidationError):
            AskRequest(question="")

    def test_top_k_out_of_range(self):
        """top_k 超出范围应被拒绝"""
        with pytest.raises(ValidationError):
            AskRequest(question="测试", top_k=0)
        with pytest.raises(ValidationError):
            AskRequest(question="测试", top_k=21)


class TestAskResponse:
    def test_valid_response(self):
        """合法响应应通过验证"""
        resp = AskResponse(
            answer="RAG 是一种检索增强生成技术。",
            sources=[
                SourceItem(index=1, source="test.pdf", page=1, snippet="RAG 是...")
            ],
            latency_ms=123.45,
        )
        assert resp.answer == "RAG 是一种检索增强生成技术。"
        assert len(resp.sources) == 1
        assert resp.latency_ms == 123.45

    def test_response_without_sources(self):
        """无来源的响应也应合法"""
        resp = AskResponse(answer="知识库中未找到相关答案。", sources=[])
        assert resp.sources == []


class TestUploadResponse:
    def test_valid_response(self):
        resp = UploadResponse(
            status="processing",
            filename="test.pdf",
            message="文档已接收",
        )
        assert resp.status == "processing"


class TestHealthResponse:
    def test_valid_response(self):
        resp = HealthResponse(status="healthy", version="2.0.0")
        assert resp.status == "healthy"
