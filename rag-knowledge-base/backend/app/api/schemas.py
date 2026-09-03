# app/api/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """问答请求体"""
    question: str = Field(..., min_length=1, description="用户提问内容")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="检索返回的相关片段数量")


class SourceItem(BaseModel):
    """引用来源条目"""
    index: int = Field(..., description="来源序号")
    source: str = Field(..., description="来源文件名")
    page: int = Field(..., description="来源页码")
    snippet: str = Field(..., description="内容摘要")


class AskResponse(BaseModel):
    """问答响应体"""
    answer: str = Field(..., description="LLM 生成的回答")
    sources: List[SourceItem] = Field(default_factory=list, description="引用来源列表")
    latency_ms: Optional[float] = Field(None, description="请求耗时（毫秒）")


class UploadResponse(BaseModel):
    """文档上传响应体"""
    status: str = Field(..., description="处理状态")
    filename: str = Field(..., description="上传的文件名")
    message: str = Field(..., description="状态说明")


class HealthResponse(BaseModel):
    """健康检查响应体"""
    status: str
    version: str
