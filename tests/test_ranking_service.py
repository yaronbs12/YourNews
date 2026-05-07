from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.ranking.service import rank_articles_for_digest


def _add_topic(session, article: Article, name: str, score: int = 1) -> None:
    topic = session.query(Topic).filter_by(name=name).one_or_none()
    if topic is None:
        topic = Topic(name=name)
        session.add(topic)
        session.flush()
    session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=score))


def test_rank_articles_for_digest_prefers_weighted_topics_over_general() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)

    with SessionLocal() as session:
        source = ArticleSource(name="Source", url="https://example.com/rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        general = Article(source_id=source.id, title="Newest general", url="https://example.com/general", content=None, published_at=None, created_at=now)
        ai = Article(source_id=source.id, title="Older AI", url="https://example.com/ai", content=None, published_at=None, created_at=now - timedelta(days=1))
        tech = Article(source_id=source.id, title="Older tech", url="https://example.com/tech", content=None, published_at=None, created_at=now - timedelta(days=2))
        session.add_all([general, ai, tech])
        session.flush()
        _add_topic(session, general, "general")
        _add_topic(session, ai, "ai")
        _add_topic(session, tech, "tech")
        session.commit()

        ranked = rank_articles_for_digest(session, limit=3)

        assert [item.article.title for item in ranked] == ["Older AI", "Older tech", "Newest general"]
        assert [item.score for item in ranked] == [3, 2, 0]


def test_rank_articles_for_digest_uses_created_at_desc_as_tiebreaker() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)

    with SessionLocal() as session:
        source = ArticleSource(name="Source", url="https://example.com/tie-rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        older = Article(source_id=source.id, title="Older AI", url="https://example.com/tie-older", content=None, published_at=None, created_at=now - timedelta(hours=1))
        newer = Article(source_id=source.id, title="Newer AI", url="https://example.com/tie-newer", content=None, published_at=None, created_at=now)
        session.add_all([older, newer])
        session.flush()
        _add_topic(session, older, "ai")
        _add_topic(session, newer, "ai")
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2)

        assert [item.article.title for item in ranked] == ["Newer AI", "Older AI"]
