from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.db import get_or_create_article_source, insert_new_articles
from app.ingestion.schemas import NormalizedArticle
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource


def test_insert_new_articles_skips_duplicate_urls() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    article = NormalizedArticle(
        title="Launch",
        url="https://example.com/news/launch",
        content="Summary",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        source="Example Feed",
        source_url="https://example.com/rss.xml",
    )

    with SessionLocal() as session:
        first_insert = insert_new_articles(session, [article, article])
        session.commit()

        second_insert = insert_new_articles(session, [article])
        session.commit()

        assert len(first_insert) == 1
        assert second_insert == []
        assert len(session.scalars(select(Article)).all()) == 1
        sources = session.scalars(select(ArticleSource)).all()
        assert len(sources) == 1
        assert sources[0].source_type == "rss"
        assert sources[0].enabled is True
        assert sources[0].last_fetched_at is None


def test_get_or_create_article_source_prefers_existing_url() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        existing = ArticleSource(name="Hacker News Newest", url="https://hnrss.org/newest", source_type="rss", enabled=True)
        session.add(existing)
        session.commit()

        result = get_or_create_article_source(session, name="Hacker News: Newest", url="https://hnrss.org/newest")
        session.commit()

        assert result.id == existing.id
        assert len(session.scalars(select(ArticleSource)).all()) == 1


def test_insert_new_articles_reuses_existing_source_by_url() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    article_one = NormalizedArticle(
        title="One",
        url="https://example.com/news/one",
        content=None,
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        source="Hacker News Newest",
        source_url="https://hnrss.org/newest",
    )
    article_two = NormalizedArticle(
        title="Two",
        url="https://example.com/news/two",
        content=None,
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        source="Hacker News: Newest",
        source_url="https://hnrss.org/newest",
    )

    with SessionLocal() as session:
        inserted = insert_new_articles(session, [article_one, article_two])
        session.commit()

        sources = session.scalars(select(ArticleSource)).all()
        articles = session.scalars(select(Article)).all()
        assert len(inserted) == 2
        assert len(sources) == 1
        assert len(articles) == 2
        assert articles[0].source_id == sources[0].id
        assert articles[1].source_id == sources[0].id
