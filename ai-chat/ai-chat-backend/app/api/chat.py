
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.ai_service import generate_stream_response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    return StreamingResponse(
        generate_stream_response(request.messages, request.model, request.resume_from),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
