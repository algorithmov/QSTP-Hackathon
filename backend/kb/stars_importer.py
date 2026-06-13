"""Import scraped Stars of Science data from JSON and CSV files in data/imports/."""
from __future__ import annotations

import csv
import json
import logging
import sqlite3
import uuid
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_IMPORTS_DIR = _DATA / "imports"
_DB = _DATA / "kb.sqlite"

VALID_PLATFORMS = {"Instagram", "LinkedIn", "X", "YouTube", "TikTok"}

_FIELD_DEFAULTS: dict[str, Any] = {
    "url": "",
    "published_at": "",
    "title": "",
    "caption": "",
    "description": "",
    "hashtags": [],
    "media_type": "post",
    "views": 0,
    "likes": 0,
    "comments_count": 0,
    "shares_count": 0,
    "transcript": "",
    "summary": "",
    "language": "en",
    "arabic_primary": False,
    "source_name": "Stars of Science",
    "source_type": "import",
}


def _normalize_row(raw: dict) -> dict | None:
    """Normalize a raw scraped record to the stars_posts schema. Returns None for invalid rows."""
    platform = str(raw.get("platform", "")).strip()
    if platform not in VALID_PLATFORMS:
        return None

    post_id = str(raw.get("post_id", "")).strip()
    if not post_id:
        return None

    def _int(key: str) -> int:
        try:
            return int(float(raw.get(key) or 0))
        except (ValueError, TypeError):
            return 0

    def _str(key: str) -> str:
        return str(raw.get(key) or _FIELD_DEFAULTS.get(key, "")).strip()

    hashtags = raw.get("hashtags")
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]
    elif not isinstance(hashtags, list):
        hashtags = []

    arabic_primary = raw.get("arabic_primary")
    if isinstance(arabic_primary, str):
        arabic_primary = arabic_primary.lower() in ("true", "1", "yes")
    else:
        arabic_primary = bool(arabic_primary)

    return {
        "platform": platform,
        "post_id": post_id,
        "url": _str("url"),
        "published_at": _str("published_at"),
        "title": _str("title"),
        "caption": _str("caption"),
        "description": _str("description"),
        "hashtags": hashtags,
        "media_type": _str("media_type") or "post",
        "views": _int("views"),
        "likes": _int("likes"),
        "comments_count": _int("comments_count"),
        "shares_count": _int("shares_count"),
        "transcript": _str("transcript"),
        "summary": _str("summary"),
        "language": _str("language") or "en",
        "arabic_primary": arabic_primary,
        "source_name": _str("source_name") or "Stars of Science",
        "source_type": "import",
    }


def _ensure_import_table() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS stars_import_runs (
                run_id TEXT PRIMARY KEY,
                imported_at TEXT,
                filename TEXT,
                row_count INTEGER,
                inserted_count INTEGER,
                updated_count INTEGER,
                skipped_count INTEGER,
                per_platform_json TEXT
            )
        """)


def _parse_file(path: Path) -> tuple[list[dict], int]:
    """Parse JSON or CSV file. Returns (raw_rows, parse_error_count)."""
    suffix = path.suffix.lower()
    raw_rows: list[dict] = []
    errors = 0

    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                raw_rows = data
            elif isinstance(data, dict):
                for key in ("posts", "data", "records", "items"):
                    if key in data and isinstance(data[key], list):
                        raw_rows = data[key]
                        break
                else:
                    raw_rows = [data]
        except Exception as exc:
            logger.error("Failed to parse JSON %s: %s", path.name, exc)
            errors += 1

    elif suffix == ".csv":
        try:
            text = path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(StringIO(text))
            raw_rows = [dict(row) for row in reader]
        except Exception as exc:
            logger.error("Failed to parse CSV %s: %s", path.name, exc)
            errors += 1

    return raw_rows, errors


def _upsert_posts(posts: list[dict]) -> tuple[int, int]:
    """Upsert normalized posts into stars_posts. Returns (inserted, updated)."""
    inserted = 0
    updated = 0
    with sqlite3.connect(_DB) as con:
        for post in posts:
            exists = con.execute(
                "SELECT 1 FROM stars_posts WHERE post_id=?", (post["post_id"],)
            ).fetchone()
            con.execute(
                """
                INSERT OR REPLACE INTO stars_posts (
                    platform, post_id, url, published_at, title, caption, description,
                    hashtags_json, media_type, views, likes, comments_count, shares_count,
                    transcript, summary, language, arabic_primary, source_name, source_type, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post["platform"],
                    post["post_id"],
                    post["url"],
                    post["published_at"],
                    post["title"],
                    post["caption"],
                    post["description"],
                    json.dumps(post["hashtags"], ensure_ascii=False),
                    post["media_type"],
                    post["views"],
                    post["likes"],
                    post["comments_count"],
                    post["shares_count"],
                    post["transcript"],
                    post["summary"],
                    post["language"],
                    1 if post["arabic_primary"] else 0,
                    post["source_name"],
                    post["source_type"],
                    json.dumps(post, ensure_ascii=False),
                ),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
    return inserted, updated


def import_file(path: Path) -> dict:
    """Import a single JSON or CSV file. Returns a run-summary dict."""
    _ensure_import_table()

    raw_rows, parse_errors = _parse_file(path)
    normalized: list[dict] = []
    skipped = parse_errors

    for row in raw_rows:
        record = _normalize_row(row)
        if record:
            normalized.append(record)
        else:
            skipped += 1

    inserted, updated = _upsert_posts(normalized) if normalized else (0, 0)

    per_platform: dict[str, int] = {}
    for post in normalized:
        per_platform[post["platform"]] = per_platform.get(post["platform"], 0) + 1

    run_id = str(uuid.uuid4())
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO stars_import_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                path.name,
                len(raw_rows),
                inserted,
                updated,
                skipped,
                json.dumps(per_platform),
            ),
        )

    logger.info(
        "Import %s: %d rows, %d inserted, %d updated, %d skipped",
        path.name, len(raw_rows), inserted, updated, skipped,
    )
    return {
        "run_id": run_id,
        "filename": path.name,
        "row_count": len(raw_rows),
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "per_platform": per_platform,
    }


def import_all_from_dir(imports_dir: Path | None = None) -> list[dict]:
    """Import all JSON and CSV files from the imports directory."""
    directory = imports_dir or _IMPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = sorted(
        f for f in directory.iterdir()
        if f.suffix.lower() in (".json", ".csv") and f.is_file()
    )
    if not files:
        logger.info("No import files found in %s", directory)
        return []

    return [import_file(f) for f in files]


def get_import_stats() -> dict:
    """Return summary stats for all import runs."""
    _ensure_import_table()
    with sqlite3.connect(_DB) as con:
        rows = con.execute(
            "SELECT run_id, imported_at, filename, row_count, inserted_count, updated_count, "
            "skipped_count, per_platform_json "
            "FROM stars_import_runs ORDER BY imported_at DESC LIMIT 20"
        ).fetchall()
        total = con.execute("SELECT COUNT(*) FROM stars_import_runs").fetchone()
    return {
        "total_runs": int(total[0]) if total else 0,
        "recent_runs": [
            {
                "run_id": row[0],
                "imported_at": row[1],
                "filename": row[2],
                "row_count": int(row[3] or 0),
                "inserted_count": int(row[4] or 0),
                "updated_count": int(row[5] or 0),
                "skipped_count": int(row[6] or 0),
                "per_platform": json.loads(row[7] or "{}"),
            }
            for row in rows
        ],
    }
