from sqlalchemy.orm import Session

from app.ingestion.db import insert_new_articles
from app.ingestion.rss import fetch_rss_articles


def ingest_rss_feed(session: Session, feed_url: str) -> int:
    try:
        articles = fetch_rss_articles(feed_url)
        inserted_articles = insert_new_articles(session, articles)
        session.commit()
        return len(inserted_articles)
    except Exception:
        session.rollback()
        raise
