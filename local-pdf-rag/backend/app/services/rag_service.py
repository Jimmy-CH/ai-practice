import uuid
from datetime import datetime, timezone
from functools import lru_cache

from app.config import settings
from app.ingestion.chunker import TextChunker
from app.ingestion.pdf_parser import PdfParser
from app.schemas import AskResponse, DocumentOut, SourceOut
from app.services.ollama_client import OllamaClient
from app.storage.base import ChunkRecord, DocumentRecord, SearchHit, VectorStore
from app.storage.json_store import JsonVectorStore


class EmptyDocumentError(Exception):
    """PDF 中没有任何可切分的文本。"""


class EmptyIndexError(Exception):
    """知识库中没有片段，无法检索。"""


class RagService:
    def __init__(
        self,
        store: VectorStore,
        ollama: OllamaClient,
        parser: PdfParser | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self.store = store
        self.ollama = ollama
        self.parser = parser or PdfParser()
        self.chunker = chunker or TextChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

    async def ingest(self, filename: str, data: bytes) -> DocumentOut:
        pages = self.parser.parse_bytes(data)
        pieces = []
        for page in pages:
            for piece in self.chunker.split(page.text):
                pieces.append((page.page, piece))
        if not pieces:
            raise EmptyDocumentError("PDF 未提取到可用文本")

        embeddings = await self.ollama.embed([piece.text for _, piece in pieces])
        doc_id = uuid.uuid4().hex
        chunks = [
            ChunkRecord(
                id=uuid.uuid4().hex,
                doc_id=doc_id,
                filename=filename,
                page=page_no,
                index=index,
                start=piece.start,
                end=piece.end,
                text=piece.text,
                embedding=embedding,
            )
            for index, ((page_no, piece), embedding) in enumerate(zip(pieces, embeddings))
        ]
        document = DocumentRecord(
            id=doc_id,
            filename=filename,
            page_count=len(pages),
            chunk_count=len(chunks),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self.store.add_document(document, chunks)
        return DocumentOut(**document.__dict__)

    async def ask(self, question: str) -> AskResponse:
        _, chunk_count = await self.store.counts()
        if chunk_count == 0:
            raise EmptyIndexError("知识库为空，请先上传 PDF")

        query_embedding = (await self.ollama.embed([question]))[0]
        hits = await self.store.search(query_embedding, settings.TOP_K)
        answer = await self.ollama.chat(self._build_messages(question, hits))
        sources = [
            SourceOut(
                index=index,
                document_id=hit.chunk.doc_id,
                filename=hit.chunk.filename,
                page=hit.chunk.page,
                score=round(hit.score, 4),
                snippet=hit.chunk.text[:120],
            )
            for index, hit in enumerate(hits, start=1)
        ]
        return AskResponse(answer=answer, sources=sources)

    @staticmethod
    def _build_messages(question: str, hits: list[SearchHit]) -> list[dict]:
        context = "\n\n".join(
            f"[{index}] ({hit.chunk.filename} p{hit.chunk.page})\n{hit.chunk.text}"
            for index, hit in enumerate(hits, start=1)
        )
        system = (
            "你是文档问答助手。只依据下方上下文回答；如果上下文不足以回答，"
            "请明确说“根据提供的文档无法回答”。引用时在句末标注 [文件名 p页码]。"
        )
        user = f"上下文:\n{context}\n\n问题: {question}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


@lru_cache(maxsize=1)
def get_service() -> RagService:
    """延迟装配默认服务；测试通过 dependency_overrides 替换。"""
    return RagService(
        store=JsonVectorStore(settings.INDEX_PATH),
        ollama=OllamaClient(
            base_url=settings.OLLAMA_BASE_URL,
            embed_model=settings.EMBED_MODEL,
            chat_model=settings.CHAT_MODEL,
            timeout=settings.OLLAMA_TIMEOUT,
        ),
    )
