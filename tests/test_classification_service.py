from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.classification.service import classify_article_text, classify_unclassified_articles
from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic


def test_classify_article_text_detects_topics() -> None:
    topics = classify_article_text(
        "OpenAI startup faces security breach during election season",
        "The company and government discussed artificial intelligence and cyber vulnerability in the market.",
    )
    assert "ai" in topics
    assert "tech" in topics
    assert "security" in topics
    assert "business" in topics
    assert "world" in topics


def test_classify_article_text_returns_general_when_no_match() -> None:
    assert classify_article_text("Gardening tips", "How to grow tomatoes") == ["general"]


def test_classify_unclassified_articles_creates_topics_and_links_and_skips_classified() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        source = ArticleSource(name="Source", url="https://example.com/rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()

        a1 = Article(source_id=source.id, title="OpenAI releases new LLM", url="https://example.com/1", content="AI and machine learning progress", published_at=None)
        a2 = Article(source_id=source.id, title="Startup funding jumps", url="https://example.com/2", content="market and business outlook", published_at=None)
        a3 = Article(source_id=source.id, title="Already tagged", url="https://example.com/3", content="security breach", published_at=None)
        session.add_all([a1, a2, a3])
        session.flush()

        pre_topic = Topic(name="security")
        session.add(pre_topic)
        session.flush()
        session.add(ArticleTopic(article_id=a3.id, topic_id=pre_topic.id, relevance_score=1))
        session.commit()

        classified_count = classify_unclassified_articles(session)

        assert classified_count == 2
        links = session.scalars(select(ArticleTopic)).all()
        assert len(links) >= 3

        a1_links = session.scalars(select(ArticleTopic).where(ArticleTopic.article_id == a1.id)).all()
        a2_links = session.scalars(select(ArticleTopic).where(ArticleTopic.article_id == a2.id)).all()
        a3_links = session.scalars(select(ArticleTopic).where(ArticleTopic.article_id == a3.id)).all()

        assert len(a1_links) >= 1
        assert len(a2_links) >= 1
        assert len(a3_links) == 1
