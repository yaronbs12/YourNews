# YourNews

YourNews is a personalized news recommendation backend focused on a data pipeline and feedback-driven personalization.

## Stack
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic Settings
- Docker Compose
- pytest
- feedparser

## Quick start
1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Start services:
   ```bash
   docker compose up --build
   ```
3. Health check:
   - `GET http://localhost:8000/health`

## Migrations
Run migrations in app container:
```bash
docker compose exec app alembic upgrade head
```

## Local test run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Current scope
Implemented backend skeleton, schema foundation, and MVP RSS ingestion. Hacker News ingestion, AI summaries, and frontend are not implemented yet.

## Demo workflow
Run this workflow to exercise the MVP end-to-end with seeded RSS sources, ingestion, topic classification, feedback-driven preferences, and personalized digest ranking.

```bash
docker compose up --build
docker compose exec app alembic upgrade head
docker compose exec app python -m app.demo.run_demo
```

The demo script creates or reuses `demo@yournews.local`, seeds default RSS sources, ingests enabled RSS feeds, classifies unclassified articles, submits sample positive/negative feedback when candidate articles are available, and prints the demo user's current preferences plus the top 5 personalized digest items. It is safe to run repeatedly: it does not delete data, though feedback and preference weights may accumulate between runs.

After the script prints the demo user id, inspect these endpoints:

- `http://localhost:8000/sources`
- `http://localhost:8000/articles?limit=10`
- `http://localhost:8000/users`
- `http://localhost:8000/users/{user_id}/preferences`
- `http://localhost:8000/digest/preview?user_id={user_id}`
