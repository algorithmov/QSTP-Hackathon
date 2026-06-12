# Masar Frontend

Standalone frontend for Masar, the AI content router. It is built to be pasted into the repository's `frontend/` directory and run independently while the backend and model service are integrated later.

## Stack

- Next.js 14 App Router
- React 18
- TypeScript
- Tailwind CSS 3.4
- Axios for the backend call

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

The checked-in local defaults keep the app fully usable without a backend:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
```

When `NEXT_PUBLIC_USE_MOCKS=true`, the app loads `public/mocks/route_response.json` with a short artificial delay. When it is `false`, the app sends the frozen request contract to:

```text
POST ${NEXT_PUBLIC_BACKEND_URL}/api/route
```

## Contract

The frontend sends:

```json
{
  "content_text": "A 30-second clip of a Jordanian student showing her water-purification prototype.",
  "media_url": "uploads/clip123.mp4",
  "goal": "applications",
  "topic_hint": "young inventors water tech"
}
```

The frontend renders the frozen response fields from `routes`, `map_data`, `trend_ticker`, `content_summary`, and optional `visual_profile`. Low match routes under 50 are de-emphasized and labeled `wrong room`. `dialect_rewrite` renders right-to-left when present.
