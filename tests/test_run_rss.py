from unittest.mock import patch

from app.ingestion.run_rss import main


def test_run_rss_all_mode_calls_ingest_enabled_sources(capsys) -> None:
    with patch("sys.argv", ["run_rss", "--all"]):
        with patch("app.ingestion.run_rss.SessionLocal") as session_local:
            with patch("app.ingestion.run_rss.ingest_enabled_rss_sources", return_value={"Feed A": 2, "Feed B": 1}) as ingest_all:
                main()

    ingest_all.assert_called_once_with(session_local.return_value.__enter__.return_value)
    assert "Inserted 3 new articles across 2 sources." in capsys.readouterr().out


def test_run_rss_single_feed_mode_still_works(capsys) -> None:
    with patch("sys.argv", ["run_rss", "https://example.com/rss.xml"]):
        with patch("app.ingestion.run_rss.SessionLocal") as session_local:
            with patch("app.ingestion.run_rss.ingest_rss_feed", return_value=4) as ingest_one:
                main()

    ingest_one.assert_called_once_with(session_local.return_value.__enter__.return_value, "https://example.com/rss.xml")
    assert "Inserted 4 new articles." in capsys.readouterr().out
