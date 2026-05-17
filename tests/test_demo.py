from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.demo.run_demo as run_demo
from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user_preference import UserPreference


def _sessionmaker() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_demo_script_can_be_imported() -> None:
    assert run_demo.DEMO_EMAIL == "demo@yournews.local"
    assert callable(run_demo.main)


def test_get_or_create_demo_user_reuses_existing_user() -> None:
    SessionLocal = _sessionmaker()
    with SessionLocal() as session:
        first_user = run_demo.get_or_create_demo_user(session)
        second_user = run_demo.get_or_create_demo_user(session)

        assert first_user.id == second_user.id
        assert first_user.email == "demo@yournews.local"


def test_pick_feedback_candidates_prefers_ai_technology_cybersecurity_positive() -> None:
    candidates = [
        run_demo.ArticleCandidate(article_id=1, title="Business", topics=["business"]),
        run_demo.ArticleCandidate(article_id=2, title="AI", topics=["ai"]),
        run_demo.ArticleCandidate(article_id=3, title="Security", topics=["cybersecurity"]),
    ]

    positive, negative = run_demo.pick_feedback_candidates(candidates)

    assert positive == candidates[1]
    assert negative == candidates[0]


def test_demo_helpers_list_preferences_and_digest_without_live_rss() -> None:
    SessionLocal = _sessionmaker()
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    with SessionLocal() as session:
        source = ArticleSource(name="Demo Source", url="https://example.com/rss", source_type="rss", enabled=True)
        user = run_demo.get_or_create_demo_user(session)
        ai = Topic(name="ai")
        business = Topic(name="business")
        session.add_all([source, ai, business])
        session.flush()
        article = Article(
            source_id=source.id,
            title="AI Demo Article",
            url="https://example.com/ai-demo",
            content=None,
            published_at=None,
            created_at=now,
        )
        session.add(article)
        session.flush()
        session.add_all(
            [
                ArticleTopic(article_id=article.id, topic_id=ai.id, relevance_score=9),
                UserPreference(user_id=user.id, topic_id=business.id, weight=-1),
                UserPreference(user_id=user.id, topic_id=ai.id, weight=4),
            ]
        )
        session.commit()

        candidates = run_demo.article_candidates_with_topics(session)
        preferences = run_demo.list_user_preferences(session, user.id)
        digest_items = run_demo.personalized_digest_items(session, user.id, limit=1)

        assert candidates == [run_demo.ArticleCandidate(article_id=article.id, title="AI Demo Article", topics=["ai"])]
        assert preferences == [("ai", 4), ("business", -1)]
        assert digest_items == [("AI Demo Article", "Demo Source", ["ai"])]
