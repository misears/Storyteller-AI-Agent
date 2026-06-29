from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routers import documents, gm, sessions, settings
from .services.browser_launcher import launch_browser_when_ready
from .services.app_paths import get_frontend_dir

FRONTEND_DIR = get_frontend_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    launch_browser_when_ready()
    yield


app = FastAPI(title="Storyteller AI Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)
app.include_router(gm.router)
app.include_router(sessions.router)
app.include_router(settings.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
