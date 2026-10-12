from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/assets", tags=["delivery"])


@router.get("/{asset_id}/download")
async def download_asset(asset_id: str, format: str) -> dict[str, str]:
    raise HTTPException(status_code=404, detail="资产不存在")
