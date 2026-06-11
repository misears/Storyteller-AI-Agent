from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/ping")
async def ping():
    return {"status": "tools-ok"}
