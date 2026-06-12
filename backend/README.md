# Stars of Science — Backend (v2)

FastAPI service that powers the Fit Score ranking and personalized delivery reports.
No model service, no GPU VM — just Gemini/Groq LLM providers + SQLite knowledge base.

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
# set GEMINI_API_KEYS and/or GROQ_API_KEY (optional — MOCK_MODE=true works with no keys)
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Or use the repo helper:

```bash
bash scripts/run_local.sh
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + mock_mode flag |
| POST | `/api/review` | Rank all 10 countries × 5 platforms, return top 8 |
| POST | `/api/personalize` | Generate delivery reports for selected countries/platforms |

### Quick test

```bash
curl http://localhost:8000/health

curl -s -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"idea_text": "A Jordanian student shows her water-purification prototype.", "goal": "applications"}' \
  | python3 -m json.tool
```

## Fit Score formula

```
fit_score = 100 × (0.30×topic + 0.25×audience + 0.20×platform + 0.15×language + 0.10×timing)
```

| Component | Weight | Source |
|-----------|--------|--------|
| topic_relevance | 0.30 | KB usage score ± LLM evidence adjustment |
| audience_fit | 0.25 | KB usage score × goal preference multiplier |
| platform_fit | 0.20 | KB content-type × platform fit |
| language_fit | 0.15 | Derived from suggested language vs Arabic |
| timing_fit | 0.10 | Fixed 0.8 (peak hours used for scheduling) |

## Architecture

```
app/main.py           FastAPI app, lifespan, CORS, routes
app/schemas.py        Pydantic v2 models — frozen contracts A + B
app/review.py         POST /api/review handler
app/personalize.py    POST /api/personalize handler
app/scoring.py        compute_fit_score(), confidence()
app/llm_client.py     Gemini-first/Groq-fallback wrapper with Gemini key rotation
app/kb_client.py      Thin wrapper over kb/ package
kb/knowledge_base.py  SQLite KB, rebuilt from kb_seed.json on first import
kb/evidence.py        Tavily search + SQLite cache + fallback_evidence.json
data/kb_seed.json     10 countries, 5 platforms, 50 usage rows, 30 fit rows
data/fallback_evidence.json  Pre-seeded evidence for demo topics
```

## Mock mode

Set `MOCK_MODE=true` in `.env` to run the full pipeline with zero API keys.
All scoring, ranking, and report generation uses rule-based fallbacks.
