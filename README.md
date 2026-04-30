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
Implemented only backend skeleton and schema foundation. No RSS ingestion, Hacker News ingestion, AI summaries, or frontend yet.
