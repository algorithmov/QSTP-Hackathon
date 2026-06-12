"""FastAPI entry point. Run: uvicorn app.main:app --reload --port 8000"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# must come after load_dotenv so env vars are visible to submodules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

import knowledge_base as kb
import model_client
import routing
from app.schemas import RouteRequest, RouteResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Masar Routing Engine", version="1.0.0")

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = [o.strip() for o in _origins_raw.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    kb.init_db()
    logger.info("Knowledge base ready. MOCK_MODE=%s", os.getenv("MOCK_MODE", "true"))


@app.get("/health")
async def health() -> dict:
    model_status = await model_client.health_check()
    return {
        "status": "ok",
        "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true",
        "model_service": model_status,
    }


@app.post("/api/route", response_model=RouteResponse)
async def route(request: RouteRequest) -> RouteResponse:
    valid_goals = {"applications", "viewers", "sponsors", "buzz"}
    if request.goal not in valid_goals:
        raise HTTPException(
            status_code=422,
            detail=f"goal must be one of: {', '.join(sorted(valid_goals))}",
        )
    if not request.content_text.strip():
        raise HTTPException(status_code=422, detail="content_text must not be empty")

    try:
        return await routing.route_content(request)
    except Exception as exc:
        logger.exception("route_content failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/upload")
async def upload_media(file: UploadFile = File(...)) -> dict:
    """Accept a media upload; return a media_url path for use in /api/route."""
    allowed = {"video/mp4", "video/quicktime", "image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="Unsupported media type")
    import uuid, pathlib
    uploads_dir = pathlib.Path(__file__).parent.parent / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    ext = pathlib.Path(file.filename or "upload").suffix or ".mp4"
    name = f"{uuid.uuid4()}{ext}"
    dest = uploads_dir / name
    dest.write_bytes(await file.read())
    return {"media_url": f"uploads/{name}"}
