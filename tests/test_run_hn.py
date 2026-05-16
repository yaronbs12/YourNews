from unittest.mock import patch

import pytest

from app.ingestion.run_hn import main


def test_run_hn_passes_story_type_and_limit_to_ingestion(capsys) -> None:
    with patch("sys.argv", ["run_hn", "--type", "best", "--limit", "7"]):
        with patch("app.ingestion.run_hn.SessionLocal") as session_local:
            with patch("app.ingestion.run_hn.ingest_hacker_news_stories", return_value=3) as ingest:
                main()

    ingest.assert_called_once_with(session_local.return_value.__enter__.return_value, story_type="best", limit=7)
    assert "Inserted 3 new Hacker News articles from best stories." in capsys.readouterr().out


def test_run_hn_rejects_negative_limit() -> None:
    with patch("sys.argv", ["run_hn", "--limit", "-1"]):
        with pytest.raises(SystemExit):
            main()
