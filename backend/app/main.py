"""FastAPI entry point. Run: uvicorn app.main:app --reload --port 8000"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    PersonalizeRequest,
    PersonalizeResponse,
    ReviewRequest,
    ReviewResponse,
    VALID_GOALS,
    VALID_COUNTRIES,
    VALID_PLATFORMS,
)
from app.review import handle_review
from app.personalize import handle_personalize
from app.review import _extract_idea_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Masar v2", version="2.0.0")

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = [o.strip() for o in _origins_raw.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true",
        "version": "2.0.0",
    }


@app.post("/api/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    if not request.idea_text.strip():
        raise HTTPException(status_code=422, detail="idea_text must not be empty")
    if request.goal not in VALID_GOALS:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(VALID_GOALS))}",
        )
    try:
        return await handle_review(request)
    except Exception as exc:
        logger.exception("handle_review failed")
        raise HTTPException(status_code=500, detail="Review failed. Try again.") from exc


@app.post("/api/personalize", response_model=PersonalizeResponse)
async def personalize(request: PersonalizeRequest) -> PersonalizeResponse:
    if not request.idea_text.strip():
        raise HTTPException(status_code=422, detail="idea_text must not be empty")
    if request.goal not in VALID_GOALS:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(VALID_GOALS))}",
        )

    invalid_countries = [c for c in request.countries if c not in VALID_COUNTRIES]
    if invalid_countries:
        raise HTTPException(status_code=400, detail=f"Unsupported countries: {invalid_countries}")
    if not request.countries:
        raise HTTPException(status_code=400, detail="At least one country required")
    if len(request.countries) > 3:
        request.countries = request.countries[:3]

    invalid_platforms = [p for p in request.platforms if p not in VALID_PLATFORMS]
    if invalid_platforms:
        raise HTTPException(status_code=400, detail=f"Unsupported platforms: {invalid_platforms}")
    if not request.platforms:
        raise HTTPException(status_code=400, detail="At least one platform required")
    if len(request.platforms) > 2:
        request.platforms = request.platforms[:2]

    try:
        idea_summary = _extract_idea_summary(request.idea_text, request.goal)
        return await handle_personalize(request, idea_summary)
    except Exception as exc:
        logger.exception("handle_personalize failed")
        raise HTTPException(status_code=500, detail="Personalization failed. Try again.") from exc
