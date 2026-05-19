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
docker compose exec app python -m app.demo.run_demo
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

## Real email setup with Gmail SMTP
1. Copy `.env.smtp.example` to `.env`.
2. Replace `SMTP_PASSWORD=************` with your Google App Password in local `.env`.
3. Keep `SMTP_USERNAME` and `SMTP_FROM_EMAIL` as `yaronbs12@gmail.com`.
4. Run `docker compose down`.
5. Run `docker compose up --build`.
6. Run migrations.
7. Create or reuse a user with a real recipient email.
8. Generate a digest.
9. Send the digest.
10. Open the received email.
11. Click `Interesting` / `Neutral` / `Not interesting`.
12. Confirm the “Thanks, your feedback was saved.” page appears.

> Note: `APP_BASE_URL=http://127.0.0.1:8000` works only when opening feedback links on the same machine running the backend. For external recipients, `APP_BASE_URL` must be a public URL such as ngrok or a deployed backend URL.

## Security note
Never commit real SMTP credentials. Keep real values only in local `.env` or secret managers.
