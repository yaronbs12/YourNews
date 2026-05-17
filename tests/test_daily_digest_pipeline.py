from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.digests.service import EmptyDigestError
from app.pipeline.daily_digest import run_daily_digest_pipeline


def _session_with_users(*user_ids: int) -> Mock:
    session = Mock()
    session.scalars.return_value.all.return_value = [SimpleNamespace(id=user_id) for user_id in user_ids]
    return session


def test_daily_digest_pipeline_successful_end_to_end_with_mocked_services() -> None:
    session = _session_with_users(1, 2)

    with patch("app.pipeline.daily_digest.ingest_enabled_rss_sources", return_value={"Feed A": 2, "Feed B": 0}) as rss:
        with patch("app.pipeline.daily_digest.ingest_hacker_news_stories", return_value=3) as hn:
            with patch("app.pipeline.daily_digest.classify_unclassified_articles", return_value=4) as classify:
                with patch("app.pipeline.daily_digest.generate_digest_for_user") as generate:
                    summary = run_daily_digest_pipeline(session, limit_per_user=5, hn_limit=12)

    rss.assert_called_once_with(session)
    hn.assert_called_once_with(session, story_type="top", limit=12)
    classify.assert_called_once_with(session)
    assert generate.call_count == 2
    generate.assert_any_call(session, user_id=1, limit=5)
    generate.assert_any_call(session, user_id=2, limit=5)
    assert summary.to_dict() == {
        "rss_sources_processed": 2,
        "rss_articles_inserted": 2,
        "hn_articles_inserted": 3,
        "articles_classified": 4,
        "users_processed": 2,
        "digests_created": 2,
        "users_skipped": 0,
    }


def test_daily_digest_pipeline_skips_users_when_digest_generation_is_empty() -> None:
    session = _session_with_users(1, 2, 3)

    def generate(_session, user_id: int, limit: int) -> None:
        if user_id == 2:
            raise EmptyDigestError("No ranked articles available for digest")

    with patch("app.pipeline.daily_digest.ingest_enabled_rss_sources", return_value={"Feed A": 0}):
        with patch("app.pipeline.daily_digest.ingest_hacker_news_stories", return_value=0):
            with patch("app.pipeline.daily_digest.classify_unclassified_articles", return_value=0):
                with patch("app.pipeline.daily_digest.generate_digest_for_user", side_effect=generate):
                    summary = run_daily_digest_pipeline(session)

    assert summary.digests_created == 2
    assert summary.users_skipped == 1
    assert summary.users_processed == 3


def test_daily_digest_pipeline_unexpected_digest_errors_fail_loudly() -> None:
    session = _session_with_users(1)

    with patch("app.pipeline.daily_digest.ingest_enabled_rss_sources", return_value={}):
        with patch("app.pipeline.daily_digest.ingest_hacker_news_stories", return_value=0):
            with patch("app.pipeline.daily_digest.classify_unclassified_articles", return_value=0):
                with patch("app.pipeline.daily_digest.generate_digest_for_user", side_effect=RuntimeError("boom")):
                    with pytest.raises(RuntimeError, match="boom"):
                        run_daily_digest_pipeline(session)
