from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    ArticleRead,
    DigestPreview,
    DigestItemRead,
    DigestPreviewItem,
    DigestRead,
    DigestDeliveryRead,
    DigestScoreBreakdown,
    DigestSummaryRead,
    DeliveryPreviewRead,
    FeedbackCreate,
    FeedbackRead,
    SourceRead,
)
from app.delivery.service import (
    DigestDeliveryNotFoundError,
    DeliveryPreviewNotFoundError,
    get_delivery,
    list_digest_deliveries,
    render_digest_delivery_preview,
    send_digest_local_email,
)
from app.digests.service import DigestUserNotFoundError, EmptyDigestError, generate_digest_for_user
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest, DigestDelivery, DigestItem
from app.models.feedback import Feedback
from app.models.topic import Topic
from app.models.user import User
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




def _delivery_to_read(delivery: DigestDelivery) -> DigestDeliveryRead:
    return DigestDeliveryRead(
        id=delivery.id,
        digest_id=delivery.digest_id,
        user_id=delivery.user_id,
        channel=delivery.channel,
        provider=delivery.provider,
        recipient_email=delivery.recipient_email,
        subject=delivery.subject,
        html_body=delivery.html_body,
        text_body=delivery.text_body,
        status=delivery.status.name,
        feedback_token=delivery.feedback_token,
        error_message=delivery.error_message,
        created_at=delivery.created_at,
        sent_at=delivery.sent_at,
    )


def _feedback_confirmation_html(title: str, body: str, status: str = "success") -> str:
    accent = "#16a34a" if status == "success" else "#dc2626"
    return f"""
    <!doctype html>
    <html lang=\"en\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>YourNews feedback</title>
      </head>
      <body style=\"font-family:Arial,sans-serif;background:#f8fbff;color:#0f172a;padding:32px;\">
        <main style=\"max-width:640px;margin:0 auto;background:#fff;border:1px solid #dbe3ef;border-radius:18px;padding:28px;\">
          <p style=\"color:#2563eb;font-weight:700;text-transform:uppercase;font-size:12px;letter-spacing:0.08em;\">YourNews</p>
          <h1 style=\"margin:0 0 12px 0;color:{accent};\">{escape(title)}</h1>
          <p style=\"line-height:1.6;color:#334155;\">{body}</p>
          <p><a href=\"/\" style=\"display:inline-block;background:#2563eb;color:#fff;text-decoration:none;border-radius:999px;padding:10px 14px;font-weight:700;\">Back to dashboard</a></p>
        </main>
      </body>
    </html>
    """.strip()


def _feedback_error_response(message: str, status_code: int) -> HTMLResponse:
    html = _feedback_confirmation_html(
        title="Feedback not saved",
        body=escape(message),
        status="error",
    )
    return HTMLResponse(content=html, status_code=status_code)


def _digest_to_read(db: Session, digest: Digest) -> DigestRead:
    rows = db.execute(
        select(DigestItem, Article, ArticleSource.name)
        .join(Article, DigestItem.article_id == Article.id)
        .join(ArticleSource, Article.source_id == ArticleSource.id)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.rank.asc())
    ).all()

    return DigestRead(
        id=digest.id,
        user_id=digest.user_id,
        created_at=digest.created_at,
        items=[
            DigestItemRead(
                rank=item.rank,
                article_id=article.id,
                title=article.title,
                url=article.url,
                source_name=source_name,
                topics=_get_article_topics(db, article.id),
            )
            for item, article, source_name in rows
        ],
    )


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
            category=source.category,
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
            score=ranked_article.score,
            score_breakdown=DigestScoreBreakdown(
                total_score=ranked_article.score_breakdown.total_score,
                topic_score=ranked_article.score_breakdown.topic_score,
                preference_score=ranked_article.score_breakdown.preference_score,
                freshness_score=ranked_article.score_breakdown.freshness_score,
                source_penalty=ranked_article.score_breakdown.source_penalty,
            ),
        )
        for index, ranked_article in enumerate(ranked_articles, start=1)
    ]
    return DigestPreview(items=items)


