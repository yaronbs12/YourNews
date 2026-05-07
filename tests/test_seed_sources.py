from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.ingestion.seed_sources import DEFAULT_RSS_SOURCES, seed_default_rss_sources
from app.models import *  # noqa: F403,F401
from app.models.article_source import ArticleSource


def test_seed_default_rss_sources_inserts_defaults() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        inserted = seed_default_rss_sources(session)

        assert inserted == len(DEFAULT_RSS_SOURCES)
        sources = session.scalars(select(ArticleSource)).all()
        assert len(sources) == len(DEFAULT_RSS_SOURCES)


def test_seed_default_rss_sources_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        first = seed_default_rss_sources(session)
        second = seed_default_rss_sources(session)

        assert first == len(DEFAULT_RSS_SOURCES)
        assert second == 0
        assert len(session.scalars(select(ArticleSource)).all()) == len(DEFAULT_RSS_SOURCES)


def test_seeded_sources_have_rss_type_and_enabled() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        seed_default_rss_sources(session)
        sources = session.scalars(select(ArticleSource)).all()

        assert all(source.source_type == "rss" for source in sources)
        assert all(source.enabled is True for source in sources)
