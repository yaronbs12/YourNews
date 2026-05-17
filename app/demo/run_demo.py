from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.classification.service import classify_unclassified_articles
from app.db.session import SessionLocal
from app.feedback.service import create_feedback_and_update_preferences
from app.ingestion.seed_sources import seed_default_rss_sources
from app.ingestion.service import ingest_enabled_rss_sources
from app.models.article import Article
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference
from app.ranking.service import rank_articles_for_digest

DEMO_EMAIL = "demo@yournews.local"
PREFERRED_POSITIVE_TOPICS = ["ai", "technology", "cybersecurity"]


@dataclass(frozen=True)
class ArticleCandidate:
    article_id: int
    title: str
    topics: list[str]


@dataclass(frozen=True)
class DemoResult:
    user_id: int
    sources_inserted: int
    articles_ingested: int
    articles_classified: int
    feedback_actions: list[str]
    preferences: list[tuple[str, int]]
    digest_items: list[tuple[str, str, list[str]]]


def get_or_create_demo_user(session: Session, email: str = DEMO_EMAIL) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(email=email)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def topic_names_for_article(session: Session, article_id: int) -> list[str]:
    return session.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


def article_candidates_with_topics(session: Session, limit: int = 20) -> list[ArticleCandidate]:
    rows = session.scalars(
        select(Article.id)
        .join(ArticleTopic, ArticleTopic.article_id == Article.id)
        .order_by(Article.created_at.desc(), Article.id.desc())
        .limit(max(1, limit) * 3)
    ).all()

    candidates: list[ArticleCandidate] = []
    seen_article_ids: set[int] = set()
    for article_id in rows:
        if article_id in seen_article_ids:
            continue
        seen_article_ids.add(article_id)
        article = session.get(Article, article_id)
        if article is None:
            continue
        topics = topic_names_for_article(session, article_id)
        if topics:
            candidates.append(ArticleCandidate(article_id=article.id, title=article.title, topics=topics))
        if len(candidates) >= max(1, limit):
            break
    return candidates


def pick_feedback_candidates(candidates: list[ArticleCandidate]) -> tuple[ArticleCandidate | None, ArticleCandidate | None]:
    positive = next(
        (
            candidate
            for topic in PREFERRED_POSITIVE_TOPICS
            for candidate in candidates
            if topic in candidate.topics
        ),
        None,
    )
    if positive is None and candidates:
        positive = candidates[0]

    negative = next((candidate for candidate in candidates if candidate.article_id != getattr(positive, "article_id", None)), None)
    return positive, negative


def list_user_preferences(session: Session, user_id: int) -> list[tuple[str, int]]:
    return [
        (topic, weight)
        for topic, weight in session.execute(
            select(Topic.name, func.sum(UserPreference.weight).label("weight"))
            .join(UserPreference, UserPreference.topic_id == Topic.id)
            .where(UserPreference.user_id == user_id)
            .group_by(Topic.name)
            .order_by(func.sum(UserPreference.weight).desc(), Topic.name.asc())
        ).all()
    ]


def personalized_digest_items(session: Session, user_id: int, limit: int = 5) -> list[tuple[str, str, list[str]]]:
    return [
        (ranked.article.title, ranked.source_name, ranked.topics)
        for ranked in rank_articles_for_digest(session, limit=limit, user_id=user_id)
    ]


def run_demo(session: Session) -> DemoResult:
    user = get_or_create_demo_user(session)
    sources_inserted = seed_default_rss_sources(session)
    ingestion_counts = ingest_enabled_rss_sources(session)
    articles_ingested = sum(ingestion_counts.values())
    articles_classified = classify_unclassified_articles(session)

    feedback_actions: list[str] = []
    positive, negative = pick_feedback_candidates(article_candidates_with_topics(session))
    if positive is not None:
        feedback = create_feedback_and_update_preferences(session, user.id, positive.article_id, "INTERESTING")
        feedback_actions.append(f"{feedback.label.value}: {positive.title}")
    if negative is not None:
        feedback = create_feedback_and_update_preferences(session, user.id, negative.article_id, "NOT_INTERESTING")
        feedback_actions.append(f"{feedback.label.value}: {negative.title}")

    return DemoResult(
        user_id=user.id,
        sources_inserted=sources_inserted,
        articles_ingested=articles_ingested,
        articles_classified=articles_classified,
        feedback_actions=feedback_actions,
        preferences=list_user_preferences(session, user.id),
        digest_items=personalized_digest_items(session, user.id, limit=5),
    )


def print_demo_result(result: DemoResult) -> None:
    print("YourNews demo complete")
    print("Preferences accumulate when this script is run repeatedly; no data is deleted.")
    print(f"Demo user id: {result.user_id}")
    print(f"Sources inserted: {result.sources_inserted}")
    print(f"Articles ingested: {result.articles_ingested}")
    print(f"Articles classified: {result.articles_classified}")
    print(f"Feedback actions created: {len(result.feedback_actions)}")
    for action in result.feedback_actions:
        print(f"  - {action}")

    print("Current user preferences:")
    if result.preferences:
        for topic, weight in result.preferences:
            print(f"  - {topic}: {weight}")
    else:
        print("  - none yet")

    print("Top 5 personalized digest items:")
    if result.digest_items:
        for index, (title, source_name, topics) in enumerate(result.digest_items, start=1):
            print(f"  {index}. {title} [{source_name}] topics={', '.join(topics) or 'none'}")
    else:
        print("  - no articles available yet")


def main() -> None:
    with SessionLocal() as session:
        result = run_demo(session)
    print_demo_result(result)


if __name__ == "__main__":
    main()
