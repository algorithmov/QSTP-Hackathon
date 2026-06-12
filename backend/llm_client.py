"""
LLM client with provider fallback ladder.

Priority order (default: fanar):
  1. Fanar  — QCRI/HBKU Arabic-native model; primary for Stars of Science.
  2. Gemini — Google Gemini 2.5 Flash via google-genai SDK; supports AQ. keys.
  3. Local  — Ollama OpenAI-compatible endpoint; fully offline, zero rate limits.
  4. Rule-based — pure Python, always succeeds, never hallucinates.

Any HTTP/parse error logs a WARNING and falls through to the next provider.
The caller never sees an exception.
"""
import json
import logging
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)

LLM_PROVIDER       = os.getenv("LLM_PROVIDER",      "fanar")
FANAR_API_KEY      = os.getenv("FANAR_API_KEY",      "")
FANAR_BASE_URL     = os.getenv("FANAR_BASE_URL",     "https://api.fanar.qa/v1")
FANAR_MODEL        = os.getenv("FANAR_MODEL",        "Fanar-S-1-7B")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY",     "")
GEMINI_MODEL       = os.getenv("GEMINI_MODEL",       "gemini-2.5-flash")
LOCAL_BASE_URL     = os.getenv("LOCAL_BASE_URL",     "http://localhost:11434/v1")
LOCAL_MODEL        = os.getenv("LOCAL_MODEL",        "qwen2.5:7b")
ENABLE_DIALECT_REWRITE = os.getenv("ENABLE_DIALECT_REWRITE", "false").lower() == "true"
LLM_TIMEOUT        = float(os.getenv("LLM_TIMEOUT", "12"))

_SYSTEM_PROMPT = (
    "You are a social media strategy assistant for Stars of Science, "
    "an Arab innovation reality TV show. Reply ONLY with valid JSON, "
    "no markdown fences, no preamble."
)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> dict:
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group())
    raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_analysis_prompt(content_text: str, goal: str, routes: list[dict]) -> str:
    routes_summary = [
        {
            "rank":           r["rank"],
            "platform":       r["platform"],
            "country_name":   r["country_name"],
            "audience":       r["audience"],
            "language":       r["language"],
            "match_score":    r["match_score"],
            "components":     r["components"],
            "trend_direction": r["trend_direction"],
            "trend_change_pct": r.get("trend_change_pct"),
        }
        for r in routes
    ]
    ranks = ", ".join(f'"{r["rank"]}"' for r in routes)
    return (
        f"Content description: {content_text}\n"
        f"Goal: {goal}\n"
        f"Routes:\n{json.dumps(routes_summary, ensure_ascii=False)}\n\n"
        "Return this exact JSON shape (no extra keys):\n"
        "{\n"
        '  "content_summary": "one sentence, max 20 words",\n'
        '  "why": {\n'
        f'    {ranks.replace(", ", chr(58) + " ...," + chr(10) + "    ")}: "one line per route, max 15 words"\n'
        "  }\n"
        "}\n"
        'Keys in "why" are the route rank as a string integer.\n'
        "Write in English unless the route language is Arabic — then use Modern Standard Arabic."
    )


def _build_rewrite_prompt(content_text: str, language: str, platform: str) -> str:
    return (
        f"Rewrite this post caption for a {language} audience on {platform}.\n"
        f"Keep it under 150 characters. Use {language} dialect naturally.\n"
        f"Original: {content_text}\n"
        'Return ONLY: {"dialect_rewrite": "...rewritten text..."}'
    )


# ── Provider implementations ──────────────────────────────────────────────────

async def _call_fanar(prompt: str) -> dict:
    if not FANAR_API_KEY:
        raise ValueError("FANAR_API_KEY not set")
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{FANAR_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {FANAR_API_KEY}"},
            json={
                "model": FANAR_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
                "max_tokens": 600,
            },
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(text)


async def _call_gemini(prompt: str) -> dict:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=600,
        ),
    )
    return _extract_json(response.text)


async def _call_local(prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{LOCAL_BASE_URL}/chat/completions",
            json={
                "model": LOCAL_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
                "max_tokens": 600,
            },
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(text)


def _rule_based_output(content_text: str, routes: list[dict]) -> dict:
    summary = content_text[:120].rstrip()
    if len(content_text) > 120:
        summary += " [auto-summary]"
    why: dict[str, str] = {}
    for r in routes:
        post_time = r.get("post_time_local", "peak time")
        tz        = r.get("timezone", "")
        why[str(r["rank"])] = (
            f"Score {r['match_score']}/100 — best fit: {r['platform']} in "
            f"{r['country_name']} for {r['audience']} audience "
            f"at {post_time} {tz}."
        )
    return {"content_summary": summary, "why": why}


# ── Provider ladder ───────────────────────────────────────────────────────────

_PROVIDER_FNS = {
    "fanar":  _call_fanar,
    "gemini": _call_gemini,
    "local":  _call_local,
}

_LADDER: dict[str, list[str]] = {
    "gemini":     ["gemini", "local"],
    "fanar":      ["fanar", "gemini", "local"],
    "local":      ["local"],
    "rule_based": [],
}


async def _try_providers(prompt: str, start: str) -> tuple[dict, str]:
    order = _LADDER.get(start, _LADDER["fanar"])
    for name in order:
        fn = _PROVIDER_FNS.get(name)
        if fn is None:
            continue
        try:
            result = await fn(prompt)
            return result, name
        except Exception as exc:
            logger.warning("LLM provider %s failed: %s", name, exc)
    return {}, "rule_based"


# ── Public interface ──────────────────────────────────────────────────────────

async def get_llm_output(
    content_text: str,
    goal: str,
    routes: list[dict],
) -> dict:
    """
    Returns:
      {
        "content_summary": str,
        "why": {"1": str, ...},
        "dialect_rewrites": {"1": str|None, ...},
        "provider_used": str,
      }
    Never raises. Falls back to rule_based if all providers fail.
    """
    analysis_prompt = _build_analysis_prompt(content_text, goal, routes)
    raw, provider_used = await _try_providers(analysis_prompt, LLM_PROVIDER)

    if not raw:
        rb = _rule_based_output(content_text, routes)
        content_summary = rb["content_summary"]
        why             = rb["why"]
        provider_used   = "rule_based"
    else:
        content_summary = raw.get("content_summary", content_text[:80])
        why = {str(k): v for k, v in raw.get("why", {}).items()}
        # Fill any missing ranks with rule-based fallback
        rb = _rule_based_output(content_text, routes)
        for r in routes:
            if str(r["rank"]) not in why:
                why[str(r["rank"])] = rb["why"][str(r["rank"])]

    # Dialect rewrites — one separate call per Arabic route
    dialect_rewrites: dict[str, Optional[str]] = {str(r["rank"]): None for r in routes}
    if ENABLE_DIALECT_REWRITE:
        for r in routes:
            lang = r.get("language", "")
            if "Arabic" not in lang and "arabic" not in lang:
                continue
            rewrite_prompt = _build_rewrite_prompt(content_text, lang, r["platform"])
            rewrite_raw, _ = await _try_providers(rewrite_prompt, LLM_PROVIDER)
            if rewrite_raw and "dialect_rewrite" in rewrite_raw:
                dialect_rewrites[str(r["rank"])] = rewrite_raw["dialect_rewrite"]

    return {
        "content_summary":  content_summary,
        "why":              why,
        "dialect_rewrites": dialect_rewrites,
        "provider_used":    provider_used,
    }
