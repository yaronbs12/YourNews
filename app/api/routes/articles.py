from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import ArticleRead, DigestPreview, DigestPreviewItem, SourceRead
from app.models.article import Article
from app.models.article_source import ArticleSource

router = APIRouter()


@router.get("/articles", response_model=list[ArticleRead])
def list_articles(limit: int = 20, db: Session = Depends(get_db)) -> list[ArticleRead]:
    clamped_limit = max(1, min(limit, 100))
    rows = db.execute(
        select(Article, ArticleSource.name)
        .join(ArticleSource, Article.source_id == ArticleSource.id)
        .order_by(Article.created_at.desc())
        .limit(clamped_limit)
    ).all()

    return [
        ArticleRead(
            id=article.id,
            title=article.title,
            url=article.url,
            content=article.content,
            published_at=article.published_at,
            created_at=article.created_at,
            source_name=source_name,
        )
        for article, source_name in rows
    ]


@router.get("/sources", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)) -> list[SourceRead]:
    sources = db.scalars(select(ArticleSource).order_by(ArticleSource.name.asc())).all()
    return [
        SourceRead(
            id=source.id,
            name=source.name,
            url=source.url,
            source_type=source.source_type,
            enabled=source.enabled,
            last_fetched_at=source.last_fetched_at,
        )
        for source in sources
    ]
