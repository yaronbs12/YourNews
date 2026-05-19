from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.delivery.service import render_digest_delivery_preview
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest, DigestDelivery, DigestItem
from app.models.feedback import Feedback
from app.models.topic import Topic
from app.models.user_preference import UserPreference
from app.models.user import User

NOW = datetime(2026, 5, 7, tzinfo=timezone.utc)


def _sessionmaker() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _client_and_sessionmaker() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _create_digest_fixture(session: Session) -> Digest:
    user = User(email="reader@example.com")
    source = ArticleSource(
        name="Example Source",
        url="https://example.com/feed",
        source_type="rss",
        category="technology",
        enabled=True,
    )
    session.add_all([user, source])
    session.flush()
    article_one = Article(
        source_id=source.id,
        title="AI Story",
        url="https://example.com/ai",
        content=None,
        published_at=None,
        created_at=NOW,
    )
    article_two = Article(
        source_id=source.id,
        title="Security Story",
        url="https://example.com/security",
        content=None,
        published_at=None,
        created_at=NOW,
    )
    session.add_all([article_one, article_two])
    session.flush()
    ai = Topic(name="ai")
    cybersecurity = Topic(name="cybersecurity")
    session.add_all([ai, cybersecurity])
    session.flush()
    digest = Digest(user_id=user.id, created_at=NOW)
    session.add(digest)
    session.flush()
    session.add_all(
        [
            ArticleTopic(article_id=article_one.id, topic_id=ai.id, relevance_score=1),
            ArticleTopic(article_id=article_two.id, topic_id=cybersecurity.id, relevance_score=1),
            DigestItem(digest_id=digest.id, article_id=article_one.id, rank=1),
            DigestItem(digest_id=digest.id, article_id=article_two.id, rank=2),
        ]
    )
    session.commit()
    return digest


def test_render_digest_delivery_preview_outputs_text_and_html() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)

        preview = render_digest_delivery_preview(session, digest.id)

        assert preview.subject == f"YourNews digest #{digest.id}"
        assert preview.user_email == "reader@example.com"
        assert preview.digest_id == digest.id
        assert "1. AI Story" in preview.text_body
        assert "Source: Example Source" in preview.text_body
        assert "Topics: ai" in preview.text_body
        assert "URL: https://example.com/ai" in preview.text_body
        assert "#1 · Example Source" in preview.html_body
        assert "AI Story" in preview.html_body
        assert "https://example.com/ai" in preview.html_body


