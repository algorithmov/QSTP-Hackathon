"""Groq LLM client with model fallback and Pydantic validation."""
import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    if MOCK_MODE or not GROQ_API_KEY:
        raise RuntimeError("MOCK_MODE active or no GROQ_API_KEY — caller must handle")

    models = [GROQ_MODEL, GROQ_FALLBACK_MODEL]
    last_error: Exception | None = None
    for model in models:
        try:
            response = _get_client().chat.completions.create(
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
