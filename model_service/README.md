# Model Service — `model` branch

FastAPI service exposing vision analysis and engagement prediction endpoints.
Built and running on a dual NVIDIA L4 GPU VM.

---

## Service URL

```
MODEL_SERVICE_URL=http://10.125.81.52:9000
```

---

## Endpoints

### GET /health
Returns service status and model version.

**Request:**
```bash
curl http://10.125.81.52:9000/health
```

**Response:**
```json
{ "status": "ok", "model_version": "lgbm_v1" }
```

---

### POST /vision/analyze
Analyzes an image or video file and returns a visual profile.

**Request (file upload):**
```bash
curl -X POST http://10.125.81.52:9000/vision/analyze \
  -F "file=@your_video.mp4"
```

**Request (URL):**
```bash
curl -X POST http://10.125.81.52:9000/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{ "media_url": "https://example.com/video.mp4" }'
```

**Response:**
```json
{
  "content_type": "talking_head | product_demo | text_overlay | scenery | group_action | interview | unknown",
  "format": "vertical_short | horizontal_long | square_image | portrait_image",
  "has_text_overlay": true,
  "detected_text_language": "ar | en | mixed | none",
  "face_count": 1,
  "motion_level": 0.62,
  "energy_score": 0.71,
  "dominant_colors": ["#1b2a3a", "#d9c2a0"],
  "aspect_ratio": "9:16",
  "confidence": 0.83
}
```

---

### POST /predict/fit_batch
Scores a batch of content candidates for predicted engagement.
Predictions are returned in the same order as candidates.
Missing fields are filled with sensible defaults — one bad candidate never breaks the batch.

**Request:**
```bash
curl -X POST http://10.125.81.52:9000/predict/fit_batch \
  -H "Content-Type: application/json" \
  -d '{
    "candidates": [
      {
        "platform": "TikTok",
        "country": "EG",
        "hour_local": 21,
        "day_of_week": 4,
        "content_type": "product_demo",
        "format": "vertical_short",
        "has_text_overlay": true,
        "text_language": "ar",
        "caption_length": 120,
        "hashtag_count": 5,
        "motion_level": 0.62,
        "energy_score": 0.71
      }
    ]
  }'
```

**Response:**
```json
{
  "model_version": "lgbm_v1",
  "predictions": [
    { "predicted_engagement": 0.9376, "confidence": 0.8752 }
  ]
}
```

**Candidate fields:**

| Field | Type | Default | Notes |
|---|---|---|---|
| platform | string | TikTok | TikTok, Instagram, YouTube, Twitter |
| country | string | EG | EG, SA, AE, MA, US, GB |
| hour_local | int | 12 | 0-23 |
| day_of_week | int | 0 | 0=Monday, 6=Sunday |
| content_type | string | talking_head | see vision endpoint values |
| format | string | vertical_short | see vision endpoint values |
| has_text_overlay | bool | false | |
| text_language | string | none | ar, en, mixed, none |
| caption_length | int | 100 | character count |
| hashtag_count | int | 3 | |
| motion_level | float | 0.5 | 0.0-1.0, from vision endpoint |
| energy_score | float | 0.5 | 0.0-1.0, from vision endpoint |

---

## Model

- **Algorithm:** LightGBM Regressor
- **Model file:** `models/lgbm_v1.txt`
- **Training notebook:** `train/train_lgbm.ipynb`
- **Held-out MAE:** 0.0679
- **Held-out R²:** 0.61
- **Top engagement signals:** energy_score, motion_level, hour_local, day_of_week, text_language_ar

---

## Project Structure

```
model_service/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI service
├── models/
│   └── lgbm_v1.txt      # trained LightGBM model
├── train/
│   └── train_lgbm.ipynb # reproducible training notebook
├── vision.py            # vision analysis pipeline
├── predictor.py         # batch engagement predictor
└── requirements.lock.txt
```

---

## Environment

- **Hardware:** dual NVIDIA L4, 24GB VRAM each (service uses GPU 0)
- **CUDA:** 12.4
- **Python:** 3.10.17
- **PyTorch:** 2.3.1+cu121
- **Key deps:** transformers==4.41.2, easyocr==1.7.1, lightgbm==4.3.0, fastapi==0.111.0

---

## Running the Service

```bash
cd model_service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

To run in the background:
```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 9000 > logs/service.log 2>&1 &
```

To reproduce the environment from scratch:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.lock.txt
```

---
