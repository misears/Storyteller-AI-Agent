from fastapi import FastAPI
from .routers import gm, sessions

app = FastAPI(title="Storyteller AI Backend")

app.include_router(gm.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
