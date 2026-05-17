from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
from app.models.digest import Digest, DigestItem
from app.models.topic import Topic
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
