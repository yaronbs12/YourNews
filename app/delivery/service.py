from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from email.message import EmailMessage
import smtplib
from secrets import token_urlsafe
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest, DigestDelivery, DigestDeliveryStatus, DigestItem
from app.models.topic import Topic
from app.models.user import User

FEEDBACK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("INTERESTING", "Interesting"),
    ("NEUTRAL", "Neutral"),
    ("NOT_INTERESTING", "Not interesting"),
)


class DeliveryPreviewNotFoundError(LookupError):
    pass


class DigestDeliveryNotFoundError(LookupError):
    pass


class EmailDeliveryConfigurationError(ValueError):
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
    rows = _digest_article_rows(session, digest.id)
    subject = _digest_subject(digest.id)
    text_body = _render_text_body(
        subject=subject,
        created_at=digest.created_at,
        rows=rows,
        session=session,
        email=user.email if user else None,
        feedback_context=None,
    )
    html_body = _render_html_body(
        subject=subject,
        created_at=digest.created_at,
        rows=rows,
        session=session,
        email=user.email if user else None,
        feedback_context=None,
    )
    return DeliveryPreview(
        subject=subject,
        user_email=user.email if user else None,
        digest_id=digest.id,
        created_at=digest.created_at,
        html_body=html_body,
        text_body=text_body,
    )


def send_digest_email(session: Session, digest_id: int) -> DigestDelivery:
    digest = session.get(Digest, digest_id)
    if digest is None:
        raise DigestDeliveryNotFoundError("Digest not found")

    user = session.get(User, digest.user_id)
    subject = _digest_subject(digest.id)
    provider = settings.email_provider.lower()
    delivery = DigestDelivery(
        digest_id=digest.id,
        user_id=digest.user_id,
        channel="email",
        provider=provider,
        recipient_email=user.email if user else None,
        subject=subject,
        html_body="",
        text_body="",
        status=DigestDeliveryStatus.PENDING,
        feedback_token=token_urlsafe(24),
    )
    session.add(delivery)
    session.flush()

    rows = _digest_article_rows(session, digest.id)
    feedback_context = FeedbackLinkContext(delivery_id=delivery.id, token=delivery.feedback_token)
    delivery.text_body = _render_text_body(
        subject=subject,
        created_at=digest.created_at,
        rows=rows,
        session=session,
        email=user.email if user else None,
        feedback_context=feedback_context,
        provider=provider,
    )
    delivery.html_body = _render_html_body(
        subject=subject,
        created_at=digest.created_at,
        rows=rows,
        session=session,
        email=user.email if user else None,
        feedback_context=feedback_context,
        provider=provider,
    )
    if provider == "local":
        delivery.status = DigestDeliveryStatus.SENT
        delivery.sent_at = datetime.now(UTC)
    elif provider == "smtp":
        try:
            _send_via_smtp(delivery)
            delivery.status = DigestDeliveryStatus.SENT
            delivery.sent_at = datetime.now(UTC)
        except EmailDeliveryConfigurationError as exc:
            delivery.status = DigestDeliveryStatus.FAILED
            delivery.error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            delivery.status = DigestDeliveryStatus.FAILED
            delivery.error_message = f"SMTP send failed: {exc}"
    else:
        delivery.status = DigestDeliveryStatus.FAILED
        delivery.error_message = f"Unsupported email provider: {settings.email_provider}"
    session.commit()
    session.refresh(delivery)
    return delivery


def list_digest_deliveries(session: Session, digest_id: int) -> list[DigestDelivery]:
    if session.get(Digest, digest_id) is None:
        raise DigestDeliveryNotFoundError("Digest not found")
    return session.scalars(
        select(DigestDelivery)
        .where(DigestDelivery.digest_id == digest_id)
        .order_by(DigestDelivery.created_at.desc(), DigestDelivery.id.desc())
    ).all()


def get_delivery(session: Session, delivery_id: int) -> DigestDelivery:
    delivery = session.get(DigestDelivery, delivery_id)
    if delivery is None:
        raise DigestDeliveryNotFoundError("Delivery not found")
    return delivery


@dataclass(frozen=True)
class FeedbackLinkContext:
    delivery_id: int
    token: str


def _digest_subject(digest_id: int) -> str:
    return f"YourNews Daily Digest #{digest_id}"


def _digest_article_rows(session: Session, digest_id: int) -> list[tuple[DigestItem, Article, str]]:
    return session.execute(
        select(DigestItem, Article, ArticleSource.name)
        .join(Article, DigestItem.article_id == Article.id)
        .join(ArticleSource, Article.source_id == ArticleSource.id)
        .where(DigestItem.digest_id == digest_id)
        .order_by(DigestItem.rank.asc())
    ).all()


