from fastapi import APIRouter

from app.api import assets as assets_api
from app.api import audit as audit_api
from app.api import auth as auth_api
from app.api import delivery as delivery_api
from app.api import generation as generation_api
from app.api import projects as projects_api

api_router = APIRouter()
api_router.include_router(auth_api.router)
api_router.include_router(projects_api.router)
api_router.include_router(generation_api.router)
api_router.include_router(assets_api.router)
api_router.include_router(delivery_api.router)
api_router.include_router(audit_api.router)
