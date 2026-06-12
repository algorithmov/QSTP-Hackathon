"""Model service client. Returns deterministic stubs when MOCK_MODE=true."""
import hashlib
import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://localhost:9000")


# --- mock helpers ---

def _hash_float(seed: str, lo: float = 0.0, hi: float = 1.0) -> float:
    digest = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return lo + (digest % 10000) / 10000 * (hi - lo)


def _mock_visual_profile(media_url: str) -> dict:
    h = lambda s: _hash_float(media_url + s)
    return {
        "content_type": "product_demo",
        "format": "vertical_short",
        "has_text_overlay": True,
        "detected_text_language": "ar",
        "face_count": 1,
        "motion_level": round(h("motion"), 2),
        "energy_score": round(h("energy"), 2),
        "dominant_colors": ["#1b2a3a", "#d9c2a0"],
        "aspect_ratio": "9:16",
        "confidence": round(0.75 + h("conf") * 0.20, 2),
    }


def _mock_prediction(candidate: dict) -> dict:
    seed = json.dumps(candidate, sort_keys=True)
    engagement = round(0.55 + _hash_float(seed + "eng") * 0.40, 4)
    confidence = round(0.60 + _hash_float(seed + "conf") * 0.35, 4)
    return {"predicted_engagement": engagement, "confidence": confidence}


# --- public API ---

async def vision_analyze(media_url: Optional[str], file_bytes: Optional[bytes] = None) -> Optional[dict]:
    if MOCK_MODE:
        if media_url:
            return _mock_visual_profile(media_url)
        return None

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            if file_bytes:
                resp = await client.post(
                    f"{MODEL_SERVICE_URL}/vision/analyze",
                    files={"file": ("upload", file_bytes, "video/mp4")},
                )
            else:
                resp = await client.post(
                    f"{MODEL_SERVICE_URL}/vision/analyze",
                    json={"media_url": media_url},
                )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("vision_analyze failed: %s", exc)
        return None


async def predict_fit_batch(candidates: list[dict]) -> list[dict]:
    if MOCK_MODE:
        return [_mock_prediction(c) for c in candidates]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MODEL_SERVICE_URL}/predict/fit_batch",
                json={"candidates": candidates},
            )
            resp.raise_for_status()
            body = resp.json()
            return body["predictions"]
    except Exception as exc:
        logger.error("predict_fit_batch failed: %s — falling back to mock", exc)
        return [_mock_prediction(c) for c in candidates]


async def health_check() -> dict:
    if MOCK_MODE:
        return {"status": "ok", "model_version": "mock", "mock_mode": True}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MODEL_SERVICE_URL}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}
