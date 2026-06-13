"""Gemini multimodal media context extraction for review uploads."""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_EMPTY_CONTEXT: dict = {
    "media_kind": "none",
    "detected_language": None,
    "transcript_or_audio_summary": None,
    "scene_summary": None,
    "subjects": [],
    "visual_proof_moments": [],
    "format_signals": [],
    "tone": None,
    "production_style": None,
    "cta_presence": False,
    "hook_strength": None,
    "platform_cues": [],
    "caption_drafts": [],
    "confidence_notes": None,
    "inferred_content_type": None,
    "inferred_language": None,
    "duration_signal": None,
}

_SYSTEM = (
    "You are a multimodal content analyst for Stars of Science (Arab innovation TV show). "
    "Analyze the provided media and return ONLY valid JSON matching the required schema. "
    "Be concise, factual, and grounded in what you can directly observe."
)

_USER_TEMPLATE = (
    "Analyze this {media_kind} for a Stars of Science social media post. "
    "Return a JSON object with these exact fields:\n"
    "- media_kind: one of 'image', 'video', 'audio'\n"
    "- detected_language: ISO code of primary spoken/written language seen, or null\n"
    "- transcript_or_audio_summary: spoken content summary or null\n"
    "- scene_summary: visual scene description in one sentence, or null for audio\n"
    "- subjects: list of visible subjects, people, objects, or topics\n"
    "- visual_proof_moments: list of key visible proof moments (prototypes, results, experiments)\n"
    "- format_signals: list of format observations (e.g. 'vertical', 'interview-style', 'talking-head')\n"
    "- tone: overall tone as a single word (e.g. 'educational', 'inspirational', 'professional')\n"
    "- production_style: one of 'polished', 'raw', 'moderate'\n"
    "- cta_presence: boolean, whether a clear call-to-action is present\n"
    "- hook_strength: one of 'strong', 'moderate', 'weak', or null if unclear\n"
    "- platform_cues: list of platform-native signals observed (e.g. 'subtitle overlays', 'caption hook')\n"
    "- caption_drafts: list of 2-3 short caption drafts suitable for Stars of Science platforms\n"
    "- confidence_notes: brief string describing any uncertainty, or null\n"
    "- inferred_content_type: best match from: product_demo, talking_head, educational, "
    "announcement, behind_the_scenes, achievement_story\n"
    "- inferred_language: 'ar', 'en', or 'mixed' based on all spoken and visible text\n"
    "- duration_signal: 'short_form' (under 3 min), 'long_form' (3 min+), or null if not applicable\n"
)

VALID_CONTENT_TYPES = frozenset({
    "product_demo", "talking_head", "educational",
    "announcement", "behind_the_scenes", "achievement_story",
})


def _classify_kind(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    return "unknown"


def extract_media_context(
    assets: list[dict],
    gemini_api_key: str,
    gemini_model: str = "gemini-1.5-flash",
) -> dict:
    """Call Gemini multimodal to extract structured context from media assets.

    Returns a merged context dict. Falls back to empty context if Gemini is unavailable or fails.
    Deterministic text-only review is always the fallback when this returns the empty context.
    """
    if not assets or not gemini_api_key:
        return {**_EMPTY_CONTEXT}

    contexts: list[dict] = []
    for asset in assets:
        ctx = _extract_single(asset, gemini_api_key, gemini_model)
        if ctx:
            contexts.append(ctx)

    if not contexts:
        return {**_EMPTY_CONTEXT}

    return _merge_contexts(contexts)


def _extract_single(asset: dict, gemini_api_key: str, gemini_model: str) -> dict | None:
    storage_path = asset.get("storage_path")
    mime_type = asset.get("mime_type", "")
    media_kind = _classify_kind(mime_type)

    if media_kind == "unknown" or not storage_path:
        return None

    path = Path(storage_path)
    if not path.exists():
        logger.warning("Media file missing: %s", storage_path)
        return None

    try:
        raw_bytes = path.read_bytes()
        b64 = base64.b64encode(raw_bytes).decode("ascii")
    except Exception as exc:
        logger.warning("Failed to encode media %s: %s", storage_path, exc)
        return None

    payload = {
        "systemInstruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": mime_type, "data": b64}},
                    {"text": _USER_TEMPLATE.format(media_kind=media_kind)},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"/{gemini_model}:generateContent"
        )
        response = httpx.post(url, params={"key": gemini_api_key}, json=payload, timeout=60.0)
        if response.status_code != 200:
            logger.warning(
                "Gemini vision HTTP %d for %s: %s",
                response.status_code, asset.get("original_filename"), response.text[:200],
            )
            return None
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        ctx = _parse_json(text)
        ctx["media_kind"] = media_kind
        return ctx
    except Exception as exc:
        logger.warning(
            "Gemini media extraction failed for %s: %s", asset.get("original_filename"), exc
        )
        return None


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


def _merge_contexts(contexts: list[dict]) -> dict:
    """Merge per-asset contexts — first asset wins for scalar fields, lists are union-merged."""
    if not contexts:
        return {**_EMPTY_CONTEXT}

    merged = {**_EMPTY_CONTEXT, **contexts[0]}
    for extra in contexts[1:]:
        for key in ("subjects", "visual_proof_moments", "format_signals", "platform_cues", "caption_drafts"):
            existing: list = merged.get(key) or []
            additional: list = extra.get(key) or []
            merged[key] = list(dict.fromkeys(existing + additional))

    # Validate inferred_content_type to avoid poisoning the scoring inputs
    ict = merged.get("inferred_content_type")
    if ict and ict not in VALID_CONTENT_TYPES:
        merged["inferred_content_type"] = None

    # Validate inferred_language
    il = merged.get("inferred_language")
    if il and il not in ("ar", "en", "mixed"):
        merged["inferred_language"] = None

    # Validate duration_signal
    ds = merged.get("duration_signal")
    if ds and ds not in ("short_form", "long_form"):
        merged["duration_signal"] = None

    return merged
