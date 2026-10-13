from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import UserOut
from app.schemas.generation import SaveFromGenerationRequest
from app.schemas.material import MaterialCreate, MaterialOut
from app.api.auth import get_current_user
from app.services import material_service as material_svc
from app.services import analysis_service as analysis_svc
from app.services.docx_parser import parse_docx_file
from app.services.analyzer import analyze_document
from app.services.material_writer import generate_material, generate_all_materials

router = APIRouter()


@router.post("/parse")
async def parse_endpoint(
    title: str = Form(...),
    content: str = Form(""),
    file: UploadFile | None = File(None),
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not content and not file:
        raise HTTPException(status_code=400, detail="请输入文档正文或上传 .docx 文件")
    if file and not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式 Word 文档")
    tmp_path = None
    try:
        existing = await analysis_svc.get_analysis_by_title(db, user.id, title)
        if existing is not None:
            return {"analysis_id": existing.id, "title": title, **existing.to_dict()}

        if file:
            suffix = Path(file.filename).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            content = parse_docx_file(tmp_path)
        if not content.strip():
            raise HTTPException(status_code=400, detail="文档正文为空")
        result = await analyze_document(title, content)
        saved = await analysis_svc.upsert_analysis(db, user.id, title, result)
        return {"analysis_id": saved.id, "title": title, **saved.to_dict()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc}") from exc
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.post("/generate")
async def generate_endpoint(
    payload: dict,
    user: UserOut = Depends(get_current_user),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    material_type = payload.get("material_type", "")
    if not analysis or not audience or not material_type:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        return await generate_material(title, analysis, audience, material_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc


@router.post("/materials/from-generation", response_model=MaterialOut)
async def save_from_generation(
    data: SaveFromGenerationRequest,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    return await material_svc.create_material(db, user.id, MaterialCreate(**data.model_dump()))


@router.post("/generate-all")
async def generate_all_endpoint(
    payload: dict,
    user: UserOut = Depends(get_current_user),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    if not analysis or not audience:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        materials = await generate_all_materials(title, analysis, audience)
        return {"audience": audience, "materials": materials}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc
