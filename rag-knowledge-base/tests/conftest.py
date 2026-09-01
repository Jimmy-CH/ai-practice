# tests/conftest.py
import sys
import os
import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_txt_path(tmp_path):
    """创建一个临时 TXT 测试文件"""
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text(
        "这是第一段内容。\n"
        "RAG 系统支持文档解析和向量化。\n\n"
        "这是第二段内容。\n"
        "ChromaDB 是本项目使用的向量数据库。",
        encoding="utf-8",
    )
    return str(txt_file)


@pytest.fixture
def unsupported_file_path(tmp_path):
    """创建一个不支持格式的文件"""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b,c\n1,2,3", encoding="utf-8")
    return str(csv_file)
