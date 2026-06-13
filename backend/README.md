# Stars of Science — Backend (v3)

FastAPI service powering the AI Reviewer (platform Fit Score ranking plus country audience-fit heatmap) and Target an Audience (localized delivery plans).

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
# MOCK_MODE=true works with no keys — both pages are fully functional
# set GEMINI_API_KEYS and/or GROQ_API_KEY for live LLM enrichment
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
| GET | `/health` | Health check, mock mode flag, last sync info, per-platform post counts |
| POST | `/api/review` | Rank all 5 Stars of Science platforms, return full platform list with Fit Scores |
| POST | `/api/review/country-fit` | Blend review scores with country usage evidence and return audience-fit scores for supported countries |
| POST | `/api/review/report` | Deep platform report: analysis, strengths, risks, recommendations, evidence |
| POST | `/api/personalize` | Localized delivery reports for selected countries/platforms |
| POST | `/api/admin/stars/sync` | Refresh the Stars of Science post store (runs per-platform adapters) |
| GET | `/api/admin/status` | Per-platform post counts, last sync time, and any sync error state |

### Quick test

```bash
curl http://localhost:8000/health

curl -s -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"idea_text": "A Jordanian student shows her water-purification prototype.", "goal": "applications"}' \
  | python3 -m json.tool
```

## Fit Score formula (AI Reviewer)

```
fit_score = 100 × (
  0.30 × semantic_match
  0.20 × content_platform_fit
  0.16 × performance_strength
  0.10 × language_fit
  0.10 × goal_alignment
  0.14 × duration_fit
)
```

| Component | Weight | Source |
|-----------|--------|--------|
| semantic_match | 0.30 | Lexical overlap with matched Stars of Science posts |
| content_platform_fit | 0.20 | KB content-type × platform fit table |
| performance_strength | 0.16 | Relative engagement of top matched posts |
| language_fit | 0.10 | Arabic / bilingual / English delivery match |
| goal_alignment | 0.10 | Platform's goal-specific strength from platform fit map |
| duration_fit | 0.14 | Long-form / short-form signal detected in idea text |

## Architecture

```
app/main.py              FastAPI app, CORS, routes
app/schemas.py           Pydantic v2 models
app/review.py            POST /api/review and /api/review/report handlers
app/personalize.py       POST /api/personalize handler
app/scoring.py           confidence()
app/llm_client.py        Gemini-first/Groq-fallback wrapper with key rotation; Fanar for Arabic
app/kb_client.py         Thin wrapper over kb/ package
app/evidence_helpers.py  Evidence assembly, deduplication, and merge utilities
kb/knowledge_base.py     SQLite KB — country/platform usage, content-type fit
kb/evidence.py           Stars post + Tavily + Serper evidence retrieval, SQLite cache
kb/stars_intelligence.py Stars of Science post store — SQLite, seed ingestion, platform scoring
kb/platform_adapters.py  Per-platform adapter stubs (seed fallback; wire live fetches when keys exist)
data/stars_posts_seed.json 25 official Stars of Science posts across 5 platforms
data/kb_seed.json        10 countries, 5 platforms, 50 usage rows, 30 fit rows
```

## Mock mode

Set `MOCK_MODE=true` in `.env` to run the full pipeline with zero API keys.
All scoring, ranking, and report generation uses rule-based fallbacks.

Optional flags:
- `USE_LLM_ENRICHMENT=true` enables LLM-generated delivery-plan enrichment (Gemini/Groq).
- `USE_LLM_EVIDENCE_SCORING=true` enables a second-pass evidence relevance scorer.
- `LLM_PROVIDER_ORDER=gemini,groq` controls provider priority; include `fanar` for Arabic caption refinement.
