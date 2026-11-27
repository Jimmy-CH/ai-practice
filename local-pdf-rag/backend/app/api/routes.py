from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import settings
from app.ingestion.pdf_parser import PdfParseError
from app.schemas import AskRequest, AskResponse, DocumentOut, HealthOut
from app.services.ollama_client import OllamaError
from app.services.rag_service import EmptyDocumentError, EmptyIndexError, RagService, get_service

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut)
async def health(service: RagService = Depends(get_service)) -> HealthOut:
    documents, chunks = await service.store.counts()
    return HealthOut(
        status="ok",
        ollama_reachable=await service.ollama.ping(),
        embed_model=settings.EMBED_MODEL,
        chat_model=settings.CHAT_MODEL,
        documents=documents,
        chunks=chunks,
    )


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    service: RagService = Depends(get_service),
) -> DocumentOut:
    filename = file.filename or "unknown.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="unsupported_file: 仅支持 PDF")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file_too_large: 文件超过大小限制")
    try:
        return await service.ingest(filename, data)
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=f"empty_document: {exc}") from exc
    except PdfParseError as exc:
        raise HTTPException(status_code=400, detail=f"parse_failed: {exc}") from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=f"{exc.code}: {exc.message}") from exc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(service: RagService = Depends(get_service)) -> list[DocumentOut]:
    documents = await service.store.list_documents()
    return [DocumentOut(**document.__dict__) for document in documents]


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, service: RagService = Depends(get_service)) -> None:
    if not await service.store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="document_not_found")


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, service: RagService = Depends(get_service)) -> AskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="empty_question: 问题不能为空")
    try:
        return await service.ask(question)
    except EmptyIndexError as exc:
        raise HTTPException(status_code=400, detail=f"empty_index: {exc}") from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=f"{exc.code}: {exc.message}") from exc