def _topic_names(session: Session, article_id: int) -> list[str]:
    return session.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


def _feedback_url(context: FeedbackLinkContext, article_id: int, label: str) -> str:
    base_url = settings.app_base_url.rstrip("/")
    query = urlencode(
        {
            "delivery_id": context.delivery_id,
            "article_id": article_id,
            "label": label,
            "token": context.token,
        }
    )
    return f"{base_url}/feedback/click?{query}"


def _render_text_body(
    subject: str,
    created_at: datetime,
    rows: list[tuple[DigestItem, Article, str]],
    session: Session,
    email: str | None,
    feedback_context: FeedbackLinkContext | None,
    provider: str = "local",
) -> str:
    lines = [subject, f"Created: {created_at.isoformat()}"]
    if email:
        lines.append(f"To: {email}")
    if feedback_context and provider == "local":
        lines.append("Delivery: local/dev email simulation (no external email sent)")
    lines.append("")

    for item, article, source_name in rows:
        topics = ", ".join(_topic_names(session, article.id)) or "none"
        lines.extend(
            [
                f"{item.rank}. {article.title}",
                f"   Source: {source_name}",
                f"   Topics: {topics}",
                f"   URL: {article.url}",
            ]
        )
        if feedback_context:
            lines.append("   Feedback:")
            for label, display in FEEDBACK_ACTIONS:
                lines.append(f"   - {display}: {_feedback_url(feedback_context, article.id, label)}")
        lines.append("")

    return "\n".join(lines).strip()


def _render_html_body(
    subject: str,
    created_at: datetime,
    rows: list[tuple[DigestItem, Article, str]],
    session: Session,
    email: str | None,
    feedback_context: FeedbackLinkContext | None,
    provider: str = "local",
) -> str:
    recipient = f'<p style="color:#64748b;">To: {escape(email)}</p>' if email else ""
    delivery_note = (
        '<p style="background:#fef3c7;border:1px solid #fde68a;border-radius:10px;color:#92400e;padding:10px 12px;">'
        "Local/dev email simulation — no external email was sent. Use the feedback buttons to record tracked signals."
        "</p>"
        if feedback_context and provider == "local"
        else ""
    )
    items = []
    for item, article, source_name in rows:
        topics = _topic_names(session, article.id)
        topic_html = "".join(
            f'<span style="background:#eff6ff;color:#1e40af;border-radius:999px;padding:3px 8px;margin-right:4px;font-size:12px;">{escape(topic)}</span>'
            for topic in topics
        ) or '<span style="color:#64748b;">No topics</span>'
        feedback_html = ""
        if feedback_context:
            links = []
            for label, display in FEEDBACK_ACTIONS:
                links.append(
                    f'<a href="{escape(_feedback_url(feedback_context, article.id, label))}" '
                    'style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;'
                    'border-radius:999px;padding:8px 12px;margin:4px 6px 0 0;font-size:13px;font-weight:700;">'
                    f"{escape(display)}</a>"
                )
            feedback_html = (
                '<div style="margin-top:14px;padding-top:12px;border-top:1px solid #e2e8f0;">'
                '<div style="font-size:12px;font-weight:700;color:#475569;margin-bottom:4px;">Was this useful?</div>'
                f"{''.join(links)}</div>"
            )
        items.append(
            f"""
            <li style="margin:0 0 18px 0;padding:16px;border:1px solid #dbe3ef;border-radius:12px;list-style:none;">
              <div style="font-size:12px;font-weight:700;color:#2563eb;">#{item.rank} · {escape(source_name)}</div>
              <h2 style="font-size:18px;margin:6px 0 8px 0;"><a href="{escape(article.url)}" style="color:#0f172a;text-decoration:none;">{escape(article.title)}</a></h2>
              <div style="margin:8px 0;">{topic_html}</div>
              <div style="margin:8px 0;color:#475569;font-size:13px;">Score: {item.rank}</div>
              <a href="{escape(article.url)}" style="color:#2563eb;">Read article</a>
              {feedback_html}
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
          {delivery_note}
          <ul style="margin:24px 0 0 0;padding:0;">{''.join(items)}</ul>
        </main>
      </body>
    </html>
    """.strip()


def _send_via_smtp(delivery: DigestDelivery) -> None:
    required = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise EmailDeliveryConfigurationError(f"Missing SMTP config: {', '.join(missing)}")
    if settings.smtp_port <= 0:
        raise EmailDeliveryConfigurationError("SMTP_PORT must be a positive integer")
    if not delivery.recipient_email:
        raise EmailDeliveryConfigurationError("Recipient email is required for SMTP delivery")

    message = EmailMessage()
    message["Subject"] = delivery.subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = delivery.recipient_email
    message.set_content(delivery.text_body)
    message.add_alternative(delivery.html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
