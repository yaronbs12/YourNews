from fastapi import FastAPI

from app.api.routes.articles import router as articles_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(articles_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
