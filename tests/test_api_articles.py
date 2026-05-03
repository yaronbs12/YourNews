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
