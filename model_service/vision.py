from __future__ import annotations

import re
from pathlib import Path

import cv2
import easyocr
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

CLIP_MODEL_ID = "openai/clip-vit-base-patch32"

CONTENT_LABELS = [
    "talking head",
    "product demo",
    "text overlay",
    "scenery",
    "group action",
    "interview",
]

CONTENT_LABEL_MAP = {
    "talking head": "talking_head",
    "product demo": "product_demo",
    "text overlay": "text_overlay",
    "scenery": "scenery",
    "group action": "group_action",
    "interview": "interview",
}

N_FRAMES = 8
N_COLORS = 5
DOMINANT_COLOR_SAMPLE = 1000

# ---------------------------------------------------------------------------
# Model loading (done once at import time)
# ---------------------------------------------------------------------------

print(f"[vision] loading CLIP on {DEVICE} ...")
_clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
_clip_model = CLIPModel.from_pretrained(CLIP_MODEL_ID).to(DEVICE)
_clip_model.eval()
print("[vision] CLIP ready")

print("[vision] loading EasyOCR (ar + en) ...")
_ocr_reader = easyocr.Reader(["ar", "en"], gpu=torch.cuda.is_available())
print("[vision] EasyOCR ready")

HAAR_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(HAAR_PATH)

# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def extract_frames(source: str | Path | bytes) -> list[np.ndarray]:
    """
    Return a list of BGR frames (numpy arrays).
    - Video: N_FRAMES evenly spaced frames.
    - Image: single frame.
    source can be a file path (str/Path) or raw bytes.
    """
    # Write bytes to a temp file so OpenCV can open it
    if isinstance(source, (bytes, bytearray)):
        import tempfile, os
        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(source)
            tmp_path = f.name
        frames = _extract_from_path(tmp_path)
        os.unlink(tmp_path)
        return frames
    return _extract_from_path(str(source))


def _extract_from_path(path: str) -> list[np.ndarray]:
    # Try as video first
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total > 1:
        indices = np.linspace(0, total - 1, N_FRAMES, dtype=int)
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        cap.release()
        if frames:
            return frames
    cap.release()
    # Fall back to image
    img = cv2.imread(path)
    if img is not None:
        return [img]
    raise ValueError(f"Could not read file as video or image: {path}")

# ---------------------------------------------------------------------------
# Format and aspect ratio
# ---------------------------------------------------------------------------

def get_format_and_ratio(frame: np.ndarray) -> tuple[str, str]:
    h, w = frame.shape[:2]
    ratio = w / h

    def nearest_ratio(w, h):
        from math import gcd
        d = gcd(w, h)
        return f"{w // d}:{h // d}"

    # Snap to common ratios
    if abs(ratio - 9 / 16) < 0.05:
        fmt, ar = "vertical_short", "9:16"
    elif abs(ratio - 16 / 9) < 0.05:
        fmt, ar = "horizontal_long", "16:9"
    elif abs(ratio - 1.0) < 0.05:
        fmt, ar = "square_image", "1:1"
    elif ratio < 1.0:
        fmt, ar = "portrait_image", nearest_ratio(w, h)
    else:
        fmt, ar = "horizontal_long", nearest_ratio(w, h)

    return fmt, ar

# ---------------------------------------------------------------------------
# CLIP content classification
# ---------------------------------------------------------------------------

def classify_content(frames: list[np.ndarray]) -> tuple[str, float]:
    """Return (content_type_snake, confidence) averaged over frames."""
    prompts = [f"a video of {label}" for label in CONTENT_LABELS]
    scores_accum = np.zeros(len(CONTENT_LABELS))

    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        inputs = _clip_processor(
            text=prompts, images=pil_img, return_tensors="pt", padding=True
        )
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = _clip_model(**inputs)
            logits = outputs.logits_per_image[0]
            probs = logits.softmax(dim=-1).cpu().numpy()
        scores_accum += probs

    scores_accum /= len(frames)
    best_idx = int(np.argmax(scores_accum))
    label_raw = CONTENT_LABELS[best_idx]
    content_type = CONTENT_LABEL_MAP[label_raw]
    confidence = float(scores_accum[best_idx])
    return content_type, confidence

# ---------------------------------------------------------------------------
# Face counting
# ---------------------------------------------------------------------------

def count_faces(frames: list[np.ndarray]) -> int:
    """Return the median face count across frames (rounded to int)."""
    counts = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        counts.append(len(faces) if isinstance(faces, np.ndarray) else 0)
    return int(np.median(counts)) if counts else 0

