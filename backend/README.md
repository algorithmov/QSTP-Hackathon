# Masar Backend

Routing engine for the Masar content router. FastAPI service that accepts a content post + goal, runs the weighted routing pipeline (knowledge base + live trends + model predictions + Claude), and returns a ranked route board.

## Setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copy the env file and fill in your keys:

```bash
cp .env.example .env
# edit .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

With `MOCK_MODE=true` (the default), the full pipeline runs without the model service.

## Test

```bash
curl http://localhost:8000/health

curl -s -X POST http://localhost:8000/api/route \
  -H "Content-Type: application/json" \
  -d '{
    "content_text": "A 30-second clip of a Jordanian student showing her water-purification prototype.",
    "media_url": "uploads/clip123.mp4",
    "goal": "applications",
    "topic_hint": "young inventors water tech"
  }' | python3 -m json.tool
```

## Architecture

```
app/main.py          FastAPI app, /api/route, /api/upload, /health
app/schemas.py       Pydantic v2 models (frozen contracts)
knowledge_base.py    SQLite KB seeded from data/kb_seed.json
live_signals.py      pytrends + YouTube, SQLite cache, JSON fallback
model_client.py      HTTP client for model service, deterministic mock
routing.py           Weighted scoring engine + Claude orchestration
data/kb_seed.json    Knowledge base seed data (real, citable sources)
data/trends_fallback.json  Captured snapshot for demo topics
```

## Scoring weights

| Component           | Weight |
|---------------------|--------|
| platform_fit        | 0.20   |
| audience_fit        | 0.15   |
| geo_fit             | 0.25   |
| timing_fit          | 0.10   |
| language_fit        | 0.10   |
| predicted_engagement| 0.20   |

## Checkpoint 2 (connecting the real model service)

Set in `.env`:

```
MOCK_MODE=false
MODEL_SERVICE_URL=http://<mahmoud-vm-or-ngrok-url>
```

Restart the server. Run the test curl above and confirm `routes` are non-empty.

## Capture live trend fallback before demo

```bash
python -c "from live_signals import capture_fallback; import asyncio; asyncio.run(capture_fallback())"
```

This overwrites `data/trends_fallback.json` with fresh data for the demo topics.
