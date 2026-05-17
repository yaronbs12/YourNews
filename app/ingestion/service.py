from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.db import insert_new_articles
from app.ingestion.hacker_news import fetch_hacker_news_articles
from app.ingestion.rss import fetch_rss_articles
from app.models.article_source import ArticleSource


def ingest_rss_feed(session: Session, feed_url: str) -> int:
    try:
        articles = fetch_rss_articles(feed_url)
        inserted_articles = insert_new_articles(session, articles)
        session.commit()
        return len(inserted_articles)
    except Exception:
        session.rollback()
        raise


def ingest_hacker_news_stories(session: Session, story_type: str = "top", limit: int = 30) -> int:
    try:
        articles = fetch_hacker_news_articles(story_type=story_type, limit=limit)
        inserted_articles = insert_new_articles(session, articles, source_type="hacker_news", category="technology")
        session.commit()
        return len(inserted_articles)
    except Exception:
        session.rollback()
        raise


def ingest_enabled_rss_sources(session: Session) -> dict[str, int]:
    results: dict[str, int] = {}
    sources = session.scalars(
        select(ArticleSource).where(ArticleSource.source_type == "rss", ArticleSource.enabled.is_(True))
    ).all()

    for source in sources:
        try:
            articles = fetch_rss_articles(source.url)
            inserted_articles = insert_new_articles(session, articles)
            source.last_fetched_at = datetime.now(timezone.utc)
            session.commit()
            results[source.name] = len(inserted_articles)
        except Exception:
            session.rollback()
            results[source.name] = 0

    return results
