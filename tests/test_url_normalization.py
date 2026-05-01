from app.ingestion.urls import normalize_url


def test_normalize_url_for_deduplication() -> None:
    assert (
        normalize_url("HTTPS://Example.COM/news/item/?utm_source=rss&b=2&a=1#comments")
        == "https://example.com/news/item?a=1&b=2"
    )


def test_normalize_url_removes_common_tracking_params() -> None:
    assert normalize_url("https://example.com/article?gclid=abc&utm_campaign=spring") == "https://example.com/article"
