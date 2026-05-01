from time import struct_time
from types import SimpleNamespace

from app.ingestion.rss import parse_rss_feed


def test_parse_rss_feed_returns_normalized_articles() -> None:
    parsed_feed = SimpleNamespace(
        feed=SimpleNamespace(title="Example Feed"),
        entries=[
            SimpleNamespace(
                title=" First Article ",
                link="HTTPS://Example.com/news/first/?utm_source=newsletter&b=2&a=1#section",
                summary="Short summary",
                published_parsed=struct_time((2026, 5, 1, 10, 30, 0, 4, 121, 0)),
            ),
            SimpleNamespace(title="", link="https://example.com/news/skip"),
        ],
    )

    articles = parse_rss_feed(parsed_feed, "https://example.com/rss.xml")

    assert len(articles) == 1
    assert articles[0].title == "First Article"
    assert articles[0].url == "https://example.com/news/first?a=1&b=2"
    assert articles[0].content == "Short summary"
    assert articles[0].published_at is not None
    assert articles[0].source == "Example Feed"
    assert articles[0].source_url == "https://example.com/rss.xml"


def test_parse_rss_feed_deduplicates_urls_within_feed() -> None:
    parsed_feed = SimpleNamespace(
        feed=SimpleNamespace(title="Example Feed"),
        entries=[
            SimpleNamespace(title="One", link="https://example.com/story?utm_medium=social"),
            SimpleNamespace(title="Two", link="https://example.com/story/"),
        ],
    )

    articles = parse_rss_feed(parsed_feed, "https://example.com/rss.xml")

    assert len(articles) == 1
    assert articles[0].title == "One"
