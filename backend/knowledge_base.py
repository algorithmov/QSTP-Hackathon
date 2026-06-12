"""SQLite knowledge base: seeded from data/kb_seed.json at startup."""
import json
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "masar.db"
SEED_PATH = Path(__file__).parent / "data" / "kb_seed.json"

ARAB_COUNTRIES = {"EG", "SA", "AE", "QA", "DZ", "MA", "JO", "SD", "IQ", "KW"}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS platforms (
                platform TEXT PRIMARY KEY,
                primary_age_band TEXT,
                rewarded_formats TEXT,
                timing_reliability REAL,
                notes TEXT,
                source TEXT
            );

            CREATE TABLE IF NOT EXISTS platform_country_usage (
                platform TEXT,
                country TEXT,
                usage_score REAL,
                peak_hours TEXT,
                source TEXT,
                PRIMARY KEY (platform, country)
            );

            CREATE TABLE IF NOT EXISTS countries (
                code TEXT PRIMARY KEY,
                name TEXT,
                timezone TEXT,
                dominant_dialect TEXT,
                secondary_dialect TEXT
            );

            CREATE TABLE IF NOT EXISTS content_type_platform_fit (
                content_type TEXT,
                platform TEXT,
                fit_score REAL,
                source TEXT,
                PRIMARY KEY (content_type, platform)
            );

            CREATE TABLE IF NOT EXISTS audience_goal_map (
                goal TEXT PRIMARY KEY,
                audience TEXT,
                preferred_platforms TEXT,
                preferred_languages TEXT,
                audience_fit_score REAL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS trends_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                cached_at REAL
            );
        """)
    conn.close()
    _seed_db()


def _seed_db() -> None:
    seed = json.loads(SEED_PATH.read_text())
    conn = _connect()
    with conn:
        for row in seed["platforms"]:
            conn.execute(
                "INSERT OR IGNORE INTO platforms VALUES (?,?,?,?,?,?)",
                (row["platform"], row["primary_age_band"],
                 json.dumps(row["rewarded_formats"]),
                 row["timing_reliability"], row["notes"], row["source"]),
            )

        for row in seed["platform_country_usage"]:
            conn.execute(
                "INSERT OR IGNORE INTO platform_country_usage VALUES (?,?,?,?,?)",
                (row["platform"], row["country"], row["usage_score"],
                 json.dumps(row["peak_hours"]), row["source"]),
            )

        for row in seed["countries"]:
            conn.execute(
                "INSERT OR IGNORE INTO countries VALUES (?,?,?,?,?)",
                (row["code"], row["name"], row["timezone"],
                 row["dominant_dialect"], row["secondary_dialect"]),
            )

        for row in seed["content_type_platform_fit"]:
            conn.execute(
                "INSERT OR IGNORE INTO content_type_platform_fit VALUES (?,?,?,?)",
                (row["content_type"], row["platform"], row["fit_score"], row["source"]),
            )

        for row in seed["audience_goal_map"]:
            conn.execute(
                "INSERT OR IGNORE INTO audience_goal_map VALUES (?,?,?,?,?,?)",
                (row["goal"], row["audience"],
                 json.dumps(row["preferred_platforms"]),
                 json.dumps(row["preferred_languages"]),
                 row["audience_fit_score"], row["notes"]),
            )
    conn.close()


def get_country(code: str) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM countries WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_countries() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM countries").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_platform_country_usage(platform: str, country: str) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM platform_country_usage WHERE platform=? AND country=?",
        (platform, country),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["peak_hours"] = json.loads(d["peak_hours"])
    return d


def get_content_type_platform_fit(content_type: str, platform: str) -> float:
    conn = _connect()
    row = conn.execute(
        "SELECT fit_score FROM content_type_platform_fit WHERE content_type=? AND platform=?",
        (content_type, platform),
    ).fetchone()
    conn.close()
    if row:
        return row["fit_score"]
    row2 = conn.execute if False else None
    # fallback to unknown
    conn2 = _connect()
    row2 = conn2.execute(
        "SELECT fit_score FROM content_type_platform_fit WHERE content_type='unknown' AND platform=?",
        (platform,),
    ).fetchone()
    conn2.close()
    return row2["fit_score"] if row2 else 0.60


def get_platform_timing_reliability(platform: str) -> float:
    conn = _connect()
    row = conn.execute(
        "SELECT timing_reliability FROM platforms WHERE platform=?", (platform,)
    ).fetchone()
    conn.close()
    return row["timing_reliability"] if row else 0.75


def get_audiences_for_goal(goal: str) -> list[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM audience_goal_map WHERE goal=?", (goal,)).fetchone()
    conn.close()
    if not row:
        return []
    d = dict(row)
    d["preferred_platforms"] = json.loads(d["preferred_platforms"])
    d["preferred_languages"] = json.loads(d["preferred_languages"])
    return [d]
