# YourNews MVP Demo Runbook

## 1) Start with Docker
```bash
docker compose up -d --build
```

## 2) Run migrations
```bash
docker compose exec app alembic upgrade head
```

## 3) Seed demo data
```bash
docker compose exec app python -m app.pipeline.run_demo
```

## 4) Run the daily pipeline
```bash
docker compose exec app python -m app.pipeline.run_daily_digest --limit-per-user 10 --hn-limit 30
```

## 5) Generate a digest
```bash
curl -X POST "http://127.0.0.1:8000/digests/generate?user_id=1&limit=10"
```

## 6) Send digest (local mode)
Set `EMAIL_PROVIDER=local` then:
```bash
curl -X POST "http://127.0.0.1:8000/digests/1/send"
```

## 7) Send digest with real SMTP
Set these env vars (for Docker, add to `.env` before `docker compose up`):
- `EMAIL_PROVIDER=smtp`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_USE_TLS`
- `APP_BASE_URL` (must be a reachable URL for feedback links)

Then send:
```bash
curl -X POST "http://127.0.0.1:8000/digests/1/send"
```

## 8) Test feedback links locally
1. Get a delivery record: `GET /digests/{digest_id}/deliveries`
2. Copy any `Interesting` / `Neutral` / `Not interesting` link from `html_body` or `text_body`.
3. Open it in the browser.
4. Confirm the HTML page says feedback was saved.
5. Regenerate a digest and verify ranking changes.

## Security note
Never commit real SMTP credentials. Keep real values only in local `.env` or secret managers.
