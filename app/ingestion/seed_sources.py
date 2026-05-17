from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.article_source import ArticleSource


@dataclass(frozen=True)
class DefaultRssSource:
    name: str
    url: str
    category: str


DEFAULT_RSS_SOURCES: list[DefaultRssSource] = [
    DefaultRssSource("NPR News", "https://feeds.npr.org/1001/rss.xml", "general"),
    DefaultRssSource("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "world"),
    DefaultRssSource("TechCrunch", "https://techcrunch.com/feed/", "technology"),
    DefaultRssSource("The Verge", "https://www.theverge.com/rss/index.xml", "technology"),
    DefaultRssSource("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "business"),
    DefaultRssSource("NASA Breaking News", "https://www.nasa.gov/news-release/feed/", "science"),
    DefaultRssSource("ESPN Top Headlines", "https://www.espn.com/espn/rss/news", "sports"),
    DefaultRssSource("Hacker News Front Page", "https://hnrss.org/frontpage", "technology"),
    DefaultRssSource("Hacker News Newest", "https://hnrss.org/newest", "technology"),
]


def seed_default_rss_sources(session: Session) -> int:
    inserted = 0
    try:
        for source_def in DEFAULT_RSS_SOURCES:
            existing = session.scalar(
                select(ArticleSource).where(
                    or_(
                        ArticleSource.name == source_def.name,
                        ArticleSource.url == source_def.url,
                    )
                )
            )
            if existing is not None:
                if getattr(existing, "category", None) in (None, "general") and source_def.category != "general":
                    existing.category = source_def.category
                continue

            session.add(
                ArticleSource(
                    name=source_def.name,
                    url=source_def.url,
                    source_type="rss",
                    category=source_def.category,
                    enabled=True,
                )
            )
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
