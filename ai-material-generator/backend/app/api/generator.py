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
from app.services import generated_material_service as gm_svc
from app.services.docx_parser import parse_docx_file
from app.services.analyzer import analyze_document
from app.services.material_writer import generate_material, generate_all_materials, MATERIAL_TYPES

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
    db: AsyncSession = Depends(get_db),
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
        cached = await gm_svc.get_generated_material(
            db, user.id, title, audience, material_type
        )
        if cached is not None:
            return {**cached.to_dict(), "cached": True}

        result = await generate_material(title, analysis, audience, material_type)
        saved = await gm_svc.upsert_generated_material(
            db, user.id, title, audience, material_type, result["content"]
        )
        return {**saved.to_dict(), "title": result["title"], "meta": result["meta"], "cached": False}
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
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    if not analysis or not audience:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        cached_materials = {}
        missing_types = set()
        for material_type in MATERIAL_TYPES:
            cached = await gm_svc.get_generated_material(
                db, user.id, title, audience, material_type
            )
            if cached is not None:
                cached_materials[material_type] = {
                    "title": title,
                    "content": cached.content,
                    "audience": audience,
                    "material_type": material_type,
                    "meta": {
                        "audience": audience,
                        "material_type": MATERIAL_TYPES[material_type],
                        "generator": "DeepSeek",
                    },
                    "cached": True,
                }
            else:
                missing_types.add(material_type)

        generated = await generate_all_materials(title, analysis, audience, missing_types)
        generated_with_id = []
        for item in generated:
            saved = await gm_svc.upsert_generated_material(
                db, user.id, title, audience, item["material_type"], item["content"]
            )
            generated_with_id.append({**saved.to_dict(), "title": item["title"], "meta": item["meta"], "cached": False})

        materials = []
        for material_type in MATERIAL_TYPES:
            if material_type in cached_materials:
                materials.append(cached_materials[material_type])
            else:
                for item in generated_with_id:
                    if item["material_type"] == material_type:
                        materials.append(item)
                        break

        return {"audience": audience, "materials": materials}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc
