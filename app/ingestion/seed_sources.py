from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.article_source import ArticleSource

DEFAULT_RSS_SOURCES: list[tuple[str, str]] = [
    ("Hacker News Front Page", "https://hnrss.org/frontpage"),
    ("Hacker News Newest", "https://hnrss.org/newest"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
]


def seed_default_rss_sources(session: Session) -> int:
    inserted = 0
    try:
        for name, url in DEFAULT_RSS_SOURCES:
            existing = session.scalar(
                select(ArticleSource).where(
                    or_(
                        ArticleSource.name == name,
                        ArticleSource.url == url,
                    )
                )
            )
            if existing is not None:
                continue

            session.add(ArticleSource(name=name, url=url, source_type="rss", enabled=True))
            inserted += 1

        session.commit()
        return inserted
    except Exception:
        session.rollback()
        raise


def main() -> None:
    with SessionLocal() as session:
        inserted = seed_default_rss_sources(session)
    print(f"Inserted {inserted} sources.")


if __name__ == "__main__":
    main()
