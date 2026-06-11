from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/ping")
async def ping():
    return {"status": "dashboard-ok"}
