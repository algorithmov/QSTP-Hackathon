"""FastAPI entry point. Run: uvicorn app.main:app --reload --port 8000"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    CountryFitResponse,
    ImportResponse,
    ImportRunResult,
    PersonalizeRequest,
    PersonalizeResponse,
    PlatformReportRequest,
    PlatformReportResponse,
    ReviewRequest,
    ReviewResponse,
    StarsSyncResponse,
    StarsStatusResponse,
    VALID_GOALS,
    VALID_COUNTRIES,
    VALID_PLATFORMS,
)
from app.review import handle_country_fit, handle_platform_report, handle_review
from app.review import _extract_idea_summary
import app.kb_client as kb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="Masar v3", version="3.0.0")

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = [o.strip() for o in _origins_raw.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",")[0].strip()
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_MAX_MEDIA_BYTES = 18 * 1024 * 1024  # 18 MB
_ALLOWED_MIME = ("image/", "video/", "audio/")


@app.get("/health")
async def health() -> dict:
    platform_stats = kb.get_platform_stats()
    return {
        "status": "ok",
        "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true",
        "version": "3.0.0",
        "stars_sync": kb.get_last_sync(),
        "platform_post_counts": {
            s["platform"]: s["post_count"] for s in platform_stats
        },
    }


@app.post("/api/review", response_model=ReviewResponse)
async def review(
    idea_text: str = Form(...),
    goal: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> ReviewResponse:
    if not idea_text.strip():
        raise HTTPException(status_code=422, detail="idea_text must not be empty")
    if goal not in VALID_GOALS:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(VALID_GOALS))}",
        )

    request = ReviewRequest(idea_text=idea_text, goal=goal)
    saved_assets: list[dict] = []
    media_context: dict | None = None

    if files:
        import uuid as _uuid
        from app.media_store import save_media, validate_mime, MAX_FILE_SIZE_BYTES
        from app.gemini_media import extract_media_context

        review_id = str(_uuid.uuid4())

        for upload in files:
            if not upload.filename:
                continue
            mime = upload.content_type or "application/octet-stream"
            if not any(mime.startswith(p) for p in _ALLOWED_MIME):
                logger.warning("Rejected file %s with mime %s", upload.filename, mime)
                continue
            content = await upload.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                logger.warning("Rejected oversized file %s (%d bytes)", upload.filename, len(content))
                continue
            try:
                asset = save_media(review_id, upload.filename, content, mime)
                # Strip storage_path before returning to client (internal detail)
                saved_assets.append({k: v for k, v in asset.items() if k != "storage_path"})
                # Keep full asset (with path) for Gemini
                saved_assets[-1]["storage_path"] = asset["storage_path"]
            except Exception as exc:
                logger.warning("Failed to save media %s: %s", upload.filename, exc)

        if saved_assets and _GEMINI_API_KEY:
            try:
                media_context = extract_media_context(saved_assets, _GEMINI_API_KEY, _GEMINI_MODEL)
            except Exception as exc:
                logger.warning("Gemini media extraction failed, continuing text-only: %s", exc)
                media_context = None

    # Strip storage_path from assets returned to client
    client_assets = [{k: v for k, v in a.items() if k != "storage_path"} for a in saved_assets]

    try:
        return await handle_review(request, saved_assets=client_assets, media_context=media_context)
    except Exception as exc:
        logger.exception("handle_review failed")
        raise HTTPException(status_code=500, detail="Review failed. Try again.") from exc


@app.post("/api/review/report", response_model=PlatformReportResponse)
async def review_report(request: PlatformReportRequest) -> PlatformReportResponse:
    if not request.idea_text.strip():
        raise HTTPException(status_code=422, detail="idea_text must not be empty")
    if request.goal not in VALID_GOALS:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(VALID_GOALS))}",
        )
    if request.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=422, detail=f"platform must be one of: {', '.join(sorted(VALID_PLATFORMS))}")
    try:
        return await handle_platform_report(request)
    except Exception as exc:
        logger.exception("handle_platform_report failed")
        raise HTTPException(status_code=500, detail="Platform report failed. Try again.") from exc


@app.post("/api/review/country-fit", response_model=CountryFitResponse)
async def review_country_fit(request: ReviewRequest) -> CountryFitResponse:
    if not request.idea_text.strip():
        raise HTTPException(status_code=422, detail="idea_text must not be empty")
    if request.goal not in VALID_GOALS:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(VALID_GOALS))}",
        )
    try:
        return await handle_country_fit(request)
    except Exception as exc:
        logger.exception("handle_country_fit failed")
        raise HTTPException(status_code=500, detail="Country fit generation failed. Try again.") from exc


@app.post("/api/admin/stars/sync", response_model=StarsSyncResponse)
async def sync_stars_dataset() -> StarsSyncResponse:
    try:
        sync = kb.sync_all_platforms(mode="manual_sync")
        return StarsSyncResponse(status="ok", sync=sync)
    except Exception as exc:
        logger.exception("sync_stars_dataset failed")
        raise HTTPException(status_code=500, detail="Stars sync failed. Try again.") from exc


@app.post("/api/admin/import", response_model=ImportResponse)
async def import_scraped_files() -> ImportResponse:
    """Import all JSON and CSV files from backend/data/imports/ into the Stars store."""
    try:
        runs = kb.import_all_from_dir()
        total_inserted = sum(r["inserted_count"] for r in runs)
        total_updated = sum(r["updated_count"] for r in runs)
        total_skipped = sum(r["skipped_count"] for r in runs)
        return ImportResponse(
            status="ok",
            runs=[ImportRunResult(**r) for r in runs],
            total_inserted=total_inserted,
            total_updated=total_updated,
            total_skipped=total_skipped,
        )
    except Exception as exc:
        logger.exception("import_scraped_files failed")
        raise HTTPException(status_code=500, detail="Import failed. Try again.") from exc


@app.get("/api/admin/status", response_model=StarsStatusResponse)
async def stars_status() -> StarsStatusResponse:
    try:
        last_sync = kb.get_last_sync()
        platform_stats = kb.get_platform_stats()
        import_stats = kb.get_import_stats()
        return StarsStatusResponse(
            last_sync=last_sync,
            platform_stats=platform_stats,
            total_posts=sum(s["post_count"] for s in platform_stats),
            import_stats=import_stats,
        )
    except Exception as exc:
        logger.exception("stars_status failed")
        raise HTTPException(status_code=500, detail="Status check failed.") from exc


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
        from app.personalize import handle_personalize
        idea_summary = _extract_idea_summary(request.idea_text, request.goal)
        return await handle_personalize(request, idea_summary)
    except Exception as exc:
        logger.exception("handle_personalize failed")
        raise HTTPException(status_code=500, detail="Personalization failed. Try again.") from exc
