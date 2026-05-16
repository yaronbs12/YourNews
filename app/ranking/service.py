from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.article_source import ArticleSource
from app.models.associations import ArticleTopic
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference

TOPIC_SCORE_WEIGHTS: dict[str, int] = {
    "ai": 3,
    "tech": 2,
    "security": 2,
    "business": 1,
    "science": 1,
    "finance": 1,
    "general": 0,
}
FRESHNESS_RECENT_SCORE = 2
FRESHNESS_WEEK_SCORE = 1
SOURCE_DIVERSITY_PENALTY = 1


class RankingUserNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ScoreBreakdown:
    topic_score: int
    preference_score: int
    freshness_score: int
    source_penalty: int = 0

    @property
    def total_score(self) -> int:
        return self.topic_score + self.preference_score + self.freshness_score - self.source_penalty


@dataclass(frozen=True)
class RankedArticle:
    article: Article
    source_name: str
    topics: list[str]
    score_breakdown: ScoreBreakdown

    @property
    def score(self) -> int:
        return self.score_breakdown.total_score


def _get_article_topics(session: Session, article_id: int) -> list[str]:
    return session.scalars(
        select(Topic.name)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(Topic.name.asc())
    ).all()


def _score_base_topics(topics: list[str]) -> int:
    return sum(TOPIC_SCORE_WEIGHTS.get(topic, 0) for topic in topics)


def _score_topics(topics: list[str], preference_weights: dict[str, int] | None = None) -> int:
    return _score_base_topics(topics) + _score_user_preferences(topics, preference_weights)


def _score_user_preferences(topics: list[str], preference_weights: dict[str, int] | None = None) -> int:
    preferences = preference_weights or {}
    return sum(preferences.get(topic, 0) for topic in topics)


def _article_ranked_at(article: Article) -> datetime:
    ranked_at = article.published_at or article.created_at
    if ranked_at.tzinfo is None:
        return ranked_at.replace(tzinfo=UTC)
    return ranked_at


def _score_freshness(article: Article, newest_ranked_at: datetime) -> int:
    age = newest_ranked_at - _article_ranked_at(article)
    if age <= timedelta(days=1):
        return FRESHNESS_RECENT_SCORE
    if age <= timedelta(days=7):
        return FRESHNESS_WEEK_SCORE
    return 0


def _get_user_preference_weights(session: Session, user_id: int | None) -> dict[str, int] | None:
    if user_id is None:
        return None

    if session.get(User, user_id) is None:
        raise RankingUserNotFoundError("User not found")

    return dict(
        session.execute(
            select(Topic.name, func.sum(UserPreference.weight))
            .join(UserPreference, UserPreference.topic_id == Topic.id)
            .where(UserPreference.user_id == user_id)
            .group_by(Topic.name)
            .order_by(Topic.name.asc())
        ).all()
    )


def _without_source_penalty(
    topics: list[str], preference_weights: dict[str, int] | None
) -> ScoreBreakdown:
    return ScoreBreakdown(
        topic_score=_score_base_topics(topics),
        preference_score=_score_user_preferences(topics, preference_weights),
        freshness_score=0,
    )


def _apply_source_diversity(candidates: list[RankedArticle], limit: int) -> list[RankedArticle]:
    selected: list[RankedArticle] = []
    remaining = candidates[:]
    selected_source_counts: dict[str, int] = {}

    while remaining and len(selected) < limit:
        best_index = 0
        best_candidate = remaining[0]
        best_breakdown = _with_source_penalty(best_candidate, selected_source_counts)
        best_sort_key = _sort_key(best_candidate, best_breakdown)

        for index, candidate in enumerate(remaining[1:], start=1):
            breakdown = _with_source_penalty(candidate, selected_source_counts)
            sort_key = _sort_key(candidate, breakdown)
            if sort_key > best_sort_key:
                best_index = index
                best_candidate = candidate
                best_breakdown = breakdown
                best_sort_key = sort_key

        selected.append(
            RankedArticle(
                article=best_candidate.article,
                source_name=best_candidate.source_name,
                topics=best_candidate.topics,
                score_breakdown=best_breakdown,
            )
        )
        selected_source_counts[best_candidate.source_name] = (
            selected_source_counts.get(best_candidate.source_name, 0) + 1
        )
        remaining.pop(best_index)

    return selected


def _with_source_penalty(candidate: RankedArticle, selected_source_counts: dict[str, int]) -> ScoreBreakdown:
    return ScoreBreakdown(
        topic_score=candidate.score_breakdown.topic_score,
        preference_score=candidate.score_breakdown.preference_score,
        freshness_score=candidate.score_breakdown.freshness_score,
        source_penalty=selected_source_counts.get(candidate.source_name, 0) * SOURCE_DIVERSITY_PENALTY,
    )


def _sort_key(candidate: RankedArticle, breakdown: ScoreBreakdown) -> tuple[int, datetime, int]:
    return (breakdown.total_score, _article_ranked_at(candidate.article), candidate.article.id)


def rank_articles_for_digest(session: Session, limit: int = 10, user_id: int | None = None) -> list[RankedArticle]:
    clamped_limit = max(1, limit)
    preference_weights = _get_user_preference_weights(session, user_id)
    rows = session.execute(
        select(Article, ArticleSource.name).join(ArticleSource, Article.source_id == ArticleSource.id)
    ).all()
    if not rows:
        return []

    newest_ranked_at = max(_article_ranked_at(article) for article, _source_name in rows)
    candidates: list[RankedArticle] = []
    for article, source_name in rows:
        topics = _get_article_topics(session, article.id)
        base_breakdown = _without_source_penalty(topics, preference_weights)
        candidates.append(
            RankedArticle(
                article=article,
                source_name=source_name,
                topics=topics,
                score_breakdown=ScoreBreakdown(
                    topic_score=base_breakdown.topic_score,
                    preference_score=base_breakdown.preference_score,
                    freshness_score=_score_freshness(article, newest_ranked_at),
                ),
            )
        )

    return _apply_source_diversity(candidates, clamped_limit)
