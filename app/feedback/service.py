from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.associations import ArticleTopic
from app.models.feedback import Feedback, FeedbackType
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference

FEEDBACK_WEIGHT_DELTAS: dict[FeedbackType, int] = {
    FeedbackType.INTERESTING: 2,
    FeedbackType.NEUTRAL: 0,
    FeedbackType.NOT_INTERESTING: -2,
}


class FeedbackValidationError(ValueError):
    pass


class FeedbackNotFoundError(LookupError):
    pass


def _parse_feedback_label(label: str) -> FeedbackType:
    try:
        return FeedbackType[label]
    except KeyError as exc:
        raise FeedbackValidationError("Invalid feedback label") from exc


def create_feedback_and_update_preferences(session: Session, user_id: int, article_id: int, label: str) -> Feedback:
    user = session.get(User, user_id)
    if user is None:
        raise FeedbackNotFoundError("User not found")

    article = session.get(Article, article_id)
    if article is None:
        raise FeedbackNotFoundError("Article not found")

    feedback_type = _parse_feedback_label(label)
    feedback = Feedback(user_id=user_id, article_id=article_id, label=feedback_type)
    session.add(feedback)

    delta = FEEDBACK_WEIGHT_DELTAS[feedback_type]
    topics = session.scalars(
        select(Topic)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
    ).all()
    for topic in topics:
        preference = session.scalar(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.topic_id == topic.id,
            )
        )
        if preference is None:
            preference = UserPreference(user_id=user_id, topic_id=topic.id, weight=0)
            session.add(preference)
            session.flush()
        preference.weight += delta

    session.commit()
    session.refresh(feedback)
    return feedback
