import argparse

from app.db.session import SessionLocal
from app.ingestion.service import ingest_enabled_rss_sources, ingest_rss_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest articles from an RSS feed.")
    parser.add_argument("feed_url", nargs="?", help="RSS feed URL to ingest")
    parser.add_argument("--all", action="store_true", help="Ingest all enabled RSS sources")
    args = parser.parse_args()
    if args.all and args.feed_url:
        parser.error("feed_url cannot be used with --all")
    if not args.all and not args.feed_url:
        parser.error("feed_url is required unless --all is provided")

    with SessionLocal() as session:
        if args.all:
            inserted_counts = ingest_enabled_rss_sources(session)
            total = sum(inserted_counts.values())
            print(f"Inserted {total} new articles across {len(inserted_counts)} sources.")
            return

        inserted_count = ingest_rss_feed(session, args.feed_url)

    print(f"Inserted {inserted_count} new articles.")


if __name__ == "__main__":
    main()
