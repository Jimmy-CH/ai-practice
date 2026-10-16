"""接口路由集中注册表。

所有业务路由统一在此汇总，main.py 只需调用 register_routers(app) 即可完成挂载。
新增接口模块时：在 app/api/ 下新建模块导出 router，然后在此追加一行 include_router，
并同步更新下方接口总览。

注意：register_routers 必须在 register_static 之前调用，避免 SPA catch-all 拦截 /api。

---- 接口总览（以各模块装饰器为准） ----
认证 auth
  POST   /api/auth/login                        登录，返回 access_token
  GET    /api/auth/me                           当前用户信息
物料 materials
  GET    /api/materials                         物料列表（editor 仅看自己的）
  POST   /api/materials                         新建物料
  GET    /api/materials/pending                 待审核列表（reviewer 专属）
  GET    /api/materials/approved                已通过列表
  GET    /api/materials/{material_id}           物料详情
  PUT    /api/materials/{material_id}           更新物料
  DELETE /api/materials/{material_id}           删除草稿/被驳回物料
  POST   /api/materials/{material_id}/submit    提交审核
  POST   /api/materials/{material_id}/reviews   审核通过/驳回（reviewer 专属）
  GET    /api/materials/{material_id}/download  下载已审核通过物料（.md）
解析结果 analyses
  GET    /api/analyses/{source_title}           按来源标题查解析结果
  PUT    /api/analyses/{analysis_id}            更新解析结果
生成物料 generated_materials
  PUT    /api/generated-materials/{id}          编辑已生成物料内容
生成器 generator
  POST   /api/parse                             解析文档（正文/.docx），后台预热生成
  POST   /api/generate                          生成单种物料（命中缓存直接返回）
  POST   /api/generate-all                      生成全部 6 种物料（未命中的才调模型）
  POST   /api/materials/from-generation         从生成结果保存为正式物料
健康检查
  GET    /api/health                            存活探测
"""
from fastapi import APIRouter, FastAPI

from app.api.analyses import router as analyses_router
from app.api.auth import router as auth_router
from app.api.generated_materials import router as generated_materials_router
from app.api.generator import router as generator_router
from app.api.materials import router as materials_router

health_router = APIRouter()


@health_router.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def register_routers(app: FastAPI) -> None:
    """把全部接口路由挂载到 app；各子路由保持与原 main.py 完全一致的挂载方式。"""
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api")
    app.include_router(materials_router, prefix="/api")
    app.include_router(analyses_router, prefix="/api/analyses")
    app.include_router(generated_materials_router, prefix="/api/generated-materials")
    app.include_router(generator_router, prefix="/api")