@router.post("/digests/generate", response_model=DigestRead)
def generate_digest(
    user_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> DigestRead:
    clamped_limit = max(1, min(limit, 50))
    try:
        digest = generate_digest_for_user(db, user_id=user_id, limit=clamped_limit)
    except DigestUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EmptyDigestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _digest_to_read(db, digest)


@router.get("/digests/{digest_id}", response_model=DigestRead)
def get_digest(digest_id: int, db: Session = Depends(get_db)) -> DigestRead:
    digest = db.get(Digest, digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return _digest_to_read(db, digest)


@router.get("/digests/{digest_id}/delivery-preview", response_model=DeliveryPreviewRead)
def get_digest_delivery_preview(digest_id: int, db: Session = Depends(get_db)) -> DeliveryPreviewRead:
    try:
        preview = render_digest_delivery_preview(db, digest_id)
    except DeliveryPreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DeliveryPreviewRead(
        subject=preview.subject,
        user_email=preview.user_email,
        digest_id=preview.digest_id,
        created_at=preview.created_at,
        html_body=preview.html_body,
        text_body=preview.text_body,
    )


@router.post("/digests/{digest_id}/send", response_model=DigestDeliveryRead)
def send_digest(digest_id: int, db: Session = Depends(get_db)) -> DigestDeliveryRead:
    try:
        delivery = send_digest_local_email(db, digest_id)
    except DigestDeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _delivery_to_read(delivery)


@router.get("/digests/{digest_id}/deliveries", response_model=list[DigestDeliveryRead])
def get_digest_deliveries(digest_id: int, db: Session = Depends(get_db)) -> list[DigestDeliveryRead]:
    try:
        deliveries = list_digest_deliveries(db, digest_id)
    except DigestDeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_delivery_to_read(delivery) for delivery in deliveries]


@router.get("/deliveries/{delivery_id}", response_model=DigestDeliveryRead)
def get_digest_delivery(delivery_id: int, db: Session = Depends(get_db)) -> DigestDeliveryRead:
    try:
        delivery = get_delivery(db, delivery_id)
    except DigestDeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _delivery_to_read(delivery)


@router.get("/users/{user_id}/digests", response_model=list[DigestSummaryRead])
def list_user_digests(user_id: int, db: Session = Depends(get_db)) -> list[DigestSummaryRead]:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    rows = db.execute(
        select(Digest, func.count(DigestItem.article_id).label("item_count"))
        .outerjoin(DigestItem, DigestItem.digest_id == Digest.id)
        .where(Digest.user_id == user_id)
        .group_by(Digest.id)
        .order_by(Digest.created_at.desc(), Digest.id.desc())
    ).all()
    return [
        DigestSummaryRead(
            id=digest.id,
            user_id=digest.user_id,
            created_at=digest.created_at,
            item_count=item_count,
        )
        for digest, item_count in rows
    ]


@router.get("/feedback/click", response_class=HTMLResponse)
def click_feedback(
    delivery_id: int,
    article_id: int,
    label: str,
    token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    delivery = db.get(DigestDelivery, delivery_id)
    if delivery is None:
        return _feedback_error_response("Unknown delivery.", 404)
    if token != delivery.feedback_token:
        return _feedback_error_response("Invalid feedback token.", 403)

    digest_item = db.scalar(
        select(DigestItem).where(
            DigestItem.digest_id == delivery.digest_id,
            DigestItem.article_id == article_id,
        )
    )
    if digest_item is None:
        return _feedback_error_response("This article is not part of the delivered digest.", 400)

    article = db.get(Article, article_id)
    try:
        feedback = create_feedback_and_update_preferences(
            session=db,
            user_id=delivery.user_id,
            article_id=article_id,
            label=label,
        )
    except FeedbackValidationError:
        return _feedback_error_response("Invalid feedback label.", 400)
    except FeedbackNotFoundError as exc:
        return _feedback_error_response(str(exc), 404)

    label_text = feedback.label.value.replace("_", " ")
    article_text = f" for <strong>{escape(article.title)}</strong>" if article else ""
    html = _feedback_confirmation_html(
        title="Feedback saved",
        body=(
            f"Saved <strong>{escape(label_text)}</strong>{article_text}. "
            "Future YourNews digests will use this signal to improve your recommendations."
        ),
    )
    return HTMLResponse(content=html)


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
