from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    ArticleRead,
    DigestPreview,
    DigestPreviewItem,
    FeedbackCreate,
    FeedbackRead,
    SourceRead,
)
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.feedback import Feedback
from app.models.topic import Topic
from app.feedback.service import (
    FeedbackNotFoundError,
    FeedbackValidationError,
    create_feedback_and_update_preferences,
)
from app.ranking.service import RankingUserNotFoundError, rank_articles_for_digest

router = APIRouter()


def _get_article_topics(db: Session, article_id: int) -> list[str]:
    return db.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


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
            topics=_get_article_topics(db, article.id),
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


@router.get("/digest/preview", response_model=DigestPreview)
def preview_digest(
    limit: int = 10,
    user_id: int | None = None,
    db: Session = Depends(get_db),
) -> DigestPreview:
    """Return a lightweight digest preview without persisting Digest rows."""

    clamped_limit = max(1, min(limit, 50))
    try:
        ranked_articles = rank_articles_for_digest(db, limit=clamped_limit, user_id=user_id)
    except RankingUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = [
        DigestPreviewItem(
            rank=index,
            article_id=ranked_article.article.id,
            title=ranked_article.article.title,
            url=ranked_article.article.url,
            source_name=ranked_article.source_name,
            published_at=ranked_article.article.published_at,
            created_at=ranked_article.article.created_at,
            topics=ranked_article.topics,
        )
        for index, ranked_article in enumerate(ranked_articles, start=1)
    ]
    return DigestPreview(items=items)


@router.get("/feedback", response_model=list[FeedbackRead])
def list_feedback(
    user_id: int | None = None,
    article_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[FeedbackRead]:
    clamped_limit = max(1, min(limit, 100))
    query = select(Feedback)
    if user_id is not None:
        query = query.where(Feedback.user_id == user_id)
    if article_id is not None:
        query = query.where(Feedback.article_id == article_id)

    feedback_rows = db.scalars(
        query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(clamped_limit)
    ).all()
    return [
        FeedbackRead(
            id=feedback.id,
            user_id=feedback.user_id,
            article_id=feedback.article_id,
            label=feedback.label.name,
            created_at=feedback.created_at,
        )
        for feedback in feedback_rows
    ]


@router.post("/feedback", response_model=FeedbackRead)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackRead:
    try:
        feedback = create_feedback_and_update_preferences(
            session=db,
            user_id=payload.user_id,
            article_id=payload.article_id,
            label=payload.label,
        )
    except FeedbackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FeedbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FeedbackRead(
        id=feedback.id,
        user_id=feedback.user_id,
        article_id=feedback.article_id,
        label=feedback.label.name,
        created_at=feedback.created_at,
    )
