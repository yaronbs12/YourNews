from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.classification.rules import TOPIC_KEYWORDS
from app.models.article import Article
from app.models.associations import ArticleTopic
from app.models.topic import Topic


def classify_article_text(title: str, content: str | None) -> list[str]:
    text = f"{title} {content or ''}".lower()
    scores: dict[str, int] = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > 0:
            scores[topic] = score

    if not scores:
        return ["general"]

    return [name for name, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def classify_unclassified_articles(session: Session, limit: int = 100) -> int:
    clamped_limit = max(1, min(limit, 1000))
    articles = session.scalars(
        select(Article)
        .where(~exists(select(1).where(ArticleTopic.article_id == Article.id)))
        .order_by(Article.id.asc())
        .limit(clamped_limit)
    ).all()

    classified_count = 0
    for article in articles:
        topic_names = classify_article_text(article.title, article.content)
        for rank, topic_name in enumerate(topic_names, start=1):
            topic = session.scalar(select(Topic).where(Topic.name == topic_name))
            if topic is None:
                topic = Topic(name=topic_name)
                session.add(topic)
                session.flush()

            session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, relevance_score=max(1, 10 - rank)))

        classified_count += 1

    session.commit()
    return classified_count
