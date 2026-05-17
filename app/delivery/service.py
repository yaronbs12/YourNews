from dataclasses import dataclass
from datetime import datetime
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest, DigestItem
from app.models.topic import Topic
from app.models.user import User


class DeliveryPreviewNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class DeliveryPreview:
    subject: str
    user_email: str | None
    digest_id: int
    created_at: datetime
    html_body: str
    text_body: str


def render_digest_delivery_preview(session: Session, digest_id: int) -> DeliveryPreview:
    digest = session.get(Digest, digest_id)
    if digest is None:
        raise DeliveryPreviewNotFoundError("Digest not found")

    user = session.get(User, digest.user_id)
    rows = session.execute(
        select(DigestItem, Article, ArticleSource.name)
        .join(Article, DigestItem.article_id == Article.id)
        .join(ArticleSource, Article.source_id == ArticleSource.id)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.rank.asc())
    ).all()

    subject = f"YourNews digest #{digest.id}"
    text_body = _render_text_body(subject, digest.created_at, rows, session, user.email if user else None)
    html_body = _render_html_body(subject, digest.created_at, rows, session, user.email if user else None)
    return DeliveryPreview(
        subject=subject,
        user_email=user.email if user else None,
        digest_id=digest.id,
        created_at=digest.created_at,
        html_body=html_body,
        text_body=text_body,
    )


def _topic_names(session: Session, article_id: int) -> list[str]:
    return session.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


def _render_text_body(subject: str, created_at: datetime, rows: list[tuple], session: Session, email: str | None) -> str:
    lines = [subject, f"Created: {created_at.isoformat()}"]
    if email:
        lines.append(f"To: {email}")
    lines.append("")

    for item, article, source_name in rows:
        topics = ", ".join(_topic_names(session, article.id)) or "none"
        lines.extend(
            [
                f"{item.rank}. {article.title}",
                f"   Source: {source_name}",
                f"   Topics: {topics}",
                f"   URL: {article.url}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _render_html_body(subject: str, created_at: datetime, rows: list[tuple], session: Session, email: str | None) -> str:
    recipient = f"<p style=\"color:#64748b;\">To: {escape(email)}</p>" if email else ""
    items = []
    for item, article, source_name in rows:
        topics = _topic_names(session, article.id)
        topic_html = "".join(
            f'<span style="background:#eff6ff;color:#1e40af;border-radius:999px;padding:3px 8px;margin-right:4px;font-size:12px;">{escape(topic)}</span>'
            for topic in topics
        ) or '<span style="color:#64748b;">No topics</span>'
        items.append(
            f"""
            <li style="margin:0 0 18px 0;padding:16px;border:1px solid #dbe3ef;border-radius:12px;list-style:none;">
              <div style="font-size:12px;font-weight:700;color:#2563eb;">#{item.rank} · {escape(source_name)}</div>
              <h2 style="font-size:18px;margin:6px 0 8px 0;"><a href="{escape(article.url)}" style="color:#0f172a;text-decoration:none;">{escape(article.title)}</a></h2>
              <div style="margin:8px 0;">{topic_html}</div>
              <a href="{escape(article.url)}" style="color:#2563eb;">Read article</a>
            </li>
            """
        )

    return f"""
    <!doctype html>
    <html>
      <body style="font-family:Arial,sans-serif;background:#f8fbff;color:#0f172a;padding:24px;">
        <main style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:18px;padding:24px;border:1px solid #dbe3ef;">
          <p style="color:#2563eb;font-weight:700;text-transform:uppercase;font-size:12px;letter-spacing:0.08em;">YourNews</p>
          <h1 style="margin:0 0 8px 0;">{escape(subject)}</h1>
          <p style="color:#64748b;">Created: {escape(created_at.isoformat())}</p>
          {recipient}
          <ul style="margin:24px 0 0 0;padding:0;">{''.join(items)}</ul>
        </main>
      </body>
    </html>
    """.strip()
