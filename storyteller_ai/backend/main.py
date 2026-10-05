import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .persistence.db import upgrade_database
from .routers import campaigns, character_sheets, documents, gm, packs, sessions, settings
from .services.browser_launcher import launch_browser_when_ready
from .services.app_paths import get_frontend_dir
from .services.ai_setup import ai_setup_service

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
    manage_ai = os.getenv("STORYTELLER_MANAGE_AI", "0").strip() == "1"
    if manage_ai:
        await ai_setup_service.initialize()
    try:
        yield
    finally:
        if manage_ai:
            await ai_setup_service.shutdown()


app = FastAPI(title="Storyteller AI Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestSizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = int(os.getenv("STORYTELLER_MAX_REQUEST_BYTES", str(4 * 1024 * 1024)))
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length and int(content_length) > max_bytes:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
            await response(scope, receive, send)
            return

        body = bytearray()
        too_large = False
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if not too_large:
                    if len(body) + len(chunk) > max_bytes:
                        too_large = True
                        body.clear()
                    else:
                        body.extend(chunk)
                if not message.get("more_body", False):
                    break

        if too_large:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
            await response(scope, receive, send)
            return

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


app.add_middleware(RequestSizeLimitMiddleware)
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
