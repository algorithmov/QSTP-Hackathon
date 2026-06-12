"""Knowledge base backed by SQLite, seeded from data/kb_seed.json."""
import json
import os
import sqlite3
from pathlib import Path

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_SEED = _DATA / "kb_seed.json"
_DB = _DATA / "kb.sqlite"

_SAFE_USAGE = {"usage_score": 0.5, "peak_hours_local": [20], "source_note": "default"}
_SAFE_FIT = 0.5


def _db_is_stale() -> bool:
    if not _DB.exists():
        return True
    return _SEED.stat().st_mtime > _DB.stat().st_mtime


def _build_db() -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    seed = json.loads(_SEED.read_text())
    con = sqlite3.connect(_DB)
    cur = con.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS countries;
        DROP TABLE IF EXISTS platforms;
        DROP TABLE IF EXISTS platform_country_usage;
        DROP TABLE IF EXISTS content_type_platform_fit;
        DROP TABLE IF EXISTS audience_goal_map;

        CREATE TABLE countries (
            iso_code TEXT PRIMARY KEY,
            name TEXT,
            timezone TEXT,
            dominant_dialect TEXT,
            secondary_dialect TEXT
        );
        CREATE TABLE platforms (
            name TEXT PRIMARY KEY,
            primary_age_band TEXT,
            rewarded_formats TEXT,
            notes TEXT
        );
        CREATE TABLE platform_country_usage (
            platform TEXT,
            country_iso TEXT,
            usage_score REAL,
            peak_hours_local TEXT,
            source_note TEXT,
            PRIMARY KEY (platform, country_iso)
        );
        CREATE TABLE content_type_platform_fit (
            content_type TEXT,
            platform TEXT,
            fit_score REAL,
            PRIMARY KEY (content_type, platform)
        );
        CREATE TABLE audience_goal_map (
            goal TEXT PRIMARY KEY,
            audiences TEXT,
            preferred_platforms TEXT,
            preferred_languages TEXT
        );
    """)

    for row in seed["countries"]:
        cur.execute(
            "INSERT INTO countries VALUES (?,?,?,?,?)",
            (row["iso_code"], row["name"], row["timezone"],
             row["dominant_dialect"], row["secondary_dialect"]),
        )
    for row in seed["platforms"]:
        cur.execute(
            "INSERT INTO platforms VALUES (?,?,?,?)",
            (row["name"], row["primary_age_band"],
             json.dumps(row["rewarded_formats"]), row["notes"]),
        )
    for row in seed["platform_country_usage"]:
        cur.execute(
            "INSERT INTO platform_country_usage VALUES (?,?,?,?,?)",
            (row["platform"], row["country_iso"], row["usage_score"],
             json.dumps(row["peak_hours_local"]), row["source_note"]),
        )
    for row in seed["content_type_platform_fit"]:
        cur.execute(
            "INSERT INTO content_type_platform_fit VALUES (?,?,?)",
            (row["content_type"], row["platform"], row["fit_score"]),
        )
    for row in seed["audience_goal_map"]:
        cur.execute(
            "INSERT INTO audience_goal_map VALUES (?,?,?,?)",
            (row["goal"], json.dumps(row["audiences"]),
             json.dumps(row["preferred_platforms"]),
             json.dumps(row["preferred_languages"])),
        )

    con.commit()
    con.close()


def _con() -> sqlite3.Connection:
    return sqlite3.connect(_DB)


if _db_is_stale():
    _build_db()


def list_countries() -> list[dict]:
    with _con() as con:
        rows = con.execute("SELECT * FROM countries").fetchall()
    return [
        {
            "iso_code": r[0], "name": r[1], "timezone": r[2],
            "dominant_dialect": r[3], "secondary_dialect": r[4],
        }
        for r in rows
    ]


def list_platforms() -> list[dict]:
    with _con() as con:
        rows = con.execute("SELECT * FROM platforms").fetchall()
    return [
        {
            "name": r[0], "primary_age_band": r[1],
            "rewarded_formats": json.loads(r[2]), "notes": r[3],
        }
        for r in rows
    ]


def get_usage(platform: str, country_iso: str) -> dict:
    with _con() as con:
        row = con.execute(
            "SELECT usage_score, peak_hours_local, source_note "
            "FROM platform_country_usage WHERE platform=? AND country_iso=?",
            (platform, country_iso),
        ).fetchone()
    if not row:
        return _SAFE_USAGE.copy()
    return {
        "usage_score": row[0],
        "peak_hours_local": json.loads(row[1]),
        "source_note": row[2],
    }


def get_content_platform_fit(content_type: str, platform: str) -> float:
    with _con() as con:
        row = con.execute(
            "SELECT fit_score FROM content_type_platform_fit "
            "WHERE content_type=? AND platform=?",
            (content_type, platform),
        ).fetchone()
    return row[0] if row else _SAFE_FIT


def get_audience_goal_map(goal: str) -> dict:
    with _con() as con:
        row = con.execute(
            "SELECT audiences, preferred_platforms, preferred_languages "
            "FROM audience_goal_map WHERE goal=?",
            (goal,),
        ).fetchone()
    if not row:
        return {
            "audiences": ["general_public"],
            "preferred_platforms": ["TikTok", "Instagram", "YouTube"],
            "preferred_languages": ["ar", "mixed"],
        }
    return {
        "audiences": json.loads(row[0]),
        "preferred_platforms": json.loads(row[1]),
        "preferred_languages": json.loads(row[2]),
    }


def get_country(iso_code: str) -> dict | None:
    with _con() as con:
        row = con.execute(
            "SELECT iso_code, name, timezone, dominant_dialect, secondary_dialect "
            "FROM countries WHERE iso_code=?",
            (iso_code,),
        ).fetchone()
    if not row:
        return None
    return {
        "iso_code": row[0], "name": row[1], "timezone": row[2],
        "dominant_dialect": row[3], "secondary_dialect": row[4],
    }
