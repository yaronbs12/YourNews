from datetime import datetime, timedelta, timezone

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference
from app.ranking.service import RankingUserNotFoundError, rank_articles_for_digest


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


def test_rank_articles_for_digest_boosts_positive_user_preferences() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)

    with SessionLocal() as session:
        source = ArticleSource(name="Source", url="https://example.com/personal-rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        ai = Article(source_id=source.id, title="AI", url="https://example.com/p-ai", content=None, published_at=None, created_at=now)
        business = Article(
            source_id=source.id,
            title="Business",
            url="https://example.com/p-business",
            content=None,
            published_at=None,
            created_at=now - timedelta(hours=1),
        )
        session.add_all([ai, business])
        session.flush()
        _add_topic(session, ai, "ai")
        _add_topic(session, business, "business")
        user = User(email="positive@example.com")
        session.add(user)
        session.flush()
        business_topic = session.query(Topic).filter_by(name="business").one()
        session.add(UserPreference(user_id=user.id, topic_id=business_topic.id, weight=5))
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Business", "AI"]
        assert [item.score for item in ranked] == [6, 3]


def test_rank_articles_for_digest_lowers_negative_user_preferences() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)

    with SessionLocal() as session:
        source = ArticleSource(name="Source", url="https://example.com/negative-rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()
        ai = Article(source_id=source.id, title="AI", url="https://example.com/n-ai", content=None, published_at=None, created_at=now)
        tech = Article(
            source_id=source.id,
            title="Tech",
            url="https://example.com/n-tech",
            content=None,
            published_at=None,
            created_at=now - timedelta(hours=1),
        )
        session.add_all([ai, tech])
        session.flush()
        _add_topic(session, ai, "ai")
        _add_topic(session, tech, "tech")
        user = User(email="negative@example.com")
        session.add(user)
        session.flush()
        ai_topic = session.query(Topic).filter_by(name="ai").one()
        session.add(UserPreference(user_id=user.id, topic_id=ai_topic.id, weight=-4))
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Tech", "AI"]
        assert [item.score for item in ranked] == [2, -1]


def test_rank_articles_for_digest_unknown_user_raises_clear_error() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        with pytest.raises(RankingUserNotFoundError, match="User not found"):
            rank_articles_for_digest(session, user_id=999)
