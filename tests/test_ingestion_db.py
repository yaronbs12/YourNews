from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.db import insert_new_articles
from app.ingestion.schemas import NormalizedArticle
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource


def test_insert_new_articles_skips_duplicate_urls() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    article = NormalizedArticle(
        title="Launch",
        url="https://example.com/news/launch",
        content="Summary",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        source="Example Feed",
        source_url="https://example.com/rss.xml",
    )

    with SessionLocal() as session:
        first_insert = insert_new_articles(session, [article, article])
        session.commit()

        second_insert = insert_new_articles(session, [article])
        session.commit()

        assert len(first_insert) == 1
        assert second_insert == []
        assert len(session.scalars(select(Article)).all()) == 1
        sources = session.scalars(select(ArticleSource)).all()
        assert len(sources) == 1
        assert sources[0].source_type == "rss"
        assert sources[0].enabled is True
        assert sources[0].last_fetched_at is None
