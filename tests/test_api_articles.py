from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.digest import Digest
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference


def _setup_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def test_get_articles_returns_inserted_articles() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Source A", url="https://example.com/a", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        session.add(Article(source_id=source.id, title="One", url="https://example.com/1", content="Body", published_at=None))
        session.commit()

    response = client.get("/articles")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "One"


def test_get_articles_respects_limit() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Source A", url="https://example.com/a", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        for i in range(5):
            session.add(Article(source_id=source.id, title=f"Article {i}", url=f"https://example.com/{i}", content=None, published_at=None))
        session.commit()

    response = client.get("/articles", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_articles_includes_source_name() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="BBC World", url="https://feeds.bbci.co.uk/news/world/rss.xml", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        session.add(
            Article(
                source_id=source.id,
                title="Headline",
                url="https://example.com/headline",
                content=None,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.get("/articles")
    assert response.status_code == 200
    assert response.json()[0]["source_name"] == "BBC World"


def test_get_articles_includes_topics_and_empty_topics() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Topic Source", url="https://example.com/topics", source_type="rss", enabled=True)
        session.add(source)
        session.flush()

        with_topics = Article(source_id=source.id, title="With Topics", url="https://example.com/with-topics", content=None, published_at=None)
        no_topics = Article(source_id=source.id, title="No Topics", url="https://example.com/no-topics", content=None, published_at=None)
        session.add_all([with_topics, no_topics])
        session.flush()

        ai_topic = Topic(name="ai")
        session.add(ai_topic)
        session.flush()
        session.add(ArticleTopic(article_id=with_topics.id, topic_id=ai_topic.id, relevance_score=3))
        session.commit()

    response = client.get("/articles", params={"limit": 10})
    assert response.status_code == 200
    by_title = {item["title"]: item for item in response.json()}
    assert by_title["With Topics"]["topics"] == ["ai"]
    assert by_title["No Topics"]["topics"] == []


def test_get_sources_returns_article_sources() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        session.add_all(
            [
                ArticleSource(name="B", url="https://example.com/b", source_type="rss", enabled=False),
                ArticleSource(name="A", url="https://example.com/a", source_type="rss", enabled=True),
            ]
        )
        session.commit()

    response = client.get("/sources")
    assert response.status_code == 200
    data = response.json()
    assert [item["name"] for item in data] == ["A", "B"]


def test_digest_preview_returns_latest_articles_with_rank_and_source_name() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Preview Source", url="https://example.com/source", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        session.add_all(
            [
                Article(source_id=source.id, title="Older", url="https://example.com/older", content=None, published_at=None),
                Article(source_id=source.id, title="Newer", url="https://example.com/newer", content=None, published_at=None),
            ]
        )
        session.commit()

    response = client.get("/digest/preview")
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) == 2
    assert data[0]["rank"] == 1
    assert data[1]["rank"] == 2
    assert data[0]["source_name"] == "Preview Source"


def test_digest_preview_includes_topics() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Preview Source", url="https://example.com/preview-topics", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        article = Article(source_id=source.id, title="Topic Story", url="https://example.com/topic-story", content=None, published_at=None)
        session.add(article)
        session.flush()

        topic = Topic(name="business")
        session.add(topic)
        session.flush()
        session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=4))
        session.commit()

    response = client.get("/digest/preview")
    assert response.status_code == 200
    assert response.json()["items"][0]["topics"] == ["business"]


def test_digest_preview_returns_ranked_results_not_only_newest() -> None:
    client, SessionLocal = _setup_client()
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    with SessionLocal() as session:
        source = ArticleSource(name="Ranking Source", url="https://example.com/ranking", source_type="rss", enabled=True)
        session.add(source)
        session.flush()

        newest_general = Article(
            source_id=source.id,
            title="Newest General",
            url="https://example.com/newest-general",
            content=None,
            published_at=None,
            created_at=now,
        )
        older_ai = Article(
            source_id=source.id,
            title="Older AI",
            url="https://example.com/older-ai",
            content=None,
            published_at=None,
            created_at=now.replace(day=6),
        )
        session.add_all([newest_general, older_ai])
        session.flush()

        ai_topic = Topic(name="ai")
        session.add(ai_topic)
        session.flush()
        session.add(ArticleTopic(article_id=older_ai.id, topic_id=ai_topic.id, relevance_score=5))
        session.commit()

    response = client.get("/digest/preview", params={"limit": 2})
    assert response.status_code == 200
    data = response.json()["items"]
    assert [item["title"] for item in data] == ["Older AI", "Newest General"]
    assert data[0]["topics"] == ["ai"]
    assert data[1]["topics"] == []


def test_digest_preview_respects_limit_and_does_not_create_digest_rows() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        source = ArticleSource(name="Preview Source", url="https://example.com/source", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        for i in range(6):
            session.add(Article(source_id=source.id, title=f"Article {i}", url=f"https://example.com/d-{i}", content=None, published_at=None))
        session.commit()

    response = client.get("/digest/preview", params={"limit": 3})
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) == 3
    assert [item["rank"] for item in data] == [1, 2, 3]

    with SessionLocal() as session:
        assert len(session.query(Digest).all()) == 0


def test_digest_preview_with_user_id_uses_personalized_preferences() -> None:
    client, SessionLocal = _setup_client()
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    with SessionLocal() as session:
        source = ArticleSource(name="Personal Source", url="https://example.com/personal-source", source_type="rss", enabled=True)
        session.add(source)
        session.flush()

        ai = Article(
            source_id=source.id,
            title="AI Story",
            url="https://example.com/api-ai-story",
            content=None,
            published_at=None,
            created_at=now,
        )
        business = Article(
            source_id=source.id,
            title="Business Story",
            url="https://example.com/api-business-story",
            content=None,
            published_at=None,
            created_at=now.replace(hour=23),
        )
        session.add_all([ai, business])
        session.flush()

        ai_topic = Topic(name="ai")
        business_topic = Topic(name="business")
        user = User(email="digest@example.com")
        session.add_all([ai_topic, business_topic, user])
        session.flush()
        session.add_all(
            [
                ArticleTopic(article_id=ai.id, topic_id=ai_topic.id, relevance_score=5),
                ArticleTopic(article_id=business.id, topic_id=business_topic.id, relevance_score=5),
                UserPreference(user_id=user.id, topic_id=business_topic.id, weight=5),
            ]
        )
        user_id = user.id
        session.commit()

    response = client.get("/digest/preview", params={"limit": 2, "user_id": user_id})
    assert response.status_code == 200
    data = response.json()["items"]
    assert [item["title"] for item in data] == ["Business Story", "AI Story"]


def test_digest_preview_unknown_user_id_returns_404() -> None:
    client, _ = _setup_client()

    response = client.get("/digest/preview", params={"user_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
