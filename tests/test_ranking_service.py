from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference
from app.ranking.service import TOPIC_SCORE_WEIGHTS, RankingUserNotFoundError, rank_articles_for_digest

NOW = datetime(2026, 5, 7, tzinfo=timezone.utc)


def _sessionmaker() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _add_source(session: Session, name: str = "Source") -> ArticleSource:
    source = ArticleSource(
        name=name,
        url=f"https://example.com/{name.lower().replace(' ', '-')}/rss",
        source_type="rss",
        enabled=True,
    )
    session.add(source)
    session.flush()
    return source


def _add_article(
    session: Session,
    source: ArticleSource,
    title: str,
    created_at: datetime,
    topics: list[str],
    published_at: datetime | None = None,
) -> Article:
    article = Article(
        source_id=source.id,
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        content=None,
        published_at=published_at,
        created_at=created_at,
    )
    session.add(article)
    session.flush()
    for name in topics:
        topic = session.query(Topic).filter_by(name=name).one_or_none()
        if topic is None:
            topic = Topic(name=name)
            session.add(topic)
            session.flush()
        session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=1))
    return article


def _add_user(session: Session, email: str = "reader@example.com") -> User:
    user = User(email=email)
    session.add(user)
    session.flush()
    return user


def _set_preference(session: Session, user: User, topic_name: str, weight: int) -> None:
    topic = session.query(Topic).filter_by(name=topic_name).one()
    session.add(UserPreference(user_id=user.id, topic_id=topic.id, weight=weight))


def test_topic_score_weights_use_canonical_taxonomy() -> None:
    assert TOPIC_SCORE_WEIGHTS == {
        "ai": 3,
        "technology": 2,
        "cybersecurity": 2,
        "sports": 2,
        "football": 2,
        "basketball": 2,
        "tennis": 2,
        "politics": 2,
        "world": 2,
        "israel": 2,
        "business": 1,
        "finance": 1,
        "startups": 1,
        "science": 1,
        "health": 1,
        "culture": 1,
        "entertainment": 1,
        "gaming": 1,
        "climate": 1,
        "general": 0,
    }
    assert "tech" not in TOPIC_SCORE_WEIGHTS
    assert "security" not in TOPIC_SCORE_WEIGHTS


def test_rank_articles_for_digest_without_user_has_score_breakdown() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Newest General", NOW, ["general"])
        _add_article(session, source, "Older AI", NOW - timedelta(days=1), ["ai"])
        _add_article(session, source, "Older Tech", NOW - timedelta(days=2), ["technology"])
        session.commit()

        ranked = rank_articles_for_digest(session, limit=3)

        assert [item.article.title for item in ranked] == ["Older AI", "Older Tech", "Newest General"]
        assert ranked[0].score_breakdown.topic_score == 3
        assert ranked[0].score_breakdown.preference_score == 0
        assert ranked[0].score_breakdown.freshness_score == 2
        assert ranked[0].score_breakdown.source_penalty == 0
        assert ranked[0].score == 5
        assert ranked[1].score_breakdown.source_penalty == 1


def test_rank_articles_for_digest_with_user_preferences_splits_scores() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Static Winner AI", NOW, ["ai"])
        _add_article(session, source, "Preferred Business", NOW - timedelta(hours=1), ["business"])
        user = _add_user(session, "positive-ranking@example.com")
        _set_preference(session, user, "business", 5)
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2, user_id=user.id)

        assert [item.article.title for item in ranked] == ["Preferred Business", "Static Winner AI"]
        assert ranked[0].score_breakdown.topic_score == 1
        assert ranked[0].score_breakdown.preference_score == 5
        assert ranked[0].score_breakdown.freshness_score == 2
        assert ranked[0].score == 8


def test_rank_articles_for_digest_freshness_boosts_newer_articles() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(session, source, "Old Tech", NOW - timedelta(days=8), ["technology"])
        _add_article(session, source, "Fresh Tech", NOW, ["technology"])
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2)

        assert [item.article.title for item in ranked] == ["Fresh Tech", "Old Tech"]
        assert ranked[0].score_breakdown.freshness_score == 2
        assert ranked[1].score_breakdown.freshness_score == 0


def test_rank_articles_for_digest_uses_published_at_for_freshness_when_available() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source = _add_source(session)
        _add_article(
            session,
            source,
            "Created New But Published Old",
            NOW,
            ["technology"],
            published_at=NOW - timedelta(days=8),
        )
        _add_article(session, source, "Published New", NOW - timedelta(days=8), ["technology"], published_at=NOW)
        session.commit()

        ranked = rank_articles_for_digest(session, limit=2)

        assert ranked[0].article.title == "Published New"
        assert ranked[0].score_breakdown.freshness_score == 2
        assert ranked[1].score_breakdown.freshness_score == 0


def test_rank_articles_for_digest_applies_source_diversity_penalty() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        source_a = _add_source(session, "Source A")
        source_b = _add_source(session, "Source B")
        _add_article(session, source_a, "Best A", NOW, ["ai"])
        _add_article(session, source_a, "Second A", NOW - timedelta(minutes=2), ["ai"])
        _add_article(session, source_b, "Best B", NOW - timedelta(minutes=1), ["technology"])
        session.commit()

        ranked = rank_articles_for_digest(session, limit=3)

        assert [item.article.title for item in ranked] == ["Best A", "Best B", "Second A"]
        assert ranked[1].score_breakdown.source_penalty == 0
        assert ranked[2].score_breakdown.source_penalty == 1


def test_rank_articles_for_digest_unknown_user_raises_clear_error() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        with pytest.raises(RankingUserNotFoundError, match="User not found"):
            rank_articles_for_digest(session, user_id=999)
