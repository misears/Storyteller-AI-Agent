import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .persistence.db import upgrade_database
from .routers import campaigns, character_sheets, documents, gm, packs, sessions, settings
from .services.browser_launcher import launch_browser_when_ready
from .services.app_paths import get_frontend_dir

FRONTEND_DIR = get_frontend_dir()
FRONTEND_SERVE_DIR = FRONTEND_DIR / "dist" if (FRONTEND_DIR / "dist").exists() else FRONTEND_DIR
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "STORYTELLER_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]
if "*" in CORS_ORIGINS:
    raise ValueError("STORYTELLER_CORS_ORIGINS cannot contain '*' with credentials enabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    upgrade_database()
    launch_browser_when_ready()
    yield


app = FastAPI(title="Storyteller AI Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_size_limit(request, call_next):
    max_bytes = int(os.getenv("STORYTELLER_MAX_REQUEST_BYTES", str(4 * 1024 * 1024)))
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "request body too large"}, status_code=413)
    return await call_next(request)
app.include_router(documents.router)
app.include_router(gm.router)
app.include_router(sessions.router)
app.include_router(campaigns.router)
app.include_router(character_sheets.router)
app.include_router(settings.router)
app.include_router(packs.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=FRONTEND_SERVE_DIR, html=True), name="frontend")
