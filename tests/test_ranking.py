from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference

NOW = datetime(2026, 5, 7, tzinfo=timezone.utc)


def _client_and_sessionmaker() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _add_source(session: Session, name: str = "Ranking Source") -> ArticleSource:
    source = ArticleSource(
        name=name,
        url=f"https://example.com/{name.lower().replace(' ', '-')}/rss",
        source_type="rss",
        enabled=True,
    )
    session.add(source)
    session.flush()
    return source


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

    for name in topic_names:
        topic = session.query(Topic).filter_by(name=name).one_or_none()
        if topic is None:
            topic = Topic(name=name)
            session.add(topic)
            session.flush()
        session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=1))

    return article


def _add_user(session: Session, email: str = "reader@example.com") -> User:
    user = User(email=email)
    session.add(user)
    session.flush()
    return user


def _set_preference(session: Session, user: User, topic_name: str, weight: int) -> None:
    topic = session.query(Topic).filter_by(name=topic_name).one()
    session.add(UserPreference(user_id=user.id, topic_id=topic.id, weight=weight))


def test_digest_preview_without_user_id_returns_score_breakdown() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session, "Digest Source")
        _add_article(session, source, "Digest General", NOW, ["general"])
        _add_article(session, source, "Digest AI", NOW - timedelta(hours=1), ["ai"])
        session.commit()

    response = client.get("/digest/preview", params={"limit": 2})

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["title"] for item in items] == ["Digest AI", "Digest General"]
    assert items[0]["rank"] == 1
    assert items[0]["source_name"] == "Digest Source"
    assert items[0]["topics"] == ["ai"]
    assert items[0]["score"] == 5
    assert items[0]["score_breakdown"] == {
        "total_score": 5,
        "topic_score": 3,
        "preference_score": 0,
        "freshness_score": 2,
        "source_penalty": 0,
    }
    assert items[1]["score_breakdown"]["source_penalty"] == 1


def test_digest_preview_with_user_id_changes_order_based_on_preferences() -> None:
    client, SessionLocal = _client_and_sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session, "Personal Digest Source")
        _add_article(session, source, "Digest AI Winner Without User", NOW, ["ai"])
        _add_article(session, source, "Digest Preferred Business", NOW - timedelta(hours=1), ["business"])
        user = _add_user(session, "personal-digest@example.com")
        _set_preference(session, user, "business", 5)
        user_id = user.id
        session.commit()

    static_response = client.get("/digest/preview", params={"limit": 2})
    personalized_response = client.get("/digest/preview", params={"limit": 2, "user_id": user_id})

    assert static_response.status_code == 200
    assert personalized_response.status_code == 200
    assert [item["title"] for item in static_response.json()["items"]] == [
        "Digest AI Winner Without User",
        "Digest Preferred Business",
    ]
    personalized_items = personalized_response.json()["items"]
    assert [item["title"] for item in personalized_items] == [
        "Digest Preferred Business",
        "Digest AI Winner Without User",
    ]
    assert personalized_items[0]["score_breakdown"]["preference_score"] == 5


def test_digest_preview_unknown_user_id_returns_404() -> None:
    client, _ = _client_and_sessionmaker()

    response = client.get("/digest/preview", params={"user_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
