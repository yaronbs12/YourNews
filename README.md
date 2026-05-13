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
4. Open the MVP dashboard:
   - `http://127.0.0.1:8000/`

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
Implemented backend skeleton, schema foundation, MVP RSS ingestion, topic classification, feedback-driven personalization, digest preview, and a minimal static frontend dashboard. Hacker News ingestion, AI summaries, authentication, and deployment are not implemented yet.


## MVP dashboard
Open the dashboard after starting the FastAPI app:

```text
http://127.0.0.1:8000/
```

Basic dashboard flow:

1. Enter an email address and click **Create / reuse user**. The dashboard calls `POST /users` and shows a friendly signed-in message.
2. Click **Load digest** to fetch `GET /digest/preview?user_id={user_id}` and inspect ranked articles with title, source, and topics.
3. Click **Interesting**, **Neutral**, or **Not interesting** on digest items to send `POST /feedback`; the dashboard then refreshes preferences and digest results automatically.
4. Click **Reload preferences** any time to manually refresh `GET /users/{user_id}/preferences` and inspect topic weights.
5. Use **Load digest** again whenever you want to manually reload feedback-adjusted ranking.
6. Use **Load recent** to inspect `GET /articles?limit=20`.

The dashboard is intentionally MVP-simple: static HTML/CSS/JavaScript served by FastAPI, with no build step, authentication, or external JavaScript dependencies.

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

## Manual personalization test
Use this flow when you want to manually verify feedback-driven personalization without running the demo script again. The examples use `curl.exe` syntax that works in Windows PowerShell; replace `{user_id}`, `{interesting_article_id}`, and `{not_interesting_article_id}` with values from your local data.

1. Create or reuse a test user:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/users `
     -H "Content-Type: application/json" `
     -d "{\"email\":\"demo@yournews.local\"}"
   ```

2. Inspect recent articles and choose two different `article_id` values:
   ```powershell
   curl.exe "http://127.0.0.1:8000/articles?limit=10"
   ```

3. Send positive feedback for one article:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/feedback `
     -H "Content-Type: application/json" `
     -d "{\"user_id\":{user_id},\"article_id\":{interesting_article_id},\"label\":\"INTERESTING\"}"
   ```

4. Send negative feedback for a different article:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/feedback `
     -H "Content-Type: application/json" `
     -d "{\"user_id\":{user_id},\"article_id\":{not_interesting_article_id},\"label\":\"NOT_INTERESTING\"}"
   ```

5. Inspect the raw feedback rows, accumulated preferences, and personalized digest:
   ```powershell
   curl.exe "http://127.0.0.1:8000/feedback?user_id={user_id}"
   curl.exe "http://127.0.0.1:8000/users/{user_id}/preferences"
   curl.exe "http://127.0.0.1:8000/digest/preview?user_id={user_id}"
   ```
