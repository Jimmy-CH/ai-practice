from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.services.docx_parser import parse_docx_file
from app.services.analyzer import analyze_document
from app.services.material_writer import generate_material, generate_all_materials

router = APIRouter()


@router.post("/parse")
async def parse_endpoint(
    title: str = Form(...),
    content: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not content and not file:
        raise HTTPException(status_code=400, detail="请输入文档正文或上传 .docx 文件")
    if file and not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式 Word 文档")
    try:
        if file:
            suffix = Path(file.filename).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            content = parse_docx_file(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
        if not content.strip():
            raise HTTPException(status_code=400, detail="文档正文为空")
        result = await analyze_document(title, content)
        return {"title": title, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc}") from exc


@router.post("/generate")
async def generate_endpoint(payload: dict):
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


@router.post("/generate-all")
async def generate_all_endpoint(payload: dict):
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
