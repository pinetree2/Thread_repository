from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DOCS_DIR = BASE_DIR.parent / "docs"

app = FastAPI(
    title="Trend2Threads AI",
    version="2.0.0",
    description="Global AI/Tech trend detection, fact verification, human approval, and Threads publishing graph.",
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/project-docs", StaticFiles(directory=DOCS_DIR, html=True), name="project-docs")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
