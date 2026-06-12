from __future__ import annotations

import sys
import os

# Ensure model_service root is on the path so vision and predictor can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

import vision
import predictor

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Model Service", version="1.0.0")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MediaURLRequest(BaseModel):
    media_url: str

class Candidate(BaseModel):
    platform: Optional[str] = "TikTok"
    country: Optional[str] = "EG"
    hour_local: Optional[int] = 12
    day_of_week: Optional[int] = 0
    content_type: Optional[str] = "talking_head"
    format: Optional[str] = "vertical_short"
    has_text_overlay: Optional[bool] = False
    text_language: Optional[str] = "none"
    caption_length: Optional[int] = 100
    hashtag_count: Optional[int] = 3
    motion_level: Optional[float] = 0.5
    energy_score: Optional[float] = 0.5

class PredictRequest(BaseModel):
    candidates: List[Candidate]

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "model_version": predictor.MODEL_VERSION}


@app.post("/vision/analyze")
async def analyze(file: Optional[UploadFile] = File(None), body: Optional[MediaURLRequest] = None):
    try:
        if file is not None:
            contents = await file.read()
            result = vision.analyze(contents)
        elif body is not None:
            result = vision.analyze(body.media_url)
        else:
            raise HTTPException(status_code=422, detail="Provide either a file upload or media_url JSON body.")
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/fit_batch")
def fit_batch(request: PredictRequest):
    try:
        candidates = [c.dict() for c in request.candidates]
        predictions = predictor.predict_batch(candidates)
        return {
            "model_version": predictor.MODEL_VERSION,
            "predictions": predictions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=9000, reload=False)