def test_delivery_preview_endpoint_returns_rendered_digest() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id

    response = client.get(f"/digests/{digest_id}/delivery-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == f"YourNews digest #{digest_id}"
    assert payload["user_email"] == "reader@example.com"
    assert payload["digest_id"] == digest_id
    assert "1. AI Story" in payload["text_body"]
    assert "<html>" in payload["html_body"]


def test_delivery_preview_endpoint_returns_404_for_unknown_digest() -> None:
    client, _SessionLocal = _client_and_sessionmaker()

    response = client.get("/digests/999/delivery-preview")

    assert response.status_code == 404
    assert response.json()["detail"] == "Digest not found"


def test_send_digest_creates_local_email_delivery_with_feedback_links() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id
        article_ids = session.scalars(
            select(DigestItem.article_id).where(DigestItem.digest_id == digest_id).order_by(DigestItem.rank.asc())
        ).all()

    response = client.post(f"/digests/{digest_id}/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["digest_id"] == digest_id
    assert payload["channel"] == "email"
    assert payload["provider"] == "local"
    assert payload["recipient_email"] == "reader@example.com"
    assert payload["status"] == "SENT"
    assert payload["sent_at"] is not None
    assert payload["feedback_token"]
    assert "local/dev email simulation" in payload["text_body"]
    assert "Local/dev email simulation" in payload["html_body"]
    for article_id in article_ids:
        for label in ["INTERESTING", "NEUTRAL", "NOT_INTERESTING"]:
            expected = f"/feedback/click?delivery_id={payload['id']}&article_id={article_id}&label={label}"
            assert expected in payload["text_body"]
            assert expected.replace("&", "&amp;") in payload["html_body"]

    with SessionLocal() as session:
        deliveries = session.scalars(select(DigestDelivery).where(DigestDelivery.digest_id == digest_id)).all()
        assert len(deliveries) == 1
        assert deliveries[0].channel == "email"
        assert deliveries[0].provider == "local"
        assert deliveries[0].status.name == "SENT"


def test_digest_delivery_history_and_detail_endpoints_return_delivery_records() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id

    send_response = client.post(f"/digests/{digest_id}/send")
    delivery_id = send_response.json()["id"]

    history_response = client.get(f"/digests/{digest_id}/deliveries")
    detail_response = client.get(f"/deliveries/{delivery_id}")

    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["id"] == delivery_id
    assert history[0]["status"] == "SENT"
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == delivery_id
    assert detail["html_body"] == history[0]["html_body"]
    assert detail["text_body"] == history[0]["text_body"]


def test_feedback_click_with_valid_token_creates_feedback_and_updates_preferences() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id
        article_id = session.scalar(
            select(DigestItem.article_id).where(DigestItem.digest_id == digest_id, DigestItem.rank == 1)
        )

    delivery = client.post(f"/digests/{digest_id}/send").json()
    response = client.get(
        "/feedback/click",
        params={
            "delivery_id": delivery["id"],
            "article_id": article_id,
            "label": "INTERESTING",
            "token": delivery["feedback_token"],
        },
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "YourNews" in response.text
    assert "Feedback saved" in response.text
    assert "AI Story" in response.text
    assert "Future YourNews digests" in response.text
    with SessionLocal() as session:
        feedback_rows = session.scalars(select(Feedback).where(Feedback.article_id == article_id)).all()
        assert len(feedback_rows) == 1
        assert feedback_rows[0].label.name == "INTERESTING"
        preference = session.scalar(select(UserPreference).join(Topic).where(Topic.name == "ai"))
        assert preference is not None
        assert preference.weight == 2


def test_feedback_click_rejects_invalid_token() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id
        article_id = session.scalar(select(DigestItem.article_id).where(DigestItem.digest_id == digest_id))

    delivery = client.post(f"/digests/{digest_id}/send").json()
    response = client.get(
        "/feedback/click",
        params={
            "delivery_id": delivery["id"],
            "article_id": article_id,
            "label": "INTERESTING",
            "token": "wrong-token",
        },
    )

    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "Invalid feedback token" in response.text


def test_feedback_click_rejects_article_not_in_digest() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id
        source = session.scalar(select(ArticleSource))
        other_article = Article(
            source_id=source.id,
            title="Outside Story",
            url="https://example.com/outside",
            content=None,
            published_at=None,
            created_at=NOW,
        )
        session.add(other_article)
        session.commit()
        other_article_id = other_article.id

    delivery = client.post(f"/digests/{digest_id}/send").json()
    response = client.get(
        "/feedback/click",
        params={
            "delivery_id": delivery["id"],
            "article_id": other_article_id,
            "label": "INTERESTING",
            "token": delivery["feedback_token"],
        },
    )

    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert "not part of the delivered digest" in response.text


def test_feedback_click_rejects_invalid_label() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id
        article_id = session.scalar(select(DigestItem.article_id).where(DigestItem.digest_id == digest_id))

    delivery = client.post(f"/digests/{digest_id}/send").json()
    response = client.get(
        "/feedback/click",
        params={
            "delivery_id": delivery["id"],
            "article_id": article_id,
            "label": "VERY_GOOD",
            "token": delivery["feedback_token"],
        },
    )

    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert "Invalid feedback label" in response.text


def test_send_digest_smtp_missing_config_fails_gracefully() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id

    with patch("app.delivery.service.settings.email_provider", "smtp"), patch(
        "app.delivery.service.settings.smtp_host", None
    ):
        response = client.post(f"/digests/{digest_id}/send")

    assert response.status_code == 502
    assert "Missing SMTP config" in response.json()["detail"]
    with SessionLocal() as session:
        delivery = session.scalar(select(DigestDelivery).where(DigestDelivery.digest_id == digest_id))
        assert delivery is not None
        assert delivery.provider == "smtp"
        assert delivery.status.name == "FAILED"


def test_send_digest_smtp_success_path_uses_mocked_smtp() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id

    with patch("app.delivery.service.settings.email_provider", "smtp"), patch(
        "app.delivery.service.settings.smtp_host", "smtp.example.com"
    ), patch("app.delivery.service.settings.smtp_port", 587), patch(
        "app.delivery.service.settings.smtp_username", "user"
    ), patch(
        "app.delivery.service.settings.smtp_password", "pass"
    ), patch(
        "app.delivery.service.settings.smtp_from_email", "no-reply@example.com"
    ), patch(
        "app.delivery.service.settings.app_base_url", "https://demo.yournews.dev"
    ), patch("app.delivery.service.smtplib.SMTP") as smtp_cls:
        response = client.post(f"/digests/{digest_id}/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "smtp"
    assert payload["status"] == "SENT"
    assert "https://demo.yournews.dev/feedback/click" in payload["text_body"]
    assert "https://demo.yournews.dev/feedback/click" in payload["html_body"]
    smtp_cls.assert_called_once()


def test_send_digest_smtp_failure_path_is_persisted() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        digest = _create_digest_fixture(session)
        digest_id = digest.id

    with patch("app.delivery.service.settings.email_provider", "smtp"), patch(
        "app.delivery.service.settings.smtp_host", "smtp.example.com"
    ), patch("app.delivery.service.settings.smtp_port", 587), patch(
        "app.delivery.service.settings.smtp_username", "user"
    ), patch(
        "app.delivery.service.settings.smtp_password", "pass"
    ), patch(
        "app.delivery.service.settings.smtp_from_email", "no-reply@example.com"
    ), patch("app.delivery.service.smtplib.SMTP", side_effect=RuntimeError("boom")):
        response = client.post(f"/digests/{digest_id}/send")

    assert response.status_code == 502
    assert "SMTP send failed" in response.json()["detail"]
    with SessionLocal() as session:
        delivery = session.scalar(select(DigestDelivery).where(DigestDelivery.digest_id == digest_id))
        assert delivery is not None
        assert delivery.status.name == "FAILED"
        assert delivery.error_message is not None
