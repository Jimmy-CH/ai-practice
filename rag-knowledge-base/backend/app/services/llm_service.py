# app/services/llm_service.py
from langchain_openai import ChatOpenAI
from app.config import settings


class LLMService:
    """LLM 服务封装，通过 OpenAI 兼容接口调用 DeepSeek"""

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            openai_api_key=settings.DEEPSEEK_API_KEY,
            openai_api_base=settings.DEEPSEEK_BASE_URL,
        )

    @property
    def llm(self) -> ChatOpenAI:
        """获取底层 LangChain ChatModel 实例"""
        return self._llm
