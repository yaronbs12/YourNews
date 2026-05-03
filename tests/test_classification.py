from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.classification.run_topics import main
from app.classification.service import classify_article_text, classify_unclassified_articles
from app.db.base import Base
from app.models import *  # noqa: F403,F401
from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic


def test_classify_article_text_detects_all_topics_case_insensitively() -> None:
    text_topics = classify_article_text(
        "OPENAI LLM and Artificial Intelligence developer update",
        "GitHub software startup reports cyber BREACH vulnerability while market funding company reacts to election and president government news.",
    )

    assert "ai" in text_topics
    assert "tech" in text_topics
    assert "security" in text_topics
    assert "business" in text_topics
    assert "world" in text_topics


def test_classify_article_text_returns_general_when_no_match() -> None:
    assert classify_article_text("Recipe", "Fresh basil and tomatoes") == ["general"]


def test_classify_article_text_returns_multiple_topics() -> None:
    topics = classify_article_text("OpenAI market update", "Artificial intelligence and company funding")
    assert "ai" in topics
    assert "business" in topics


def test_classify_unclassified_articles_creates_rows_and_skips_already_classified() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        source = ArticleSource(name="Feed", url="https://example.com/rss", source_type="rss", enabled=True)
        session.add(source)
        session.flush()

        new_a = Article(source_id=source.id, title="OpenAI LLM launch", url="https://example.com/a", content="artificial intelligence", published_at=None)
        old_a = Article(source_id=source.id, title="Breach update", url="https://example.com/b", content="cyber vulnerability", published_at=None)
        session.add_all([new_a, old_a])
        session.flush()

        security = Topic(name="security")
        session.add(security)
        session.flush()
        session.add(ArticleTopic(article_id=old_a.id, topic_id=security.id, relevance_score=2))
        session.commit()

        count = classify_unclassified_articles(session)

        assert count == 1
        topics = session.scalars(select(Topic)).all()
        links = session.scalars(select(ArticleTopic)).all()
        assert len(topics) >= 2
        assert len(links) >= 2
        assert all(link.relevance_score >= 1 for link in links)

        already_links = session.scalars(select(ArticleTopic).where(ArticleTopic.article_id == old_a.id)).all()
        assert len(already_links) == 1


def test_run_topics_main_calls_service_and_prints(capsys) -> None:
    with patch("app.classification.run_topics.SessionLocal") as session_local:
        with patch("app.classification.run_topics.classify_unclassified_articles", return_value=7) as classify:
            main()

    classify.assert_called_once_with(session_local.return_value.__enter__.return_value)
    assert "Classified 7 articles." in capsys.readouterr().out
