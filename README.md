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
- httpx

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
Implemented backend skeleton, schema foundation, MVP RSS ingestion, Hacker News ingestion, topic classification, feedback-driven personalization, digest preview, and a minimal static frontend dashboard. AI summaries, authentication, and deployment are not implemented yet.


## MVP dashboard
Open the dashboard after starting the FastAPI app:

```text
http://127.0.0.1:8000/
```

Basic dashboard flow:

1. Enter an email address and click **Create / reuse user**. The dashboard calls `POST /users` and shows the selected `user_id`.
2. Click **Load digest** to fetch `GET /digest/preview?user_id={user_id}` and inspect ranked articles with title, source, topics, and `article_id`.
3. Click **Interesting**, **Neutral**, or **Not interesting** on digest items to send `POST /feedback`.
4. Click **Reload preferences** to refresh `GET /users/{user_id}/preferences` and inspect topic weights.
5. Reload the digest to see how feedback-adjusted preferences affect ranking.
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

## Ranking v2 explainability
Digest preview ranking uses a simple deterministic MVP score so each recommendation can explain why it appeared. Every ranked article gets a score breakdown with:

- `topic_score`: the base score from classified article topics such as `ai`, `tech`, or `business`.
- `preference_score`: the user's accumulated feedback preference weights for matching topics.
- `freshness_score`: a small boost for newer articles using `published_at` when available, otherwise `created_at`.
- `source_penalty`: a small diversity penalty applied when earlier digest items already came from the same source.

`GET /digest/preview` returns both the total score and this breakdown for each item, and the dashboard displays the components next to digest articles so it is clear why each article was ranked.

## Hacker News ingestion
YourNews can ingest Hacker News `top`, `new`, or `best` stories through the public Hacker News Firebase API. HN payloads are normalized into the same article ingestion shape used by RSS feeds, then stored through the shared database insertion path so URL deduplication and `ArticleSource` behavior remain consistent.

Run Hacker News ingestion locally after applying migrations:

```bash
python -m app.ingestion.run_hn --type top --limit 30
```

Valid `--type` values are `top`, `new`, and `best`. The command creates or reuses a Hacker News article source with `source_type="hacker_news"`; inserted articles can then be classified and will appear in `GET /articles` and `GET /digest/preview` like RSS articles.

To include Hacker News in the demo-style workflow, run HN ingestion before topic classification or before rerunning the demo inspection endpoints:

```bash
docker compose exec app python -m app.ingestion.run_hn --type top --limit 30
docker compose exec app python -m app.classification.run_topics
```

The existing demo script still seeds and ingests the default RSS sources; HN ingestion is an additional source-type command that can be run before opening `/articles` or `/digest/preview`.

## Persisted digest workflow
`GET /digest/preview` remains a read-only way to inspect the current Ranking v2 order without writing rows. To save a digest for later review, generate a persisted digest for a user:

```bash
curl.exe -X POST "http://127.0.0.1:8000/digests/generate?user_id={user_id}&limit=10"
```

The generate endpoint validates the user, reuses the same Ranking v2 service as preview, creates one `Digest` row, and stores ordered `DigestItem` rows with article ids and ranks. It returns the saved digest with ordered article details:

```bash
curl.exe "http://127.0.0.1:8000/digests/{digest_id}"
```

List saved digests for a user with:

```bash
curl.exe "http://127.0.0.1:8000/users/{user_id}/digests"
```

If there are no ranked articles, generation returns an error instead of creating an empty digest.

## Daily pipeline runner
Run the daily pipeline after migrations when you want one command to execute the full MVP workflow: ingest enabled RSS sources, ingest Hacker News top stories, classify unclassified articles, and generate persisted digests for existing users.

Recommended local Docker workflow:

```bash
docker compose up --build
docker compose exec app alembic upgrade head
docker compose exec app python -m app.pipeline.run_daily_digest --limit-per-user 10 --hn-limit 30
```

The runner prints a summary with RSS sources processed, inserted RSS/HN article counts, classified article count, users processed, digests created, and users skipped. Users are skipped when no digest can be generated, while unexpected errors still fail the run so they can be investigated.

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
