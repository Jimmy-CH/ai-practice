"""海报配图接口：提炼画面描述 / 生图 / 列表 / 文件 / 删除。

权限：提炼与生图仅 editor（沿用 get_current_user + 函数体判 role 的既有模式，
勿用返回 Pydantic 模型的自定义依赖，会被并入请求体 schema 导致 422）。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import UserOut
from app.api.auth import get_current_user
from app.services import poster_image_service as poster_svc
from app.services import poster_writer
from app.models.poster_image import compute_script_hash

router = APIRouter()


class PosterPromptRequest(BaseModel):
    script_content: str


class PosterImageCreate(BaseModel):
    source_title: str
    audience: str
    prompt: str


def _require_editor(user: UserOut) -> None:
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")


@router.post("/prompt")
async def refine_prompt_endpoint(
    data: PosterPromptRequest,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    if not data.script_content.strip():
        raise HTTPException(status_code=400, detail="海报脚本内容为空")
    script_hash = compute_script_hash(data.script_content)
    cached = await poster_svc.get_poster_prompt(db, user.id, script_hash)
    if cached is not None:
        return {"prompt": cached.prompt, "cached": True}
    try:
        description = await poster_writer.refine_poster_prompt(data.script_content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"画面描述提炼失败: {exc}") from exc
    saved = await poster_svc.upsert_poster_prompt(db, user.id, script_hash, description)
    return {"prompt": saved.prompt, "cached": False}


@router.post("/images")
async def create_image_endpoint(
    data: PosterImageCreate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="画面描述为空")
    try:
        _, image_bytes = await poster_writer.generate_poster_image(data.prompt)
        file_path = poster_writer.save_poster_image(user.id, image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"海报图生成失败: {exc}") from exc
    try:
        saved = await poster_svc.create_poster_image(
            db, user.id, data.source_title, data.audience, data.prompt,
            file_path, len(image_bytes),
        )
    except Exception:
        poster_writer.remove_poster_image(file_path)  # 入库失败回滚，不留孤儿文件
        raise
    return saved.to_dict()


@router.get("/images")
async def list_images_endpoint(
    source_title: str,
    audience: str,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    images = await poster_svc.list_poster_images(db, user.id, source_title, audience)
    return [image.to_dict() for image in images]
