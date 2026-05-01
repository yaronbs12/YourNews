from datetime import UTC, datetime
from time import struct_time
from urllib.parse import urlparse

import feedparser

from app.ingestion.schemas import NormalizedArticle
from app.ingestion.urls import normalize_url


def fetch_rss_articles(feed_url: str) -> list[NormalizedArticle]:
    parsed_feed = feedparser.parse(feed_url)
    return parse_rss_feed(parsed_feed, feed_url)


def parse_rss_feed(parsed_feed: object, feed_url: str) -> list[NormalizedArticle]:
    source = _source_name(parsed_feed, feed_url)
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    for entry in getattr(parsed_feed, "entries", []):
        raw_url = _entry_link(entry)
        title = _entry_value(entry, "title")
        if not raw_url or not title:
            continue

        normalized_url = normalize_url(raw_url)
        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)
        articles.append(
            NormalizedArticle(
                title=title,
                url=normalized_url,
                content=_entry_content(entry),
                published_at=_entry_datetime(entry),
                source=source,
                source_url=feed_url,
            )
        )

    return articles


def _entry_value(entry: object, key: str) -> str | None:
    value = getattr(entry, key, None)
    if value is None and isinstance(entry, dict):
        value = entry.get(key)
    if value is None:
        return None
    return str(value).strip() or None


def _entry_link(entry: object) -> str | None:
    return _entry_value(entry, "link") or _entry_value(entry, "id")


def _entry_content(entry: object) -> str | None:
    content = getattr(entry, "content", None)
    if content is None and isinstance(entry, dict):
        content = entry.get("content")
    if content:
        first_item = content[0]
        if isinstance(first_item, dict):
            value = first_item.get("value")
        else:
            value = getattr(first_item, "value", None)
        if value:
            return str(value).strip()

    return _entry_value(entry, "summary")


def _entry_datetime(entry: object) -> datetime | None:
    published = getattr(entry, "published_parsed", None)
    if published is None and isinstance(entry, dict):
        published = entry.get("published_parsed")
    if published is None:
        published = getattr(entry, "updated_parsed", None)
    if published is None and isinstance(entry, dict):
        published = entry.get("updated_parsed")
    if not isinstance(published, struct_time):
        return None

    return datetime(*published[:6], tzinfo=UTC)


def _source_name(parsed_feed: object, feed_url: str) -> str:
    feed = getattr(parsed_feed, "feed", None)
    if feed is None and isinstance(parsed_feed, dict):
        feed = parsed_feed.get("feed")

    title = None
    if feed is not None:
        title = getattr(feed, "title", None)
        if title is None and isinstance(feed, dict):
            title = feed.get("title")

    if title:
        return str(title).strip()

    hostname = urlparse(feed_url).hostname
    return hostname or feed_url
