# app/ingestion/parsers.py
import os
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader


class DocumentParser:
    """文档解析器，支持 PDF 和 TXT 格式"""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt"}

    def parse(self, file_path: str) -> List[Document]:
        """根据文件扩展名选择对应的加载器进行解析"""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件格式: {ext}，仅支持 {self.SUPPORTED_EXTENSIONS}")

        return loader.load()

    @staticmethod
    def is_supported(file_path: str) -> bool:
        """检查文件格式是否受支持"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in DocumentParser.SUPPORTED_EXTENSIONS
