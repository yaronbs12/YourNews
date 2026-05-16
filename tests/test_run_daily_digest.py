from unittest.mock import patch

import pytest

from app.pipeline.daily_digest import DailyDigestPipelineSummary
from app.pipeline.run_daily_digest import main


def test_run_daily_digest_cli_passes_arguments_and_prints_summary(capsys) -> None:
    summary = DailyDigestPipelineSummary(
        rss_sources_processed=2,
        rss_articles_inserted=5,
        hn_articles_inserted=3,
        articles_classified=4,
        users_processed=2,
        digests_created=1,
        users_skipped=1,
    )

    with patch("sys.argv", ["run_daily_digest", "--limit-per-user", "7", "--hn-limit", "11"]):
        with patch("app.pipeline.run_daily_digest.SessionLocal") as session_local:
            with patch("app.pipeline.run_daily_digest.run_daily_digest_pipeline", return_value=summary) as run_pipeline:
                main()

    session = session_local.return_value.__enter__.return_value
    run_pipeline.assert_called_once_with(session, limit_per_user=7, hn_limit=11)
    output = capsys.readouterr().out
    assert "Daily digest pipeline complete" in output
    assert "Rss sources processed: 2" in output
    assert "Digests created: 1" in output
    assert "Users skipped: 1" in output


def test_run_daily_digest_cli_rejects_invalid_limits() -> None:
    with patch("sys.argv", ["run_daily_digest", "--limit-per-user", "0"]):
        with pytest.raises(SystemExit):
            main()

    with patch("sys.argv", ["run_daily_digest", "--hn-limit", "-1"]):
        with pytest.raises(SystemExit):
            main()
