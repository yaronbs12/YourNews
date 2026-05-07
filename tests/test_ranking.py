from datetime import datetime, timedelta, timezone

import pytest
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
from app.ranking.service import RankingUserNotFoundError, rank_articles_for_digest

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


def test_rank_articles_for_digest_without_user_id_uses_static_ranking() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Newest General", NOW, ["general"])
        _add_article(session, source, "Older AI", NOW - timedelta(days=1), ["ai"])
        _add_article(session, source, "Older Tech", NOW - timedelta(days=2), ["tech"])
        session.commit()

        ranked = rank_articles_for_digest(session, limit=3)

        assert [item.article.title for item in ranked] == ["Older AI", "Older Tech", "Newest General"]
        assert [item.score for item in ranked] == [3, 2, 0]


def test_rank_articles_for_digest_with_positive_user_preference_increases_rank() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Static Winner AI", NOW, ["ai"])
        _add_article(session, source, "Preferred Business", NOW - timedelta(hours=1), ["business"])
        user = _add_user(session, "positive-ranking@example.com")
        _set_preference(session, user, "business", 5)
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Preferred Business", "Static Winner AI"]
        assert [item.score for item in ranked] == [6, 3]


def test_rank_articles_for_digest_with_negative_user_preference_lowers_rank() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Disliked AI", NOW, ["ai"])
        _add_article(session, source, "Neutral Tech", NOW - timedelta(hours=1), ["tech"])
        user = _add_user(session, "negative-ranking@example.com")
        _set_preference(session, user, "ai", -4)
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Neutral Tech", "Disliked AI"]
        assert [item.score for item in ranked] == [2, -1]


def test_rank_articles_for_digest_combines_static_and_user_preference_scores() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Multi Topic Match", NOW, ["ai", "business"])
        user = _add_user(session, "combined-ranking@example.com")
        _set_preference(session, user, "business", 5)
        session.commit()

        ranked = rank_articles_for_digest(session, limit=1, user_id=user.id)

        assert ranked[0].article.title == "Multi Topic Match"
        assert ranked[0].topics == ["ai", "business"]
        assert ranked[0].score == 9


def test_rank_articles_for_digest_uses_created_at_desc_as_tiebreaker() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Older AI", NOW - timedelta(hours=1), ["ai"])
        _add_article(session, source, "Newer AI", NOW, ["ai"])
        user = _add_user(session, "tie-ranking@example.com")
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Newer AI", "Older AI"]
        assert [item.score for item in ranked] == [3, 3]


def test_rank_articles_for_digest_unknown_user_id_raises_ranking_error() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        with pytest.raises(RankingUserNotFoundError, match="User not found"):
            rank_articles_for_digest(session, limit=10, user_id=999)


def test_digest_preview_without_user_id_still_returns_ranked_response_format() -> None:
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
    assert {"rank", "article_id", "title", "url", "source_name", "topics"}.issubset(items[0].keys())
    assert items[0]["rank"] == 1
    assert items[0]["source_name"] == "Digest Source"
    assert items[0]["topics"] == ["ai"]


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
    assert [item["title"] for item in personalized_response.json()["items"]] == [
        "Digest Preferred Business",
        "Digest AI Winner Without User",
    ]


def test_digest_preview_unknown_user_id_returns_404() -> None:
    client, _ = _client_and_sessionmaker()

    response = client.get("/digest/preview", params={"user_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
