"""Multi-provider LLM client.

Gemini is the primary provider when configured. Groq is retained as a fallback
so live demos can continue if Gemini quota is exhausted or keys fail.
"""
import json
import logging
import os
import re
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

GEMINI_API_KEYS = [
    key.strip()
    for key in re.split(r"[,\n]", os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")))
    if key.strip()
]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

LLM_PROVIDER_ORDER = [
    provider.strip().lower()
    for provider in os.getenv("LLM_PROVIDER_ORDER", "gemini,groq").split(",")
    if provider.strip()
]

_groq_client: Groq | None = None
_gemini_key_index = 0
_gemini_disabled_until = 0.0


def llm_available() -> bool:
    return not MOCK_MODE and (bool(GEMINI_API_KEYS) or bool(GROQ_API_KEY))


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"([?&]key=)[^&\s]+", r"\1[redacted]", message)
    return message[:500]


def _gemini_ordered_keys() -> list[str]:
    if not GEMINI_API_KEYS:
        return []
    start = _gemini_key_index % len(GEMINI_API_KEYS)
    return GEMINI_API_KEYS[start:] + GEMINI_API_KEYS[:start]


def _call_gemini_json(system_prompt: str, user_prompt: str) -> dict:
    global _gemini_disabled_until, _gemini_key_index
    if not GEMINI_API_KEYS:
        raise RuntimeError("Gemini API keys are not configured")
    if time.time() < _gemini_disabled_until:
        raise RuntimeError("Gemini is temporarily disabled after quota exhaustion")

    last_error: Exception | None = None
    quota_failures = 0
    for offset, key in enumerate(_gemini_ordered_keys()):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
            payload: dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "responseMimeType": "application/json",
                },
            }
            response = httpx.post(url, params={"key": key}, json=payload, timeout=45.0)

            # Config errors (bad model name, malformed request) — fail fast, don't rotate
            if response.status_code in (400, 404):
                msg = response.json().get("error", {}).get("message", response.text[:200])
                raise RuntimeError(f"Gemini config error (HTTP {response.status_code}): {msg}")

            # Quota exhausted for this key — rotate to next
            if response.status_code == 429:
                quota_failures += 1
                last_error = RuntimeError(f"Gemini key slot {offset + 1} quota exceeded (429)")
                logger.warning("Gemini key slot %s/%s quota exceeded", offset + 1, len(GEMINI_API_KEYS))
                _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_API_KEYS)
                continue

            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            _gemini_key_index = (GEMINI_API_KEYS.index(key) + 1) % len(GEMINI_API_KEYS)
            return _extract_json(text)
        except RuntimeError:
            raise  # fast-fail config errors bubble up immediately
        except Exception as exc:
            _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_API_KEYS)
            logger.warning("Gemini key slot %s/%s failed: %s", offset + 1, len(GEMINI_API_KEYS), _safe_error(exc))
            last_error = exc

    # Only apply backoff when ALL keys were quota-exhausted (not for other transient errors)
    if quota_failures == len(GEMINI_API_KEYS):
        _gemini_disabled_until = time.time() + 600
        logger.warning("All %s Gemini keys quota-exhausted — disabling for 10 min", len(GEMINI_API_KEYS))
    raise RuntimeError(f"All Gemini keys failed: {_safe_error(last_error) if last_error else 'unknown error'}")


def _call_groq_json(system_prompt: str, user_prompt: str) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("Groq API key is not configured")

    last_error: Exception | None = None
    for model in [GROQ_MODEL, GROQ_FALLBACK_MODEL]:
        try:
            response = _get_groq_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as exc:
            logger.warning("Groq model %s failed: %s", model, exc)
            last_error = exc
    raise RuntimeError(f"All Groq models failed: {last_error}")


def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    if MOCK_MODE:
        raise RuntimeError("MOCK_MODE active — caller must handle")

    last_error: Exception | None = None
    for provider in LLM_PROVIDER_ORDER:
        try:
            if provider == "gemini":
                return _call_gemini_json(system_prompt, user_prompt)
            if provider == "groq":
                return _call_groq_json(system_prompt, user_prompt)
            logger.warning("Unknown LLM provider ignored: %s", provider)
        except Exception as exc:
            logger.warning("%s provider failed: %s", provider, _safe_error(exc))
            last_error = exc
    raise RuntimeError(f"All LLM providers failed: {_safe_error(last_error) if last_error else 'unknown error'}")


def call_llm_validated(
    system_prompt: str,
    user_prompt: str,
    model_cls: type[BaseModel],
    default: dict,
) -> dict:
    try:
        raw = call_llm_json(system_prompt, user_prompt)
        model_cls(**raw)
        return raw
    except (RuntimeError, ValidationError) as exc:
        logger.warning("LLM call or validation failed: %s — using default", exc)
        return default
    except Exception as exc:
        logger.warning("Unexpected LLM error: %s — using default", exc)
        return default
