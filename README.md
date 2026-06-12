# QSTP-Hackathon — Masar v2

Masar is an AI content co-pilot for Stars of Science marketing. It takes a text idea and campaign goal, then produces ranked platform and country recommendations with a transparent Fit Score and evidence-backed reasoning, plus fully localized delivery plans with dialect-appropriate captions.

## Two-page product

| Page | URL | What it does |
|---|---|---|
| AI Reviewer | `/review` | Ranks country + platform combinations by Fit Score, shows score breakdown and cited evidence |
| Personalized Targeter | `/personalize` | Generates ready-to-use delivery plans: format, hook, caption (RTL where needed), hashtags, best time, dos/don'ts |

## One-command local start

```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

This installs all dependencies, starts the backend (`:8000`) and frontend (`:3000`), and opens the app. Press `Ctrl+C` to stop.

By default `MOCK_MODE=true` in `backend/.env` — both pages work instantly with no API keys. To enable live LLM calls, set `GROQ_API_KEY` and `GROQ_MODEL=llama-3.3-70b-versatile` in `backend/.env` and set `MOCK_MODE=false`.

## Architecture

```
frontend/       Next.js 14 App Router — two pages, mock-ready
backend/
  app/          FastAPI, two endpoints, Groq LLM, scoring formula
  kb/           Knowledge base package (SQLite + Tavily evidence)
  data/         kb_seed.json (50 usage rows, 30 fit rows), fallback evidence
contracts/      Frozen example responses for both endpoints
scripts/        run_local.sh, log files
```

## Fit Score formula

```
fit_score = 100 × (0.30 × topic_relevance + 0.25 × audience_fit + 0.20 × platform_fit + 0.15 × language_fit + 0.10 × timing_fit)
```

Every number is traceable: `platform_fit` comes from the KB's content-type/platform table, `audience_fit` from the platform usage score weighted by goal preference, `language_fit` from the detected idea language, `timing_fit` from peak hours in the KB. `topic_relevance` starts at the usage score baseline and is adjusted ±0.15 when live Tavily evidence is available. `confidence` is `high` when evidence was used, `medium` when not but usage score ≥ 0.6, `low` otherwise.

## API endpoints

**`POST /api/review`** — returns ranked country/platform list with Fit Scores, component breakdown, why lines, and cited evidence.

**`POST /api/personalize`** — accepts up to 3 countries + 2 platforms, returns a localized delivery report per pair: format, hook, dialect caption with RTL/LTR direction, hashtags, post time, dos/don'ts.

**`GET /health`** — service status and mock mode flag.

## Stack

- **Backend**: Python 3.11, FastAPI, Pydantic v2, Groq SDK (Llama 3.3 70B), Tavily search, SQLite KB
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Recharts, Axios
- **LLM**: Groq free tier — Llama 3.3 70B primary, Llama 3.1 8B fallback
- **Evidence**: Tavily free tier — 1000 credits/month, SQLite-cached with 24-hour TTL

## Submission requirements

1. Product Requirements document
2. MVP link (working demo)
3. Pitch deck
4. Pitch video

Deadline: Saturday 11:59 PM
