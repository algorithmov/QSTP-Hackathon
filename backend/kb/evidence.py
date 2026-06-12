"""Evidence search with SQLite cache and fallback JSON."""
import json
import os
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_DB = _DATA / "kb.sqlite"
_FALLBACK = _DATA / "fallback_evidence.json"

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TTL_HOURS = float(os.getenv("EVIDENCE_CACHE_TTL_HOURS", "24"))


def _ensure_cache_table() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS evidence_cache (
                topic_norm TEXT,
                country_name TEXT,
                fetched_at REAL,
                result_json TEXT,
                PRIMARY KEY (topic_norm, country_name)
            )
        """)


def _load_fallback(topic: str, country_name: str) -> list[dict]:
    if not _FALLBACK.exists():
        return []
    topic_norm = topic.strip().lower()
    entries = json.loads(_FALLBACK.read_text())
    for entry in entries:
        if (entry["topic"].strip().lower() == topic_norm and
                entry["country_name"].strip().lower() == country_name.strip().lower()):
            return entry.get("evidence", [])
    return []


def _cache_get(topic_norm: str, country_name: str) -> list[dict] | None:
    _ensure_cache_table()
    with sqlite3.connect(_DB) as con:
        row = con.execute(
            "SELECT fetched_at, result_json FROM evidence_cache "
            "WHERE topic_norm=? AND country_name=?",
            (topic_norm, country_name.strip().lower()),
        ).fetchone()
    if not row:
        return None
    age_hours = (time.time() - row[0]) / 3600
    if age_hours > TTL_HOURS:
        return None
    return json.loads(row[1])


def _cache_set(topic_norm: str, country_name: str, results: list[dict]) -> None:
    _ensure_cache_table()
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO evidence_cache VALUES (?,?,?,?)",
            (topic_norm, country_name.strip().lower(), time.time(), json.dumps(results)),
        )


def _parse_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return url[:40]


def _tavily_search(topic: str, country_name: str, max_results: int) -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(api_key=TAVILY_API_KEY)
    query = f"{topic} {country_name} social media audience trend 2025"
    response = client.search(query=query, max_results=max_results, include_answer=False)
    results = []
    for item in response.get("results", []):
        url = item.get("url", "")
        snippet = (item.get("content") or item.get("snippet") or "")[:300]
        claim = (item.get("title") or snippet)[:120].rstrip(".,:;") + "."
        results.append({
            "claim": claim,
            "source": _parse_domain(url) if url else item.get("source", "unknown"),
            "url": url or None,
            "snippet": snippet,
        })
    return results


def search_topic_evidence(topic: str, country_name: str, max_results: int = 3) -> list[dict]:
    topic_norm = topic.strip().lower()
    cached = _cache_get(topic_norm, country_name)
    if cached is not None:
        return cached[:max_results]

    if MOCK_MODE or not TAVILY_API_KEY:
        return _load_fallback(topic, country_name)[:max_results]

    try:
        results = _tavily_search(topic, country_name, max_results)
        if results:
            _cache_set(topic_norm, country_name, results)
            return results[:max_results]
    except Exception:
        pass

    fallback = _load_fallback(topic, country_name)
    if fallback:
        _cache_set(topic_norm, country_name, fallback)
    return fallback[:max_results]