# ---------------------------------------------------------------------------
# Motion level
# ---------------------------------------------------------------------------

def compute_motion(frames: list[np.ndarray]) -> float:
    """Mean absolute difference between consecutive frames, normalized 0-1."""
    if len(frames) < 2:
        return 0.0
    diffs = []
    for a, b in zip(frames[:-1], frames[1:]):
        gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(float)
        gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(float)
        diffs.append(np.mean(np.abs(gray_a - gray_b)))
    raw = float(np.mean(diffs))
    # Typical MAD range 0-40; clip and normalize
    return float(np.clip(raw / 40.0, 0.0, 1.0))

# ---------------------------------------------------------------------------
# Energy score
# ---------------------------------------------------------------------------

def compute_energy(frames: list[np.ndarray], motion: float) -> float:
    """Combine motion, mean saturation, and cut frequency into 0-1 score."""
    saturations = []
    for frame in frames:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturations.append(float(np.mean(hsv[:, :, 1])) / 255.0)
    mean_sat = float(np.mean(saturations))

    # Cut frequency: std of mean brightness across frames
    brightness = [float(np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))) / 255.0
                  for f in frames]
    cut_freq = float(np.std(brightness))

    energy = 0.5 * motion + 0.3 * mean_sat + 0.2 * min(cut_freq * 5, 1.0)
    return float(np.clip(energy, 0.0, 1.0))

# ---------------------------------------------------------------------------
# OCR: text overlay and language
# ---------------------------------------------------------------------------

def detect_text(frames: list[np.ndarray]) -> tuple[bool, str]:
    """
    Run EasyOCR on the middle frame.
    Returns (has_text_overlay, detected_text_language).
    language: 'ar' | 'en' | 'mixed' | 'none'
    """
    mid = frames[len(frames) // 2]
    rgb = cv2.cvtColor(mid, cv2.COLOR_BGR2RGB)
    results = _ocr_reader.readtext(rgb, detail=1)

    if not results:
        return False, "none"

    ar_count = 0
    en_count = 0
    ar_pattern = re.compile(r'[\u0600-\u06FF]')

    for _bbox, text, _conf in results:
        if ar_pattern.search(text):
            ar_count += 1
        else:
            en_count += 1

    if ar_count > 0 and en_count > 0:
        lang = "mixed"
    elif ar_count > 0:
        lang = "ar"
    elif en_count > 0:
        lang = "en"
    else:
        lang = "none"

    return True, lang

# ---------------------------------------------------------------------------
# Dominant colors
# ---------------------------------------------------------------------------

def dominant_colors(frames: list[np.ndarray], k: int = N_COLORS) -> list[str]:
    """K-means on sampled pixels across all frames. Returns hex color strings."""
    pixels = []
    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        flat = rgb.reshape(-1, 3).astype(np.float32)
        if len(flat) > DOMINANT_COLOR_SAMPLE:
            idx = np.random.choice(len(flat), DOMINANT_COLOR_SAMPLE, replace=False)
            flat = flat[idx]
        pixels.append(flat)

    all_pixels = np.vstack(pixels)
    k = min(k, len(all_pixels))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(
        all_pixels, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS
    )
    # Sort by frequency
    counts = np.bincount(labels.flatten())
    order = np.argsort(-counts)
    hex_colors = []
    for i in order:
        r, g, b = [int(c) for c in centers[i]]
        hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")
    return hex_colors

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze(source: str | Path | bytes) -> dict:
    """
    Full vision analysis pipeline.
    source: file path (str/Path) or raw bytes.
    Returns the Contract 2 vision shape.
    """
    frames = extract_frames(source)
    if not frames:
        raise ValueError("No frames could be extracted from source.")

    fmt, ar = get_format_and_ratio(frames[0])
    content_type, confidence = classify_content(frames)
    face_count = count_faces(frames)
    motion = compute_motion(frames)
    energy = compute_energy(frames, motion)
    has_text, lang = detect_text(frames)
    colors = dominant_colors(frames)

    return {
        "content_type": content_type,
        "format": fmt,
        "has_text_overlay": has_text,
        "detected_text_language": lang,
        "face_count": face_count,
        "motion_level": round(motion, 4),
        "energy_score": round(energy, 4),
        "dominant_colors": colors,
        "aspect_ratio": ar,
        "confidence": round(confidence, 4),
    }