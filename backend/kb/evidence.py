"""Evidence search with scored multi-source retrieval and SQLite cache."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv

from app.evidence_helpers import hash_idea_text, normalize_text
from kb.stars_intelligence import search_platform_evidence

load_dotenv()

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_DB = _DATA / "kb.sqlite"
_FALLBACK = _DATA / "fallback_evidence.json"
_COUNTRY = _DATA / "country_evidence.json"

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TTL_HOURS = float(os.getenv("EVIDENCE_CACHE_TTL_HOURS", "24"))
USE_LLM_EVIDENCE_SCORING = os.getenv("USE_LLM_EVIDENCE_SCORING", "false").lower() == "true"
EVIDENCE_LLM_SCORE_THRESHOLD = int(os.getenv("EVIDENCE_LLM_SCORE_THRESHOLD", "3"))

_STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "from", "into", "about", "that", "this",
    "idea", "video", "clip", "post", "content", "student", "students", "young", "show",
    "social", "media", "audience", "digital", "learning", "technology",
}


def _ensure_cache_table() -> None:
    with sqlite3.connect(_DB) as con:
        columns = [row[1] for row in con.execute("PRAGMA table_info(evidence_cache)").fetchall()]
        if columns and columns != ["idea_hash", "topic_norm", "country_name", "fetched_at", "result_json"]:
            con.execute("DROP TABLE IF EXISTS evidence_cache")
        con.execute("""
            CREATE TABLE IF NOT EXISTS evidence_cache (
                idea_hash TEXT,
                topic_norm TEXT,
                country_name TEXT,
                fetched_at REAL,
                result_json TEXT,
                PRIMARY KEY (idea_hash, topic_norm, country_name)
            )
        """)


def _topic_terms(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def _load_fallback(topic: str, country_name: str) -> list[dict]:
    if not _FALLBACK.exists():
        return []
    topic_norm = topic.strip().lower()
    entries = json.loads(_FALLBACK.read_text())
    best_overlap: tuple[int, list[dict]] = (0, [])
    topic_terms = _topic_terms(topic_norm)
    for entry in entries:
        if entry["country_name"].strip().lower() != country_name.strip().lower():
            continue
        entry_topic = entry["topic"].strip().lower()
        if entry_topic == topic_norm:
            return entry.get("evidence", [])
        overlap = len(topic_terms & _topic_terms(entry_topic))
        if overlap > best_overlap[0]:
            best_overlap = (overlap, entry.get("evidence", []))
    return best_overlap[1]


def _load_country_evidence(country_name: str) -> list[dict]:
    if not _COUNTRY.exists():
        return []
    entries = json.loads(_COUNTRY.read_text())
    for entry in entries:
        if entry["country_name"].strip().lower() == country_name.strip().lower():
            return entry.get("evidence", [])
    return []


def _cache_get(idea_hash: str, topic_norm: str, country_name: str) -> list[dict] | None:
    _ensure_cache_table()
    with sqlite3.connect(_DB) as con:
        row = con.execute(
            "SELECT fetched_at, result_json FROM evidence_cache "
            "WHERE idea_hash=? AND topic_norm=? AND country_name=?",
            (idea_hash, topic_norm, country_name.strip().lower()),
        ).fetchone()
    if not row:
        return None
    age_hours = (time.time() - row[0]) / 3600
    if age_hours > TTL_HOURS:
        return None
    return json.loads(row[1])


def _cache_set(idea_hash: str, topic_norm: str, country_name: str, results: list[dict]) -> None:
    _ensure_cache_table()
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO evidence_cache VALUES (?,?,?,?,?)",
            (idea_hash, topic_norm, country_name.strip().lower(), time.time(), json.dumps(results)),
        )


def _parse_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return url[:40]


def _clean_claim(title: str, snippet: str) -> str:
    source_text = (title or snippet).strip()
    source_text = " ".join(source_text.split())
    if not source_text:
        return "Search result returned relevant context."
    claim = source_text[:150].rstrip(".,:;")
    return f"{claim}."


def _search_queries(topic: str, idea_text: str, country_name: str, platform: str | None) -> list[str]:
    platform_clause = f" {platform}" if platform else ""
    topic_focus = " ".join(topic.split()[:6])
    idea_focus = " ".join(idea_text.split()[:10])
    return [
        f"{topic_focus} {country_name}{platform_clause} social media audience 2026",
        f"{idea_focus} {country_name}{platform_clause} youth innovation students 2026",
    ]


def _normalize_result(item: dict, source_name: str) -> dict:
    url = item.get("url") or item.get("link") or None
    title = item.get("title") or ""
    snippet = (item.get("content") or item.get("snippet") or "")[:500]
    source = item.get("source") or (_parse_domain(url) if url else source_name)
    return {
        "claim": _clean_claim(title, snippet),
        "source": source,
        "url": url,
        "snippet": snippet,
    }


def _dedupe_results(*collections: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for collection in collections:
        for item in collection:
            url = str(item.get("url") or "").strip().lower()
            identity = url or f"{str(item.get('source', '')).strip().lower()}::{str(item.get('claim', '')).strip().lower()}"
            key = ("url", identity) if url else ("text", identity)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
    return deduped


def _lexical_relevance(item: dict, idea_text: str, topic: str, country_name: str, platform: str | None) -> float:
    evidence_terms = _topic_terms(
        " ".join([
            str(item.get("claim", "")),
            str(item.get("snippet", "")),
            str(item.get("source", "")),
        ])
    )
    if not evidence_terms:
        return 0.0

    query_terms = _topic_terms(" ".join(filter(None, [idea_text, topic, country_name, platform or ""])))
    if not query_terms:
        return 0.0

    overlap = len(evidence_terms & query_terms)
    coverage = overlap / max(1, len(query_terms))
    density = overlap / max(1, len(evidence_terms))
    source_bonus = 0.15 if item.get("url") else 0.05
    return round(min(1.0, 0.7 * coverage + 0.2 * density + source_bonus), 4)


def _llm_rescore(results: list[dict], idea_text: str, topic: str, country_name: str, platform: str | None) -> list[dict]:
    from app.llm_client import call_llm_json, llm_available

    if not USE_LLM_EVIDENCE_SCORING or not llm_available() or not results:
        return results

    system = (
        "You score evidence relevance for social media strategy. "
        "Return only JSON, no markdown."
    )
    user = json.dumps({
        "idea_text": idea_text,
        "topic": topic,
        "country_name": country_name,
        "platform": platform,
        "results": [
            {
                "index": i,
                "claim": result.get("claim"),
                "source": result.get("source"),
                "snippet": result.get("snippet"),
            }
            for i, result in enumerate(results)
        ],
        "task": "Score each result from 1 to 5 for relevance to this exact idea and platform targeting.",
    }, ensure_ascii=False)

    try:
        raw = call_llm_json(system, user)
        score_map = {
            item["index"]: int(item["score"])
            for item in raw.get("scores", [])
            if isinstance(item, dict) and isinstance(item.get("index"), int) and str(item.get("score", "")).isdigit()
        }
        rescored: list[dict] = []
        for i, result in enumerate(results):
            score = score_map.get(i)
            if score is None or score < EVIDENCE_LLM_SCORE_THRESHOLD:
                continue
            rescored.append({**result, "relevance_score": max(result.get("relevance_score", 0.0), score / 5)})
        return rescored or results
    except Exception:
        return results


def _tavily_search(topic: str, idea_text: str, country_name: str, platform: str | None, max_results: int) -> list[dict]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=TAVILY_API_KEY)
    results = []
    for query in _search_queries(topic, idea_text, country_name, platform):
        response = client.search(query=query, max_results=max_results, include_answer=False)
        for item in response.get("results", []):
            results.append(_normalize_result(item, "tavily"))
            if len(results) >= max_results * 2:
                return results
    return results


def _serper_search(topic: str, idea_text: str, country_name: str, platform: str | None, max_results: int) -> list[dict]:
    import httpx

    results = []
    with httpx.Client(timeout=12) as client:
        for query in _search_queries(topic, idea_text, country_name, platform):
            response = client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": max_results, "gl": "qa", "hl": "en"},
            )
            response.raise_for_status()
            body = response.json()
            for item in body.get("organic", []):
                results.append(_normalize_result(item, "serper"))
                if len(results) >= max_results * 2:
                    return results
    return results


def _rank_results(results: list[dict], idea_text: str, topic: str, country_name: str, platform: str | None) -> list[dict]:
    ranked = []
    for result in results:
        score = _lexical_relevance(result, idea_text, topic, country_name, platform)
        if score <= 0:
            continue
        ranked.append({**result, "relevance_score": score})
    ranked.sort(
        key=lambda item: (
            item.get("relevance_score", 0.0),
            1 if item.get("url") else 0,
            len(str(item.get("snippet", ""))),
        ),
        reverse=True,
    )
    return ranked


def search_topic_evidence(
    topic: str,
    country_name: str,
    idea_text: str = "",
    platform: str | None = None,
    goal: str = "applications",
    max_results: int = 5,
) -> list[dict]:
    topic_norm = topic.strip().lower()
    idea_hash = hash_idea_text(idea_text or topic)
    curated_country = _load_country_evidence(country_name)
    cached = _cache_get(idea_hash, topic_norm, country_name)
    if cached is not None:
        combined = _dedupe_results(cached, curated_country)
        return combined[:max_results]

    fetched: list[dict] = []
    if platform:
        fetched.extend(search_platform_evidence(
            idea_text=idea_text or topic,
            topic=topic,
            goal=goal,
            platform=platform,
            max_results=max_results,
        ))

    if TAVILY_API_KEY:
        try:
            fetched.extend(_tavily_search(topic, idea_text, country_name, platform, max_results))
        except Exception:
            pass

    if SERPER_API_KEY:
        try:
            fetched.extend(_serper_search(topic, idea_text, country_name, platform, max_results))
        except Exception:
            pass

    if not fetched and (MOCK_MODE or (not TAVILY_API_KEY and not SERPER_API_KEY)):
        fetched = _load_fallback(topic, country_name)

    deduped = _dedupe_results(fetched, curated_country)
    ranked = _rank_results(deduped, idea_text, topic, country_name, platform)
    ranked = _llm_rescore(ranked[: max_results * 2], idea_text, topic, country_name, platform)
    final_results = _dedupe_results(ranked, curated_country)[:max_results]

    if final_results:
        _cache_set(idea_hash, topic_norm, country_name, final_results)

    return final_results or curated_country[:max_results]
