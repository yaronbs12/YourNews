from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.feedback.service import create_feedback_and_update_preferences
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.feedback import Feedback
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference


def _setup_db() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_article_with_topic(session):
    user = User(email="reader@example.com")
    source = ArticleSource(name="Feed", url="https://example.com/rss", source_type="rss", enabled=True)
    topic = Topic(name="ai")
    session.add_all([user, source, topic])
    session.flush()
    article = Article(source_id=source.id, title="OpenAI news", url="https://example.com/a", content=None, published_at=None)
    session.add(article)
    session.flush()
    session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=1))
    session.commit()
    return user, article, topic


def test_feedback_row_is_created_and_interesting_increases_preference() -> None:
    SessionLocal = _setup_db()
    with SessionLocal() as session:
        user, article, topic = _seed_article_with_topic(session)

        feedback = create_feedback_and_update_preferences(session, user.id, article.id, "INTERESTING")

        preference = session.scalar(select(UserPreference).where(UserPreference.user_id == user.id, UserPreference.topic_id == topic.id))
        assert feedback.id is not None
        assert len(session.scalars(select(Feedback)).all()) == 1
        assert preference is not None
        assert preference.weight == 2


def test_not_interesting_decreases_preference() -> None:
    SessionLocal = _setup_db()
    with SessionLocal() as session:
        user, article, topic = _seed_article_with_topic(session)

        create_feedback_and_update_preferences(session, user.id, article.id, "NOT_INTERESTING")

        preference = session.scalar(select(UserPreference).where(UserPreference.user_id == user.id, UserPreference.topic_id == topic.id))
        assert preference is not None
        assert preference.weight == -2


def test_neutral_creates_feedback_without_changing_preference() -> None:
    SessionLocal = _setup_db()
    with SessionLocal() as session:
        user, article, topic = _seed_article_with_topic(session)
        preference = UserPreference(user_id=user.id, topic_id=topic.id, weight=5)
        session.add(preference)
        session.commit()

        create_feedback_and_update_preferences(session, user.id, article.id, "NEUTRAL")

        assert len(session.scalars(select(Feedback)).all()) == 1
        assert preference.weight == 5


def test_multiple_feedback_events_accumulate_weights() -> None:
    SessionLocal = _setup_db()
    with SessionLocal() as session:
        user, article, topic = _seed_article_with_topic(session)

        create_feedback_and_update_preferences(session, user.id, article.id, "INTERESTING")
        create_feedback_and_update_preferences(session, user.id, article.id, "INTERESTING")
        create_feedback_and_update_preferences(session, user.id, article.id, "NOT_INTERESTING")

        preference = session.scalar(select(UserPreference).where(UserPreference.user_id == user.id, UserPreference.topic_id == topic.id))
        assert preference is not None
        assert preference.weight == 2


def test_feedback_api_validates_invalid_user_article_and_label() -> None:
    SessionLocal = _setup_db()

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with SessionLocal() as session:
        user, article, _ = _seed_article_with_topic(session)
        user_id = user.id
        article_id = article.id

    invalid_user = client.post("/feedback", json={"user_id": 999, "article_id": article_id, "label": "INTERESTING"})
    invalid_article = client.post("/feedback", json={"user_id": user_id, "article_id": 999, "label": "INTERESTING"})
    invalid_label = client.post("/feedback", json={"user_id": user_id, "article_id": article_id, "label": "BAD"})

    assert invalid_user.status_code == 404
    assert invalid_article.status_code == 404
    assert invalid_label.status_code == 400
    app.dependency_overrides.clear()
