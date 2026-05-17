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


def test_classify_article_text_detects_new_topics() -> None:
    topics = classify_article_text(
        "NASA science study links climate and health policy",
        "Doctors discuss vaccine research while a football team, Netflix movie, bitcoin fund, and solar energy story trend.",
    )

    assert "science" in topics
    assert "health" in topics
    assert "sports" in topics
    assert "politics" in topics
    assert "finance" in topics
    assert "climate" in topics
    assert "entertainment" in topics


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


def test_classify_article_text_detects_football_article() -> None:
    topics = classify_article_text(
        "NFL quarterback throws winning touchdown",
        "The football team advanced in the playoffs after a dramatic game.",
    )

    assert "football" in topics
    assert "sports" in topics


def test_classify_article_text_detects_basketball_article() -> None:
    topics = classify_article_text(
        "NBA playoffs: point guard hits three-pointer",
        "The basketball team celebrated a late dunk.",
    )

    assert "basketball" in topics
    assert "sports" in topics


def test_classify_article_text_detects_tennis_article() -> None:
    topics = classify_article_text(
        "Wimbledon champion wins grand slam final",
        "The tennis star used a strong serve and forehand.",
    )

    assert "tennis" in topics


def test_classify_article_text_detects_israel_world_politics_article() -> None:
    topics = classify_article_text(
        "Israel government discusses Gaza border policy",
        "The prime minister and foreign diplomats responded to the conflict.",
    )

    assert "israel" in topics
    assert "world" in topics
    assert "politics" in topics


def test_classify_article_text_detects_startup_business_article() -> None:
    topics = classify_article_text(
        "Startup raises Series A funding",
        "The founder said the company will grow revenue after the venture round.",
    )

    assert "startups" in topics
    assert "business" in topics


def test_classify_article_text_detects_gaming_entertainment_article() -> None:
    topics = classify_article_text(
        "Netflix announces video game adaptation",
        "The gaming studio and Hollywood film producers will stream the series.",
    )

    assert "gaming" in topics
    assert "entertainment" in topics


def test_classify_article_text_detects_climate_science_article() -> None:
    topics = classify_article_text(
        "Scientists publish climate study on carbon emissions",
        "NASA researchers measured warming and renewable energy impacts.",
    )

    assert "climate" in topics
    assert "science" in topics
