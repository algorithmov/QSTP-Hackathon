# QSTP-Hackathon

Masar is an AI content router for the Stars of Science marketing workflow. Given a content draft, optional image/video, topic hint, and campaign goal, it recommends where to publish across Instagram, TikTok, YouTube, LinkedIn, and X by platform, country, language, and local time.

The product is designed to avoid vanity-only reporting. Each recommendation shows a transparent match score, component breakdown, country interest signal, data mode (`live`, `cache`, or `fallback`), and practical publishing guidance.

## One-command local demo

From the repository root:

```bash
./setup.sh
```

This starts all three services:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/health |
| Model service | http://localhost:9000/health |

`setup.sh` checks for Python 3, Node.js, and npm, then delegates to `scripts/run_local.sh`. The local runner creates or repairs Python virtual environments, installs frontend dependencies, creates missing local env files, clears stale processes on ports `9000`, `8000`, and `3000`, and starts the model service, backend, and frontend.

Stop the full stack with `Ctrl+C` in the terminal running `./setup.sh`.

## Architecture

```text
frontend/       Next.js route board, trend ticker, visual profile, MENA choropleth
backend/        FastAPI routing engine, knowledge base, live/cache/fallback signals
model_service/  FastAPI vision analyzer and LightGBM engagement predictor
contracts/      Shared example response contract
scripts/        Local orchestration scripts and runtime logs
```

Core request:

```http
POST /api/route
```

```json
{
  "content_text": "A 30-second clip of a Jordanian student showing her water-purification prototype.",
  "media_url": null,
  "goal": "applications",
  "topic_hint": "young inventors water tech"
}
```

Goals are `applications`, `viewers`, `sponsors`, or `buzz`.

## Data and scoring

The route score is a weighted, explainable decision score:

```text
match_score = platform_fit + audience_fit + geo_fit + timing_fit + language_fit + predicted_engagement
```

The backend returns the score components for every route. Current signal sources include:

- Knowledge-base priors from source-labeled platform and country benchmark rows.
- Google Trends through live provider calls when available.
- SQLite cache and committed fallback snapshots when live trend providers rate-limit.
- Local LightGBM model predictions from the model service.
- Optional LLM explanation generation with fallback to deterministic rule-based copy.

The frontend displays `data_mode` so judges can see whether a route used live data, cached data, or fallback data.

## Demo notes

- The app is configured for local services by default: `MODEL_SERVICE_URL=http://localhost:9000` and `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.
- File uploads are stored in `backend/uploads/` and forwarded to the model service as multipart bytes for visual analysis.
- The MENA panel uses `react-simple-maps` and `world-atlas` country polygons, colored by interest score.
- Route diversity caps prevent the top six recommendations from collapsing into one country.

## API strategy

For the hackathon demo, keep live API dependencies minimal:

- YouTube Data API is the safest live public signal if an API key is available.
- Google Trends is useful but rate-limit prone, so cache and fallback are intentional.
- TikTok, X, and Reddit APIs should be treated as roadmap integrations unless credentials and approvals are already working before demo time.

## Manual checks

Useful validation commands:

```bash
cd frontend && npm run lint && npm run build
cd ../backend && ./.venv/bin/python -m compileall app *.py
cd ../model_service && ./.venv/bin/python -m compileall app *.py
curl http://localhost:8000/health
curl http://localhost:9000/health
```

## Submission requirements

Submission must consist of one folder uploaded to the QSTP Google Drive folder:

1. Product Requirements document: problem definition, solution scope, users, technical architecture, and success metrics.
2. MVP link: a working demonstration accessible through the submitted link.
3. Pitch deck: visual narrative covering problem, solution, demo walkthrough, impact, and scalability.
4. Pitch video: recorded walkthrough of the product for asynchronous judging.

Submission deadline: Saturday 11:59 PM.
