# Masar

Masar is an evidence-backed decision layer for Stars of Science social distribution. It helps judges and operators move from a raw content idea to three concrete outputs: the best official platform, the strongest countries for that idea, and a localized posting plan for the chosen route.

## What judges should look at

Masar is built around three pages:

| Page | Purpose |
| --- | --- |
| `/review` | Scores and ranks the five official Stars of Science platforms, then shows a country choropleth of where the idea is strongest by audience fit. |
| `/personalize` | Generates localized delivery plans by country and platform: hook, caption, hashtags, timing, and do/don’t guidance. |
| `/about` | Explains the product, methodology, evidence model, and recommended judge demo path. |

## What is new in this version

- Stronger product shell and cleaner navigation across three pages
- Guided review dashboard instead of one long stacked report
- Platform ranking overview that keeps all five scores visible at once
- Evidence-backed country heatmap on the reviewer page
- More prominent media upload flow for Gemini-assisted context extraction
- Judge-facing About page and repo documentation

## How Masar makes decisions

### 1. Platform ranking

The reviewer scores only the five official Stars of Science platforms:

- TikTok
- Instagram
- YouTube
- LinkedIn
- X

The fit score blends:

- semantic match with similar Stars of Science posts
- content-type to platform fit
- performance strength from matched posts
- language fit
- goal alignment
- duration fit

### 2. Country audience fit

The country choropleth does not use a separate disconnected heuristic. It takes the current platform review result and uses those platform scores as weights, then blends them with country-specific platform usage scores from the local knowledge base. The output is an `audience_fit_score` per supported country plus:

- strongest contributing platform
- breakdown by platform contribution
- supporting evidence

### 3. Localized delivery plans

After the user chooses countries and platforms, Masar generates:

- recommended format
- localized hook
- caption
- hashtags
- best posting time
- recommended day window
- country-specific do/don’t guidance

## Why this matters for Stars of Science

Masar is not a generic social media recommender. It is intentionally constrained to the Stars of Science operating context:

- the five official channels
- Stars of Science post evidence
- country-level audience usage references
- judge-friendly transparency through evidence disclosures

That gives the product a clearer evaluation story: it ranks, explains, localizes, and exposes the evidence behind each recommendation.

## Judge demo script

1. Start on `/review`.
2. Paste the seeded idea already shown in the UI.
3. Run the review and inspect the top-ranked platform.
4. Compare the five platform scores in the ranking overview.
5. Hover the country map and inspect the audience fit breakdown and evidence.
6. Open one platform’s score breakdown and deep report.
7. Move to `/personalize`.
8. Generate a delivery plan for selected countries and platforms.
9. Open `/about` for the methodology and product summary.

## Local run

### One-command startup

```bash
./setup.sh
```

This installs dependencies if needed, starts:

- backend on `http://localhost:8000`
- frontend on `http://localhost:3000`

### Frontend-only

```bash
cd frontend
npm install
npm run dev
```

### Backend-only

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Mock mode vs live mode

By default, the project can run in mock mode for a stable demo:

- frontend reads seeded mock responses
- backend can run without live provider keys

To use live model-backed behavior, configure backend keys and disable frontend mocks as needed.

## Architecture summary

```text
frontend/   Next.js 14 App Router, TypeScript, Tailwind CSS
backend/    FastAPI, Pydantic, scoring logic, Gemini/Groq integration hooks
backend/kb/ SQLite-backed country/platform usage and Stars of Science evidence layer
```

Key implementation pieces:

- `frontend/app/review/page.tsx` — platform ranking dashboard + country choropleth
- `frontend/app/personalize/page.tsx` — localized delivery planner
- `frontend/app/about/page.tsx` — judge-facing explanation page
- `backend/app/review.py` — review scoring and country-fit generation
- `backend/app/personalize.py` — country/platform delivery-plan generation

## Verification expectation

This version should be checked by:

- running `next build` in the frontend
- compiling backend Python modules
- exercising `/review`, `/personalize`, and `/about`
- verifying ranking, map, modal, and upload flows in the browser
