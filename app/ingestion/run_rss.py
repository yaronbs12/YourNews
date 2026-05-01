import argparse

from app.db.session import SessionLocal
from app.ingestion.service import ingest_rss_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest articles from an RSS feed.")
    parser.add_argument("feed_url", help="RSS feed URL to ingest")
    args = parser.parse_args()

    with SessionLocal() as session:
        inserted_count = ingest_rss_feed(session, args.feed_url)

    print(f"Inserted {inserted_count} new articles.")


if __name__ == "__main__":
    main()
