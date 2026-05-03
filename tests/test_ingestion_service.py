from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.schemas import NormalizedArticle
from app.ingestion.service import ingest_enabled_rss_sources, ingest_rss_feed
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource


def test_ingest_rss_feed_fetches_inserts_commits_and_returns_count() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    articles = [
        NormalizedArticle(
            title="First",
            url="https://example.com/first",
            content="Summary",
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
            source="Example Feed",
            source_url="https://example.com/rss.xml",
        ),
        NormalizedArticle(
            title="Second",
            url="https://example.com/second",
            content=None,
            published_at=None,
            source="Example Feed",
            source_url="https://example.com/rss.xml",
        ),
    ]

    with SessionLocal() as session:
        with patch("app.ingestion.service.fetch_rss_articles", return_value=articles) as fetcher:
            inserted_count = ingest_rss_feed(session, "https://example.com/rss.xml")

        assert inserted_count == 2
        fetcher.assert_called_once_with("https://example.com/rss.xml")
        assert len(session.scalars(select(Article)).all()) == 2


def test_ingest_rss_feed_rolls_back_on_error() -> None:
    session = Mock()

    with patch("app.ingestion.service.fetch_rss_articles", side_effect=RuntimeError("feed failed")):
        with pytest.raises(RuntimeError, match="feed failed"):
            ingest_rss_feed(session, "https://example.com/rss.xml")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_ingest_enabled_rss_sources_only_ingests_enabled_rss_and_updates_last_fetched() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        enabled_rss = ArticleSource(name="Enabled RSS", url="https://example.com/rss.xml", source_type="rss", enabled=True)
        disabled_rss = ArticleSource(name="Disabled RSS", url="https://example.com/disabled.xml", source_type="rss", enabled=False)
        api_source = ArticleSource(name="API Source", url="https://example.com/api", source_type="api", enabled=True)
        session.add_all([enabled_rss, disabled_rss, api_source])
        session.commit()

        articles = [
            NormalizedArticle(
                title="Enabled Story",
                url="https://example.com/enabled-story",
                content=None,
                published_at=None,
                source="Enabled RSS",
                source_url="https://example.com/rss.xml",
            )
        ]
        with patch("app.ingestion.service.fetch_rss_articles", return_value=articles) as fetcher:
            result = ingest_enabled_rss_sources(session)

        assert result == {"Enabled RSS": 1}
        fetcher.assert_called_once_with("https://example.com/rss.xml")

        updated_enabled = session.scalar(select(ArticleSource).where(ArticleSource.name == "Enabled RSS"))
        updated_disabled = session.scalar(select(ArticleSource).where(ArticleSource.name == "Disabled RSS"))
        assert updated_enabled is not None and updated_enabled.last_fetched_at is not None
        assert updated_disabled is not None and updated_disabled.last_fetched_at is None


def test_ingest_enabled_rss_sources_continues_after_failure() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        first = ArticleSource(name="First RSS", url="https://example.com/first.xml", source_type="rss", enabled=True)
        second = ArticleSource(name="Second RSS", url="https://example.com/second.xml", source_type="rss", enabled=True)
        session.add_all([first, second])
        session.commit()

        def _fetch(url: str) -> list[NormalizedArticle]:
            if url.endswith("first.xml"):
                raise RuntimeError("boom")
            return [
                NormalizedArticle(
                    title="Second Story",
                    url="https://example.com/second-story",
                    content=None,
                    published_at=None,
                    source="Second RSS",
                    source_url="https://example.com/second.xml",
                )
            ]

        with patch("app.ingestion.service.fetch_rss_articles", side_effect=_fetch):
            result = ingest_enabled_rss_sources(session)

        assert result == {"First RSS": 0, "Second RSS": 1}
