from unittest.mock import patch

from app.classification.run_topics import main


def test_run_topics_calls_classification_service(capsys) -> None:
    with patch("app.classification.run_topics.SessionLocal") as session_local:
        with patch("app.classification.run_topics.classify_unclassified_articles", return_value=5) as classify:
            main()

    classify.assert_called_once_with(session_local.return_value.__enter__.return_value)
    assert "Classified 5 articles." in capsys.readouterr().out
