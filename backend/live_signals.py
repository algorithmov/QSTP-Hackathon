"""Live trend signals: pytrends + YouTube, with SQLite caching and JSON fallback."""
import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "masar.db"
FALLBACK_PATH = Path(__file__).parent / "data" / "trends_fallback.json"

ARAB_COUNTRIES = ["EG", "SA", "AE", "QA", "DZ", "MA", "JO", "SD", "IQ", "KW"]
CACHE_TTL_SECONDS = 6 * 3600

_fallback: Optional[dict] = None


def _load_fallback() -> dict:
    global _fallback
    if _fallback is None:
        _fallback = json.loads(FALLBACK_PATH.read_text())
    return _fallback


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cache_get(key: str) -> Optional[dict]:
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT data, cached_at FROM trends_cache WHERE cache_key=?", (key,)
        ).fetchone()
        conn.close()
        if row and (time.time() - row["cached_at"]) < CACHE_TTL_SECONDS:
            return json.loads(row["data"])
    except Exception:
        pass
    return None


def _cache_get_stale(key: str) -> Optional[dict]:
    """Return cached value even if expired — last resort before fallback."""
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT data FROM trends_cache WHERE cache_key=?", (key,)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row["data"])
    except Exception:
        pass
    return None


def _cache_set(key: str, data: dict) -> None:
    try:
        conn = _connect()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO trends_cache (cache_key, data, cached_at) VALUES (?,?,?)",
                (key, json.dumps(data), time.time()),
            )
        conn.close()
    except Exception as exc:
        logger.warning("cache write failed: %s", exc)


async def interest_by_country(topic: str) -> dict[str, int]:
    """Return {country_code: interest_0_to_100} for all Arab countries."""
    cache_key = f"ibc:{topic}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        result = await asyncio.to_thread(_pytrends_interest_by_country, topic)
        if result:
            _cache_set(cache_key, result)
            return result
    except Exception as exc:
        logger.warning("pytrends interest_by_country failed for %r: %s", topic, exc)

    stale = _cache_get_stale(cache_key)
    if stale:
        logger.info("serving stale cache for %r", topic)
        return stale

    return _fallback_interest(topic)


def _pytrends_interest_by_country(topic: str) -> dict[str, int]:
    from pytrends.request import TrendReq

    pt = TrendReq(hl="ar", tz=0, timeout=(10, 25), retries=1, backoff_factor=0.5)
    pt.build_payload([topic], timeframe="now 7-d", geo="")
    df = pt.interest_by_region(resolution="COUNTRY", inc_low_vol=True)
    if df is None or df.empty:
        return {}
    result = {}
    for code in ARAB_COUNTRIES:
        try:
            import pycountry
            country = pycountry.countries.get(alpha_2=code)
            if country is None:
                continue
            name = country.name
            if name in df.index:
                result[code] = int(df.loc[name, topic])
        except Exception:
            continue
    return result


async def trend_direction(topic: str, country: str) -> dict:
    """Return {direction: rising|flat|falling, change_pct: int}."""
    cache_key = f"td:{topic}:{country}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        result = await asyncio.to_thread(_pytrends_trend_direction, topic, country)
        if result:
            _cache_set(cache_key, result)
            return result
    except Exception as exc:
        logger.warning("pytrends trend_direction failed for %r/%s: %s", topic, country, exc)

    stale = _cache_get_stale(cache_key)
    if stale:
        return stale

    return _fallback_direction(topic, country)


def _pytrends_trend_direction(topic: str, country: str) -> dict:
    from pytrends.request import TrendReq

    pt = TrendReq(hl="ar", tz=0, timeout=(10, 25), retries=1, backoff_factor=0.5)
    pt.build_payload([topic], timeframe="now 7-d", geo=country)
    df = pt.interest_over_time()
    if df is None or df.empty or topic not in df.columns:
        return {}
    values = df[topic].tolist()
    if len(values) < 2:
        return {"direction": "flat", "change_pct": 0}
    mid = len(values) // 2
    first_half = sum(values[:mid]) / max(mid, 1)
    second_half = sum(values[mid:]) / max(len(values) - mid, 1)
    if first_half == 0:
        change_pct = 0
    else:
        change_pct = round((second_half - first_half) / first_half * 100)
    if change_pct >= 10:
        direction = "rising"
    elif change_pct <= -10:
        direction = "falling"
    else:
        direction = "flat"
    return {"direction": direction, "change_pct": change_pct}


def _fallback_interest(topic: str) -> dict[str, int]:
    fb = _load_fallback()
    # exact match first
    ibc = fb.get("interest_by_country", {})
    if topic in ibc:
        return ibc[topic]
    # fuzzy: find closest key
    for key in ibc:
        if any(w in key for w in topic.lower().split()):
            return ibc[key]
    # default
    defaults = {"EG": 60, "SA": 55, "AE": 50, "JO": 45, "MA": 45,
                "DZ": 40, "QA": 40, "KW": 38, "IQ": 35, "SD": 28}
    return defaults


def _fallback_direction(topic: str, country: str) -> dict:
    fb = _load_fallback()
    td = fb.get("trend_direction", {})
    for key in td:
        if topic in key or any(w in key for w in topic.lower().split()):
            country_data = td[key].get(country)
            if country_data:
                return country_data
    return {"direction": "flat", "change_pct": 0}


async def youtube_regional_signal(topic: str, country: str, api_key: str) -> Optional[dict]:
    """Fetch top popular YouTube videos for region as a corroborating signal."""
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": country,
                    "maxResults": 5,
                    "key": api_key,
                },
            )
            if resp.status_code != 200:
                return None
            items = resp.json().get("items", [])
            topic_lower = topic.lower()
            matches = [
                i for i in items
                if topic_lower in (i.get("snippet", {}).get("title", "") + " " +
                                   i.get("snippet", {}).get("description", "")).lower()
            ]
            return {"matching_videos": len(matches), "total_popular": len(items)}
    except Exception as exc:
        logger.warning("YouTube signal failed for %s/%s: %s", topic, country, exc)
        return None


async def capture_fallback(topics: Optional[list[str]] = None) -> None:
    """Capture live pytrends data into trends_fallback.json. Run once before demo."""
    if topics is None:
        topics = ["young inventors water tech", "student innovation",
                  "water technology", "arabic education", "entrepreneurship"]
    result: dict = {"interest_by_country": {}, "trend_direction": {}}
    for topic in topics:
        ibc = await interest_by_country(topic)
        result["interest_by_country"][topic] = ibc
        td_per_country = {}
        for code in ARAB_COUNTRIES:
            td_per_country[code] = await trend_direction(topic, code)
        result["trend_direction"][topic] = td_per_country
    FALLBACK_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    logger.info("Fallback data written to %s", FALLBACK_PATH)
