from datetime import datetime
from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    is_active: bool
    role_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    permissions: list[str]

    model_config = {"from_attributes": True}


class UpdateRoleRequest(BaseModel):
    role_id: int


class UpdateActiveRequest(BaseModel):
    is_active: bool


class UpdateProfileRequest(BaseModel):
    email: str | None = None
    phone: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ProfileStatsOut(BaseModel):
    total_queries: int = 0
    saved_queries: int = 0
    shared_links: int = 0
    data_sources: int = 0
