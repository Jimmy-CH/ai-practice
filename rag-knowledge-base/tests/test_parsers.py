# tests/test_parsers.py
"""文档解析模块测试"""
import pytest
from app.ingestion.parsers import DocumentParser


@pytest.fixture
def parser():
    return DocumentParser()


class TestDocumentParser:
    def test_parse_txt(self, parser, sample_txt_path):
        """TXT 文件应成功解析为 Document 列表"""
        docs = parser.parse(sample_txt_path)
        assert len(docs) >= 1
        assert "RAG" in docs[0].page_content

    def test_parse_unsupported_format(self, parser, unsupported_file_path):
        """不支持的格式应抛出 ValueError"""
        with pytest.raises(ValueError, match="不支持的文件格式"):
            parser.parse(unsupported_file_path)

    def test_is_supported(self, parser):
        """is_supported 应正确识别支持/不支持的格式"""
        assert parser.is_supported("doc.pdf") is True
        assert parser.is_supported("doc.txt") is True
        assert parser.is_supported("doc.PDF") is True
        assert parser.is_supported("doc.csv") is False
        assert parser.is_supported("doc.docx") is False
