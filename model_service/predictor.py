from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

# ---------------------------------------------------------------------------
# Constants - must match training notebook exactly
# ---------------------------------------------------------------------------

MODEL_PATH = Path(__file__).parent / "models" / "lgbm_v1.txt"

PLATFORMS = ["Instagram", "TikTok", "Twitter", "YouTube"]
COUNTRIES = ["AE", "EG", "GB", "MA", "SA", "US"]
CONTENT_TYPES = ["group_action", "interview", "product_demo", "scenery", "talking_head", "text_overlay"]
FORMATS = ["horizontal_long", "portrait_image", "square_image", "vertical_short"]
LANGUAGES = ["ar", "en", "mixed", "none"]

NUMERIC_FEATURES = [
    "hour_local",
    "day_of_week",
    "has_text_overlay",
    "caption_length",
    "hashtag_count",
    "motion_level",
    "energy_score",
]

# Defaults for missing fields
DEFAULTS = {
    "platform": "TikTok",
    "country": "EG",
    "hour_local": 12,
    "day_of_week": 0,
    "content_type": "talking_head",
    "format": "vertical_short",
    "has_text_overlay": 0,
    "text_language": "none",
    "caption_length": 100,
    "hashtag_count": 3,
    "motion_level": 0.5,
    "energy_score": 0.5,
}

# ---------------------------------------------------------------------------
# Model loading (once at import time)
# ---------------------------------------------------------------------------

print(f"[predictor] loading model from {MODEL_PATH} ...")
_booster = lgb.Booster(model_file=str(MODEL_PATH))
print("[predictor] model ready")

MODEL_VERSION = "lgbm_v1"

# ---------------------------------------------------------------------------
# Feature engineering - must mirror the training notebook
# ---------------------------------------------------------------------------

def _build_feature_row(candidate: dict) -> dict:
    """Fill missing fields with defaults and return a flat feature dict."""
    c = {**DEFAULTS, **candidate}

    row = {
        "hour_local": int(c.get("hour_local", DEFAULTS["hour_local"])),
        "day_of_week": int(c.get("day_of_week", DEFAULTS["day_of_week"])),
        "has_text_overlay": int(bool(c.get("has_text_overlay", DEFAULTS["has_text_overlay"]))),
        "caption_length": int(c.get("caption_length", DEFAULTS["caption_length"])),
        "hashtag_count": int(c.get("hashtag_count", DEFAULTS["hashtag_count"])),
        "motion_level": float(c.get("motion_level", DEFAULTS["motion_level"])),
        "energy_score": float(c.get("energy_score", DEFAULTS["energy_score"])),
    }

    # One-hot: platform
    for p in PLATFORMS:
        row[f"platform_{p}"] = int(c.get("platform", DEFAULTS["platform"]) == p)

    # One-hot: country
    for ct in COUNTRIES:
        row[f"country_{ct}"] = int(c.get("country", DEFAULTS["country"]) == ct)

    # One-hot: content_type
    for ctype in CONTENT_TYPES:
        row[f"content_type_{ctype}"] = int(c.get("content_type", DEFAULTS["content_type"]) == ctype)

    # One-hot: format
    for fmt in FORMATS:
        row[f"format_{fmt}"] = int(c.get("format", DEFAULTS["format"]) == fmt)

    # One-hot: text_language
    for lang in LANGUAGES:
        row[f"text_language_{lang}"] = int(c.get("text_language", DEFAULTS["text_language"]) == lang)

    return row


def _build_dataframe(candidates: list[dict]) -> pd.DataFrame:
    rows = [_build_feature_row(c) for c in candidates]
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict_batch(candidates: list[dict]) -> list[dict]:
    """
    Score a batch of candidates.
    Returns a list of dicts with predicted_engagement and confidence,
    in the same order as candidates.
    One bad candidate never breaks the batch - errors get a default prediction.
    """
    results = []
    for candidate in candidates:
        try:
            df = _build_dataframe([candidate])
            raw = float(_booster.predict(df)[0])
            predicted = float(np.clip(raw, 0.0, 1.0))
            # Confidence: distance from 0.5, scaled to 0-1
            confidence = float(np.clip(abs(predicted - 0.5) * 2, 0.1, 1.0))
            results.append({
                "predicted_engagement": round(predicted, 4),
                "confidence": round(confidence, 4),
            })
        except Exception as e:
            print(f"[predictor] error scoring candidate: {e}")
            results.append({
                "predicted_engagement": 0.5,
                "confidence": 0.1,
            })
    return results