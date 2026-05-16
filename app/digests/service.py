from sqlalchemy.orm import Session

from app.models.digest import Digest, DigestItem
from app.models.user import User
from app.ranking.service import RankingUserNotFoundError, rank_articles_for_digest


class DigestGenerationError(RuntimeError):
    pass


class DigestUserNotFoundError(LookupError):
    pass


class EmptyDigestError(DigestGenerationError):
    pass


def generate_digest_for_user(session: Session, user_id: int, limit: int = 10) -> Digest:
    """Generate and persist a digest for a user from the current ranked article list."""
    if session.get(User, user_id) is None:
        raise DigestUserNotFoundError("User not found")

    try:
        ranked_articles = rank_articles_for_digest(session, limit=max(1, limit), user_id=user_id)
    except RankingUserNotFoundError as exc:
        raise DigestUserNotFoundError(str(exc)) from exc

    if not ranked_articles:
        raise EmptyDigestError("No ranked articles available for digest")

    try:
        digest = Digest(user_id=user_id)
        session.add(digest)
        session.flush()

        for rank, ranked_article in enumerate(ranked_articles, start=1):
            session.add(DigestItem(digest_id=digest.id, article_id=ranked_article.article.id, rank=rank))

        session.commit()
        session.refresh(digest)
        return digest
    except Exception:
        session.rollback()
        raise
