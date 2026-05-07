from app.classification.service import classify_unclassified_articles
from app.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        count = classify_unclassified_articles(session)
    print(f"Classified {count} articles.")


if __name__ == "__main__":
    main()
