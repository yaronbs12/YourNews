from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.digests.service import DigestUserNotFoundError, EmptyDigestError, generate_digest_for_user
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest, DigestItem
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference

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


def _add_source(session: Session, name: str = "Digest Source") -> ArticleSource:
    source = ArticleSource(
        name=name,
        url=f"https://example.com/{name.lower().replace(' ', '-')}",
        source_type="rss",
        enabled=True,
    )
    session.add(source)
    session.flush()
    return source


def _add_user(session: Session, email: str = "digest-user@example.com") -> User:
    user = User(email=email)
    session.add(user)
    session.flush()
    return user


def _add_article(
    session: Session,
    source: ArticleSource,
    title: str,
    created_at: datetime,
    topic_names: list[str],
) -> Article:
    article = Article(
        source_id=source.id,
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        content=None,
        published_at=None,
        created_at=created_at,
    )
    session.add(article)
    session.flush()
    for topic_name in topic_names:
        topic = session.query(Topic).filter_by(name=topic_name).one_or_none()
        if topic is None:
            topic = Topic(name=topic_name)
            session.add(topic)
            session.flush()
        session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=1))
    return article


def _set_preference(session: Session, user: User, topic_name: str, weight: int) -> None:
    topic = session.query(Topic).filter_by(name=topic_name).one()
    session.add(UserPreference(user_id=user.id, topic_id=topic.id, weight=weight))


def test_generate_digest_for_valid_user_persists_digest_and_items() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session)
        source = _add_source(session)
        article = _add_article(session, source, "AI Story", NOW, ["ai"])
        session.commit()

        digest = generate_digest_for_user(session, user_id=user.id, limit=10)

        assert digest.user_id == user.id
        items = session.scalars(select(DigestItem).where(DigestItem.digest_id == digest.id)).all()
        assert len(items) == 1
        assert items[0].article_id == article.id
        assert items[0].rank == 1


def test_generate_digest_preserves_ranked_order() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session, "ordered@example.com")
        source = _add_source(session)
        general = _add_article(session, source, "General Story", NOW, ["general"])
        ai = _add_article(session, source, "AI Story", NOW - timedelta(hours=1), ["ai"])
        business = _add_article(session, source, "Business Story", NOW - timedelta(hours=2), ["business"])
        _set_preference(session, user, "business", 5)
        session.commit()

        digest = generate_digest_for_user(session, user_id=user.id, limit=3)

        rows = session.scalars(
            select(DigestItem).where(DigestItem.digest_id == digest.id).order_by(DigestItem.rank.asc())
        ).all()
        assert [(item.article_id, item.rank) for item in rows] == [
            (business.id, 1),
            (ai.id, 2),
            (general.id, 3),
        ]


def test_generate_digest_unknown_user_raises_clear_error() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        with pytest.raises(DigestUserNotFoundError, match="User not found"):
            generate_digest_for_user(session, user_id=999)


def test_generate_digest_empty_article_set_does_not_create_digest() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session, "empty@example.com")
        session.commit()

        with pytest.raises(EmptyDigestError, match="No ranked articles"):
            generate_digest_for_user(session, user_id=user.id)

        assert session.scalars(select(Digest)).all() == []


def test_generate_digest_api_unknown_user_returns_404() -> None:
    client, _SessionLocal = _client_and_sessionmaker()

    response = client.post("/digests/generate", params={"user_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_generate_digest_api_empty_article_set_returns_409() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session, "api-empty@example.com")
        user_id = user.id
        session.commit()

    response = client.post("/digests/generate", params={"user_id": user_id})

    assert response.status_code == 409
    assert response.json()["detail"] == "No ranked articles available for digest"


def test_list_digests_by_user() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session, "list@example.com")
        other_user = _add_user(session, "other@example.com")
        source = _add_source(session)
        _add_article(session, source, "AI Story", NOW, ["ai"])
        user_id = user.id
        other_user_id = other_user.id
        session.commit()
        generate_digest_for_user(session, user_id=user_id, limit=1)
        generate_digest_for_user(session, user_id=user_id, limit=1)
        generate_digest_for_user(session, user_id=other_user_id, limit=1)

    response = client.get(f"/users/{user_id}/digests")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["user_id"] == user_id for item in data)
    assert all(item["item_count"] == 1 for item in data)


def test_get_digest_returns_ordered_items_with_article_details() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        user = _add_user(session, "read@example.com")
        source = _add_source(session, "Read Source")
        _add_article(session, source, "General Story", NOW, ["general"])
        _add_article(session, source, "AI Story", NOW - timedelta(hours=1), ["ai"])
        user_id = user.id
        session.commit()
        digest = generate_digest_for_user(session, user_id=user_id, limit=2)
        digest_id = digest.id

    response = client.get(f"/digests/{digest_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == digest_id
    assert data["user_id"] == user_id
    assert [item["rank"] for item in data["items"]] == [1, 2]
    assert [item["title"] for item in data["items"]] == ["AI Story", "General Story"]
    assert data["items"][0]["url"] == "https://example.com/ai-story"
    assert data["items"][0]["source_name"] == "Read Source"
    assert data["items"][0]["topics"] == ["ai"]
