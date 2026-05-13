from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.articles import router as articles_router
from app.api.routes.users import router as users_router
from app.core.config import settings

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(articles_router)
app.include_router(users_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/", response_class=FileResponse)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
