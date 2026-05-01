from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.schemas import NormalizedArticle
from app.ingestion.service import ingest_rss_feed
from app.models import *  # noqa: F403,F401
from app.models.article import Article


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
