import asyncio
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, get_db
from app.schemas.auth import UserOut
from app.schemas.generation import SaveFromGenerationRequest
from app.schemas.material import MaterialCreate, MaterialOut
from app.api.auth import get_current_user
from app.services import material_service as material_svc
from app.services import analysis_service as analysis_svc
from app.services import generated_material_service as gm_svc
from app.services import material_writer
from app.services.docx_parser import parse_docx_file
from app.services.analyzer import analyze_document
from app.services.material_writer import (
    generate_material,
    generate_all_materials,
    generate_material_deduped,
    MATERIAL_TYPES,
)
from app.models.generated_material import compute_analysis_hash

logger = logging.getLogger("app.api.generator")

router = APIRouter()


async def pregenerate_materials(
    owner_id: int,
    title: str,
    analysis: dict,
    audience: str,
    session_factory=None,
) -> None:
    """后台预热：为当前受众生成全部 6 种物料并写缓存，不阻塞解析响应。

    每种物料完成即单独落库，且落库包含在生成任务内部（任务结束才释放去重键），
    因此预热期间的用户请求要么命中缓存、要么复用同一在飞任务，不会重复调用模型。
    使用独立数据库会话（请求会话在响应后已关闭）；单个类型失败仅记日志，其余照常落库。
    """
    analysis_hash = compute_analysis_hash(analysis)
    factory = session_factory or AsyncSessionLocal
    write_lock = asyncio.Lock()

    async def generate_and_cache(material_type: str) -> None:
        async def produce() -> dict:
            # 经模块引用调用，与 generate_all_materials 保持同一 patch 目标
            result = await material_writer.generate_material(title, analysis, audience, material_type)
            # 串行落库：避免 SQLite 并发写锁争用，也保证任务结束前缓存已可见
            async with write_lock:
                async with factory() as session:
                    await gm_svc.upsert_generated_material(
                        session, owner_id, title, audience,
                        material_type, analysis_hash, result["content"],
                    )
            return result

        key = (owner_id, title, audience, material_type, analysis_hash)
        await generate_material_deduped(key, produce)

    try:
        results = await asyncio.gather(
            *(generate_and_cache(material_type) for material_type in MATERIAL_TYPES),
            return_exceptions=True,
        )
        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            logger.warning(
                "pregenerate_materials '%s' audience='%s' failures=%s first=%s",
                title, audience, len(failures), failures[0],
            )
        else:
            logger.info(
                "pregenerate_materials '%s' audience='%s' count=%s",
                title, audience, len(results),
            )
    except Exception as exc:
        logger.warning("pregenerate_materials '%s' audience='%s' failed: %s", title, audience, exc)


@router.post("/parse")
async def parse_endpoint(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    content: str = Form(""),
    audience: str = Form("网点管理员"),
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

        # 物料预热移交后台执行：解析结果立即返回，预热完成后写入缓存供后续命中
        background_tasks.add_task(pregenerate_materials, user.id, title, result, audience)

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
    analysis_hash = compute_analysis_hash(analysis)
    try:
        cached = await gm_svc.get_generated_material(
            db, user.id, title, audience, material_type, analysis_hash
        )
        if cached is not None:
            return {**cached.to_dict(), "title": title, "meta": {
                "audience": audience,
                "material_type": MATERIAL_TYPES.get(material_type, material_type),
                "generator": "DeepSeek",
            }, "cached": True}

        # 与后台预热共用同一去重键：预热在飞时直接复用该任务，不会重复调用模型
        result = await generate_material_deduped(
            (user.id, title, audience, material_type, analysis_hash),
            lambda: generate_material(title, analysis, audience, material_type),
        )
        saved = await gm_svc.upsert_generated_material(
            db, user.id, title, audience, material_type, analysis_hash, result["content"]
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
    analysis_hash = compute_analysis_hash(analysis)
    try:
        cached_materials = {}
        missing_types = set()
        for material_type in MATERIAL_TYPES:
            cached = await gm_svc.get_generated_material(
                db, user.id, title, audience, material_type, analysis_hash
            )
            if cached is not None:
                cached_materials[material_type] = {
                    **cached.to_dict(),
                    "title": title,
                    "meta": {
                        "audience": audience,
                        "material_type": MATERIAL_TYPES[material_type],
                        "generator": "DeepSeek",
                    },
                    "cached": True,
                }
            else:
                missing_types.add(material_type)

        # only_types 为白名单：全命中时 missing_types 为空集，不会发起任何模型调用
        # dedup_keys 与后台预热共用同一在飞任务，撞车时复用而非重复调用模型
        dedup_keys = {
            material_type: (user.id, title, audience, material_type, analysis_hash)
            for material_type in missing_types
        }
        generated = await generate_all_materials(title, analysis, audience, missing_types, dedup_keys)
        generated_with_id = []
        for item in generated:
            saved = await gm_svc.upsert_generated_material(
                db, user.id, title, audience, item["material_type"], analysis_hash, item["content"]
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
