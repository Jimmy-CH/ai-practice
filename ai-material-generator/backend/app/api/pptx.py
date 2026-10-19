"""培训课件 PPTX 导出接口。

只接收前端当前展示的大纲内容，实时生成并直接返回文件流，不落盘、不写数据库、
不调用大模型。权限沿用「路由签名取 current_user + 函数体判 role」的既有模式。
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.schemas.auth import UserOut
from app.services import pptx_writer

router = APIRouter()

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class TrainingOutlinePptxRequest(BaseModel):
    title: str = ""
    content: str
    audience: str = ""
    source_title: str = ""


@router.post("/training-outline")
async def export_training_outline_pptx(
    data: TrainingOutlinePptxRequest,
    user: UserOut = Depends(get_current_user),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="培训课件大纲内容为空")
    try:
        pptx_bytes = pptx_writer.build_training_pptx(
            data.title or "培训课件",
            data.content,
            data.audience,
            data.source_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PPT 生成失败: {exc}") from exc

    filename = pptx_writer.build_filename(data.title or "培训课件", data.audience)
    disposition = (
        'attachment; filename="training-outline.pptx"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return Response(
        content=pptx_bytes,
        media_type=PPTX_MEDIA_TYPE,
        headers={"Content-Disposition": disposition},
    )
