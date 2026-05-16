import argparse

from app.db.session import SessionLocal
from app.ingestion.hacker_news import HN_STORY_TYPES
from app.ingestion.service import ingest_hacker_news_stories


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest stories from the Hacker News Firebase API.")
    parser.add_argument(
        "--type", default="top", choices=sorted(HN_STORY_TYPES), help="HN story list to ingest"
    )
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of stories to fetch")
    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit must be greater than or equal to 0")

    with SessionLocal() as session:
        inserted_count = ingest_hacker_news_stories(
            session, story_type=args.type, limit=args.limit
        )

    print(f"Inserted {inserted_count} new Hacker News articles from {args.type} stories.")


if __name__ == "__main__":
    main()
