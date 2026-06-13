"""Persist uploaded review media files and their metadata."""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_MEDIA_DIR = _DATA / "media"
_DB = _DATA / "kb.sqlite"

ALLOWED_MIME_PREFIXES = ("image/", "video/", "audio/")
MAX_FILE_SIZE_BYTES = 18 * 1024 * 1024  # 18 MB — headroom under Gemini 20 MB inline ceiling


def _ensure_table() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS review_media (
                media_id TEXT PRIMARY KEY,
                review_id TEXT,
                original_filename TEXT,
                mime_type TEXT,
                file_size INTEGER,
                storage_path TEXT,
                uploaded_at TEXT
            )
        """)


def validate_mime(mime_type: str) -> bool:
    return any(mime_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)


def save_media(review_id: str, filename: str, content: bytes, mime_type: str) -> dict:
    """Save uploaded bytes to disk and record metadata. Returns a MediaAsset dict."""
    _ensure_table()
    media_id = str(uuid.uuid4())
    dest_dir = _MEDIA_DIR / review_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename).name  # strip any path traversal
    dest = dest_dir / safe_name
    dest.write_bytes(content)

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT INTO review_media VALUES (?, ?, ?, ?, ?, ?, ?)",
            (media_id, review_id, filename, mime_type, len(content), str(dest), now),
        )

    logger.info("Saved media %s (%d bytes) for review %s", filename, len(content), review_id)
    return {
        "media_id": media_id,
        "review_id": review_id,
        "original_filename": filename,
        "mime_type": mime_type,
        "file_size": len(content),
        "storage_path": str(dest),
        "uploaded_at": now,
    }
