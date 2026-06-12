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


def _repair_json(text: str) -> str:
    """Fix common LLM JSON issues: trailing commas, unescaped control chars."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # Remove literal newlines/tabs inside string values (replace with space)
    text = re.sub(r'(?<=["\w])\n(?=["\w])', " ", text)
    return text


def _extract_json(text: str) -> dict:
    text = _strip_fences(text)
    for candidate in (text, _repair_json(text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Try largest {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        for candidate in (m.group(), _repair_json(m.group())):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    # Last resort: extract individual fields with regex
    result: dict = {}
    summary_m = re.search(r'"content_summary"\s*:\s*"([^"]+)"', text)
    if summary_m:
        result["content_summary"] = summary_m.group(1)
    why_m = re.search(r'"why"\s*:\s*(\{[^}]+\})', text, re.DOTALL)
    if why_m:
        try:
            result["why"] = json.loads(_repair_json(why_m.group(1)))
        except Exception:
            pass
    tips_m = re.search(r'"tips"\s*:\s*(\{.*?\}\s*\})', text, re.DOTALL)
    if tips_m:
        try:
            result["tips"] = json.loads(_repair_json(tips_m.group(1)))
        except Exception:
            pass
    if result:
        return result
    raise ValueError(f"No JSON found in LLM response: {text[:300]!r}")


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_analysis_prompt(content_text: str, goal: str, routes: list[dict]) -> str:
    routes_summary = [
        {
            "rank":            r["rank"],
            "platform":        r["platform"],
            "country_name":    r["country_name"],
            "audience":        r["audience"],
            "language":        r["language"],
            "match_score":     r["match_score"],
            "trend_direction": r["trend_direction"],
            "trend_change_pct": r.get("trend_change_pct"),
        }
        for r in routes
    ]

    # Build the expected JSON shape with one entry per route so the LLM can
    # see exactly which rank maps to which platform+country.
    why_lines = "\n".join(
        f'    "{r["rank"]}": "sentence about rank {r["rank"]} — {r["platform"]} in {r["country_name"]}, max 18 words"'
        for r in routes
    )
    tips_lines = "\n".join(
        f'    "{r["rank"]}": ["tip 1 for {r["country_name"]} on {r["platform"]}", "tip 2", "tip 3"]'
        for r in routes
    )

    return (
        f"Content: {content_text}\n"
        f"Campaign goal: {goal}\n"
        f"Top routes (ranked by fit score):\n{json.dumps(routes_summary, ensure_ascii=False)}\n\n"
        "Reply with ONLY this JSON object (no markdown, no extra keys):\n"
        "{\n"
        '  "content_summary": "one sentence, max 20 words",\n'
        '  "why": {\n'
        f"{why_lines}\n"
        "  },\n"
        '  "tips": {\n'
        f"{tips_lines}\n"
        "  }\n"
        "}\n\n"
        "Rules:\n"
        '- Each "why" value must name the EXACT platform and country for that rank. Max 18 words.\n'
        '- Each "tips" value: exactly 3 short imperative sentences (10 words max each) '
        "specific to that country's culture, platform norms, and the trend direction shown.\n"
        "- Write in English."
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
                "max_tokens": 2500,
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
            max_output_tokens=2500,
        ),
    )
    try:
        return _extract_json(response.text)
    except Exception as exc:
        logger.warning("Gemini JSON parse failed (%s); raw: %s", exc, (response.text or "")[:500])
        raise


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
                "max_tokens": 2500,
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
    tips: dict[str, list[str]] = {}
    for r in routes:
        post_time = r.get("post_time_local", "peak time")
        tz        = r.get("timezone", "")
        why[str(r["rank"])] = (
            f"Score {r['match_score']}/100 — {r['platform']} in "
            f"{r['country_name']} for {r['audience']} at {post_time} {tz}."
        )
        tips[str(r["rank"])] = [
            f"Post at {post_time} {tz} for peak {r['country_name']} audience activity.",
            f"Use {r.get('language', 'local language')} captions throughout the content.",
            f"Engage every comment within 60 minutes to boost {r['platform']} ranking.",
        ]
    return {"content_summary": summary, "why": why, "tips": tips}


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

    rb = _rule_based_output(content_text, routes)

    if not raw:
        content_summary = rb["content_summary"]
        why             = rb["why"]
        tips            = rb["tips"]
        provider_used   = "rule_based"
    else:
        content_summary = raw.get("content_summary", content_text[:80])
        why = {str(k): v for k, v in raw.get("why", {}).items()}
        tips = {
            str(k): v for k, v in raw.get("tips", {}).items()
            if isinstance(v, list)
        }
        # Fill any missing ranks with rule-based fallback
        for r in routes:
            key = str(r["rank"])
            if key not in why:
                why[key] = rb["why"][key]
            if key not in tips:
                tips[key] = rb["tips"][key]

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
        "tips":             tips,
        "dialect_rewrites": dialect_rewrites,
        "provider_used":    provider_used,
    }
