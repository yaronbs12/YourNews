from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.hacker_news import (
    HN_SOURCE_NAME,
    HN_SOURCE_URL,
    fetch_hacker_news_articles,
    fetch_hacker_news_story_ids,
    normalize_hacker_news_item,
)
from app.ingestion.schemas import NormalizedArticle
from app.ingestion.service import ingest_hacker_news_stories
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource


def _sessionmaker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_normalize_hacker_news_item_converts_story_payload() -> None:
    article = normalize_hacker_news_item(
        {
            "id": 123,
            "type": "story",
            "title": " Launch  ",
            "url": "https://Example.com/news?utm_source=hn&b=2&a=1",
            "text": " Discussion text ",
            "time": 1_772_668_800,
        }
    )

    assert article == NormalizedArticle(
        title="Launch",
        url="https://example.com/news?a=1&b=2",
        content="Discussion text",
        published_at=datetime(2026, 3, 5, tzinfo=UTC),
        source=HN_SOURCE_NAME,
        source_url=HN_SOURCE_URL,
    )


def test_normalize_hacker_news_item_uses_hn_item_url_when_external_url_missing() -> None:
    article = normalize_hacker_news_item({"id": 456, "type": "story", "title": "Ask HN", "time": 1_772_668_800})

    assert article is not None
    assert article.url == "https://news.ycombinator.com/item?id=456"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"id": 1, "type": "comment", "title": "Nope"},
        {"id": 1, "type": "story", "title": "Deleted", "deleted": True},
        {"id": 1, "type": "story", "title": "Dead", "dead": True},
        {"id": 1, "type": "story", "title": "   "},
        {"id": "1", "type": "story", "title": "Bad id"},
    ],
)
def test_normalize_hacker_news_item_skips_invalid_non_story_deleted_and_dead_items(payload) -> None:
    assert normalize_hacker_news_item(payload) is None


def test_fetch_hacker_news_articles_fetches_ids_and_items_without_live_network_calls() -> None:
    responses = [
        Mock(json=Mock(return_value=[101, "bad", 102]), raise_for_status=Mock()),
        Mock(
            json=Mock(
                return_value={
                    "id": 101,
                    "type": "story",
                    "title": "One",
                    "url": "https://example.com/one",
                }
            ),
            raise_for_status=Mock(),
        ),
        Mock(json=Mock(return_value={"id": 102, "type": "comment", "title": "Skip"}), raise_for_status=Mock()),
    ]

    with patch("app.ingestion.hacker_news.httpx.get", side_effect=responses) as get:
        articles = fetch_hacker_news_articles(story_type="new", limit=2)

    assert [article.title for article in articles] == ["One"]
    assert get.call_count == 3
    assert get.call_args_list[0].args[0].endswith("/newstories.json")


def test_fetch_hacker_news_story_ids_rejects_unknown_story_type_before_http() -> None:
    with patch("app.ingestion.hacker_news.httpx.get") as get:
        with pytest.raises(ValueError, match="Unsupported Hacker News story type"):
            fetch_hacker_news_story_ids("show")

    get.assert_not_called()


def test_ingest_hacker_news_stories_inserts_through_db_path_with_source_type() -> None:
    SessionLocal = _sessionmaker()
    articles = [
        NormalizedArticle(
            title="HN Story",
            url="https://example.com/hn-story",
            content=None,
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
            source=HN_SOURCE_NAME,
            source_url=HN_SOURCE_URL,
        )
    ]

    with SessionLocal() as session:
        with patch("app.ingestion.service.fetch_hacker_news_articles", return_value=articles) as fetcher:
            inserted_count = ingest_hacker_news_stories(session, story_type="best", limit=10)

        assert inserted_count == 1
        fetcher.assert_called_once_with(story_type="best", limit=10)
        source = session.scalar(select(ArticleSource).where(ArticleSource.name == HN_SOURCE_NAME))
        inserted_article = session.scalar(select(Article).where(Article.title == "HN Story"))
        assert source is not None
        assert source.source_type == "hacker_news"
        assert inserted_article is not None
        assert inserted_article.source_id == source.id


def test_ingest_hacker_news_stories_deduplicates_existing_urls() -> None:
    SessionLocal = _sessionmaker()
    duplicate_articles = [
        NormalizedArticle(
            title="Same",
            url="https://example.com/same",
            content=None,
            published_at=None,
            source=HN_SOURCE_NAME,
            source_url=HN_SOURCE_URL,
        ),
        NormalizedArticle(
            title="Same Again",
            url="https://example.com/same",
            content=None,
            published_at=None,
            source=HN_SOURCE_NAME,
            source_url=HN_SOURCE_URL,
        ),
    ]

    with SessionLocal() as session:
        with patch("app.ingestion.service.fetch_hacker_news_articles", return_value=duplicate_articles):
            first_count = ingest_hacker_news_stories(session)
        with patch("app.ingestion.service.fetch_hacker_news_articles", return_value=duplicate_articles):
            second_count = ingest_hacker_news_stories(session)

        assert first_count == 1
        assert second_count == 0
        assert len(session.scalars(select(Article)).all()) == 1
        assert len(session.scalars(select(ArticleSource)).all()) == 1
