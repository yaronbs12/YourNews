import argparse

from app.db.session import SessionLocal
from app.pipeline.daily_digest import DailyDigestPipelineSummary, run_daily_digest_pipeline


def _format_summary(summary: DailyDigestPipelineSummary) -> str:
    lines = ["Daily digest pipeline complete"]
    for key, value in summary.to_dict().items():
        label = key.replace("_", " ").capitalize()
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the YourNews daily digest pipeline.")
    parser.add_argument("--limit-per-user", type=int, default=10, help="Maximum digest items to generate per user")
    parser.add_argument("--hn-limit", type=int, default=30, help="Maximum Hacker News top stories to ingest")
    args = parser.parse_args()

    if args.limit_per_user < 1:
        parser.error("--limit-per-user must be greater than or equal to 1")
    if args.hn_limit < 0:
        parser.error("--hn-limit must be greater than or equal to 0")

    with SessionLocal() as session:
        summary = run_daily_digest_pipeline(
            session,
            limit_per_user=args.limit_per_user,
            hn_limit=args.hn_limit,
        )

    print(_format_summary(summary))


if __name__ == "__main__":
    main()
