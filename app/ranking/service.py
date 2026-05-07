from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic

TOPIC_SCORE_WEIGHTS: dict[str, int] = {
    "ai": 3,
    "tech": 2,
    "security": 2,
    "business": 1,
    "science": 1,
    "finance": 1,
    "general": 0,
}


@dataclass(frozen=True)
class RankedArticle:
    article: Article
    source_name: str
    topics: list[str]
    score: int


def _get_article_topics(session: Session, article_id: int) -> list[str]:
    return session.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


def _score_topics(topics: list[str]) -> int:
    return sum(TOPIC_SCORE_WEIGHTS.get(topic, 0) for topic in topics)


def rank_articles_for_digest(session: Session, limit: int = 10) -> list[RankedArticle]:
    clamped_limit = max(1, limit)
    rows = session.execute(
        select(Article, ArticleSource.name).join(ArticleSource, Article.source_id == ArticleSource.id)
    ).all()

    ranked_articles: list[RankedArticle] = []
    for article, source_name in rows:
        topics = _get_article_topics(session, article.id)
        ranked_articles.append(
            RankedArticle(
                article=article,
                source_name=source_name,
                topics=topics,
                score=_score_topics(topics),
            )
        )

    return sorted(
        ranked_articles,
        key=lambda item: (item.score, item.article.created_at, item.article.id),
        reverse=True,
    )[:clamped_limit]
