# YourNews API Examples

These examples assume the API is running locally at `http://127.0.0.1:8000`.

## Health

```bash
curl http://127.0.0.1:8000/health
```

## Users

Create or reuse a user:

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@yournews.local"}'
```

List users:

```bash
curl http://127.0.0.1:8000/users
```

List user preferences:

```bash
curl http://127.0.0.1:8000/users/{user_id}/preferences
```

## Articles and sources

List recent articles:

```bash
curl "http://127.0.0.1:8000/articles?limit=10"
```

List sources:

```bash
curl http://127.0.0.1:8000/sources
```

## Digest preview

Preview a ranked digest without persistence:

```bash
curl "http://127.0.0.1:8000/digest/preview?user_id={user_id}&limit=10"
```

The response includes topics and Ranking v2 score breakdowns.

## Persisted digests

Generate a persisted digest:

```bash
curl -X POST "http://127.0.0.1:8000/digests/generate?user_id={user_id}&limit=10"
```

Read a persisted digest:

```bash
curl "http://127.0.0.1:8000/digests/{digest_id}"
```

List saved digests for a user:

```bash
curl "http://127.0.0.1:8000/users/{user_id}/digests"
```

## Feedback

Submit positive feedback:

```bash
curl -X POST http://127.0.0.1:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"article_id":1,"label":"INTERESTING"}'
```

Submit negative feedback:

```bash
curl -X POST http://127.0.0.1:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"article_id":2,"label":"NOT_INTERESTING"}'
```

List feedback rows:

```bash
curl "http://127.0.0.1:8000/feedback?user_id={user_id}"
```

## Pipeline commands

Run Hacker News ingestion only:

```bash
python -m app.ingestion.run_hn --type top --limit 30
```

Run topic classification only:

```bash
python -m app.classification.run_topics
```

Run the full daily digest pipeline:

```bash
python -m app.pipeline.run_daily_digest --limit-per-user 10 --hn-limit 30
```
