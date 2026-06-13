# Masar

## Abstract

Masar is a decision support system for Stars of Science social distribution. It takes one content idea and returns three practical outputs:

- the best official platform for that idea
- the strongest target countries for that idea
- a localized posting plan for the chosen countries and platforms

The system is evidence-based. It does not score all social platforms on the internet. It only works inside the Stars of Science operating scope and uses matched records, country usage references, and clear scoring rules.

## Objective

The project answers a simple operational question:

How should a Stars of Science idea be distributed so it has the best chance to reach the right audience at the right time?

Masar is built to help judges, operators, and campaign teams move from a rough idea to a grounded posting decision.

## Scope

Masar is intentionally narrow. This is a feature, not a limitation.

It is constrained to:

- the five official Stars of Science platforms
- the local knowledge base included in this repository
- audience fit across supported Arab-market countries
- transparent reasoning with evidence shown in the interface

The five scored platforms are: TikTok, Instagram, YouTube LinkedIn & X

## System Outputs

### 1. Platform review

The `/review` page ranks the five official platforms and explains the ranking with:

- fit score, confidence level, score breakdown, supporting patterns, deep report & evidence disclosure

### 2. Country targeting

The same review flow estimates where the idea is strongest by country. Country scores are not guessed in isolation. They are derived from the current platform result and blended with country-level platform usage signals from the knowledge base.

### 3. Delivery plan

The `/personalize` page generates localized delivery reports for selected countries and platforms. Each report includes:

- recommended format, hook, caption, hashtags, posting time, recommended day window, do guidance, do not guidance &supporting evidence

## Method

Masar uses a simple and inspectable method.

### Step 1. Summarize the idea

The system extracts the core topic, content type, audience, and language direction from the input idea.

### Step 2. Match related records

The system looks for related Stars of Science records and platform patterns in the local data layer.

### Step 3. Score platform fit

Each platform score blends:

- semantic match, format fit, performance strength, goal alignment, language fit & duration fit

### Step 4. Blend country fit

Country audience fit uses the current platform result as an input. Stronger platforms contribute more weight. This keeps the country result tied to the actual review outcome.

### Step 5. Generate localized guidance

For selected country and platform pairs, Masar creates delivery guidance that stays aligned with the review result and attached evidence.

## Product Structure

The current product surface has two main pages:

| Route | Purpose |
| --- | --- |
| `/review` | Review one idea, rank the platforms, inspect evidence, and open deep reports. |
| `/personalize` | Generate localized posting plans for selected countries and platforms. |

## Repository Structure

```text
frontend/   Next.js 14, TypeScript, Tailwind CSS
backend/    FastAPI, Pydantic, scoring and report logic
backend/kb/ Local knowledge base, evidence helpers, platform and country data
contracts/  Example response contracts
scripts/    Local startup and utility scripts
```

## Run Locally

### One-command startup

```bash
./setup.sh
```

This starts:

- backend at `http://localhost:8000`
- frontend at `http://localhost:3000`


## Runtime Modes

Masar supports two operating modes.

### 1. Mock mode

Mock mode is the default demo path.

- the frontend reads seeded mock review and personalize responses
- the backend can run without model keys
- the system remains stable for presentations and judge demos

### 2. Live mode

Live mode uses configured model providers and live backend execution. To enable live behavior:

1. add backend keys in `backend/.env`
2. set `NEXT_PUBLIC_USE_MOCKS=false` in `frontend/.env.local`

## Demo Protocol

For a clean demo:

1. Open `http://localhost:3000/review`.
2. Use the seeded idea or paste a new one.
3. Run the review.
4. Inspect the top-ranked platform.
5. Open score breakdown and deep report.
6. Move to `/personalize`.
7. Choose countries and platforms.
8. Generate the localized delivery plan.

## Design Principles

The system follows four design principles:

- narrow scope over broad but vague recommendations
- evidence before opinion
- simple outputs for operational use
- clear reasoning that a judge can inspect quickly

## Current Limitations

- the product is limited to the five official Stars of Science platforms
- output quality depends on the local evidence layer and configured providers
- mock mode is best for stable demos, not for testing live provider quality
- country targeting is only available for the supported country set in the repository

## Verification

Recommended checks:

- run `npm run build` inside `frontend`
- compile backend Python modules
- test `/review` and `/personalize`
- verify ranking, deep report, and localization flows
- confirm mock mode and live mode behavior when switching environments

## Conclusion

Masar is not a general social media assistant. It is a focused decision layer for one real operating context. That focus makes the system easier to test, easier to explain, and more useful for Stars of Science campaign decisions.
