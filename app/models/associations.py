from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArticleTopic(Base):
    __tablename__ = "article_topics"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    relevance_score: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
