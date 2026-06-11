from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routers import documents, gm, sessions

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Storyteller AI Backend")
app.include_router(documents.router)
app.include_router(gm.router)
app.include_router(sessions.router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/health")
async def health():
    return {"status": "ok"}
