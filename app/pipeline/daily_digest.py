from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.service import classify_unclassified_articles
from app.digests.service import EmptyDigestError, generate_digest_for_user
from app.ingestion.service import ingest_enabled_rss_sources, ingest_hacker_news_stories
from app.models.user import User


@dataclass(frozen=True)
class DailyDigestPipelineSummary:
    rss_sources_processed: int
    rss_articles_inserted: int
    hn_articles_inserted: int
    articles_classified: int
    users_processed: int
    digests_created: int
    users_skipped: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def run_daily_digest_pipeline(
    session: Session,
    limit_per_user: int = 10,
    hn_limit: int = 30,
) -> DailyDigestPipelineSummary:
    rss_results = ingest_enabled_rss_sources(session)
    hn_articles_inserted = ingest_hacker_news_stories(session, story_type="top", limit=hn_limit)
    articles_classified = classify_unclassified_articles(session)

    users = session.scalars(select(User).order_by(User.id.asc())).all()
    digests_created = 0
    users_skipped = 0

    for user in users:
        try:
            generate_digest_for_user(session, user_id=user.id, limit=limit_per_user)
            digests_created += 1
        except EmptyDigestError:
            users_skipped += 1

    return DailyDigestPipelineSummary(
        rss_sources_processed=len(rss_results),
        rss_articles_inserted=sum(rss_results.values()),
        hn_articles_inserted=hn_articles_inserted,
        articles_classified=articles_classified,
        users_processed=len(users),
        digests_created=digests_created,
        users_skipped=users_skipped,
    )
