
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "username": current_user.username}
