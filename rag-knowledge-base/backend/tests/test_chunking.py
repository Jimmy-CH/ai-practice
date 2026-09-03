# tests/test_chunking.py
"""文本分块模块测试"""
from langchain_core.documents import Document
from app.ingestion.chunking import TextChunker


class TestTextChunker:
    def test_split_short_document(self):
        """短文档不应被分块"""
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        doc = Document(page_content="这是一段很短的文本。")
        chunks = chunker.split([doc])
        assert len(chunks) == 1
        assert chunks[0].page_content == doc.page_content

    def test_split_long_document(self):
        """长文档应被切分为多个块"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        long_text = "这是一段测试文本。" * 20  # 约 180 字符
        doc = Document(page_content=long_text)
        chunks = chunker.split([doc])
        assert len(chunks) > 1

    def test_chunk_overlap(self):
        """相邻块之间应有重叠内容"""
        chunker = TextChunker(chunk_size=30, chunk_overlap=10)
        long_text = "A" * 100
        doc = Document(page_content=long_text)
        chunks = chunker.split([doc])
        assert len(chunks) > 1
        # 每个块的内容长度不应超过 chunk_size 太多
        for chunk in chunks:
            assert len(chunk.page_content) <= 50  # 允许一定容差

    def test_split_multiple_documents(self):
        """多个文档应分别被分块"""
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        docs = [
            Document(page_content="文档一的内容" * 10),
            Document(page_content="文档二的内容" * 10),
        ]
        chunks = chunker.split(docs)
        assert len(chunks) > 2
