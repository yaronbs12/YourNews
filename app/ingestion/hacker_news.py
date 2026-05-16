from datetime import UTC, datetime
from typing import Any

import httpx

from app.ingestion.schemas import NormalizedArticle
from app.ingestion.urls import normalize_url

HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={item_id}"
HN_SOURCE_NAME = "Hacker News"
HN_SOURCE_URL = "https://news.ycombinator.com/"
HN_STORY_TYPES = {"top", "new", "best"}


def fetch_hacker_news_articles(
    story_type: str = "top", limit: int = 30
) -> list[NormalizedArticle]:
    """Fetch and normalize Hacker News stories from the public Firebase API."""
    story_ids = fetch_hacker_news_story_ids(story_type)
    articles: list[NormalizedArticle] = []

    for story_id in story_ids[: max(limit, 0)]:
        item = fetch_hacker_news_item(story_id)
        article = normalize_hacker_news_item(item)
        if article is not None:
            articles.append(article)

    return articles


def fetch_hacker_news_story_ids(story_type: str = "top") -> list[int]:
    validated_story_type = _validate_story_type(story_type)
    response = httpx.get(
        f"{HN_API_BASE_URL}/{validated_story_type}stories.json", timeout=10.0
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return [story_id for story_id in payload if isinstance(story_id, int)]


def fetch_hacker_news_item(item_id: int) -> dict[str, Any] | None:
    response = httpx.get(f"{HN_API_BASE_URL}/item/{item_id}.json", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return payload


def normalize_hacker_news_item(item: dict[str, Any] | None) -> NormalizedArticle | None:
    """Convert a Hacker News item payload into the shared NormalizedArticle shape."""
    if not item:
        return None
    if item.get("type") != "story" or item.get("deleted") is True or item.get("dead") is True:
        return None

    title = _clean_string(item.get("title"))
    item_id = item.get("id")
    if not title or not isinstance(item_id, int):
        return None

    raw_url = _clean_string(item.get("url")) or HN_ITEM_URL.format(item_id=item_id)
    return NormalizedArticle(
        title=title,
        url=normalize_url(raw_url),
        content=_clean_string(item.get("text")),
        published_at=_published_at(item.get("time")),
        source=HN_SOURCE_NAME,
        source_url=HN_SOURCE_URL,
    )


def _validate_story_type(story_type: str) -> str:
    normalized = story_type.lower().strip()
    if normalized not in HN_STORY_TYPES:
        raise ValueError(f"Unsupported Hacker News story type: {story_type}")
    return normalized


def _clean_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=UTC)
