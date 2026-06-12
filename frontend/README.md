# Masar Frontend

Next.js frontend for the Masar v2 rebuild. The app has two text-only pages:

- `/review` - AI Reviewer ranks country/platform combinations with fit scores, confidence, component bars, and evidence.
- `/personalize` - Personalized Targeter generates delivery reports for selected countries and platforms.

Image and video inputs were intentionally removed from this version so the product can focus on grounded text analysis and cited recommendations.

## Stack

- Next.js 14 App Router
- React 18
- TypeScript
- Tailwind CSS 3.4
- Axios
- Recharts 2.x

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. The root path redirects to `/review`.

## Environment

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
```

When `NEXT_PUBLIC_USE_MOCKS=true`, the app loads:

```text
public/mocks/review_response.json
public/mocks/personalize_response.json
```

When mocks are disabled, the app calls:

```text
POST ${NEXT_PUBLIC_BACKEND_URL}/api/review
POST ${NEXT_PUBLIC_BACKEND_URL}/api/personalize
```

No UI code changes should be needed when switching from mocks to the backend if the frozen contracts are honored.
