"""TikTok scraper for Stars of Science using pyktok (no credentials needed).

Optional env:
    TIKTOK_PROFILES=starsofscience,starsofsciencetv
    TIKTOK_MAX_VIDEOS=200
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("scrape_tiktok")

TT_PROFILES = [p.strip().lstrip("@") for p in os.getenv("TIKTOK_PROFILES", "starsofscience").split(",") if p.strip()]
TT_MAX      = int(os.getenv("TIKTOK_MAX_VIDEOS", "200"))

_DATA = Path(__file__).resolve().parent.parent / "data"


def _detect_language(text: str) -> tuple[str, bool]:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    ratio = arabic / max(len(text), 1)
    if ratio > 0.35:
        return "ar", True
    if ratio > 0.08:
        return "mixed", False
    return "en", False


def _normalize_row(row: dict) -> dict | None:
    video_id = str(row.get("video_id") or row.get("id") or "")
    if not video_id:
        return None
    desc = str(row.get("video_description") or row.get("desc") or "")
    author = str(row.get("author_name") or row.get("author") or "")
    lang, arabic_primary = _detect_language(desc)
    hashtags = [f"#{m}" for m in re.findall(r"#(\w+)", desc)]
    create_time = row.get("video_timestamp") or row.get("createTime") or ""
    published_at = ""
    if create_time:
        try:
            from datetime import datetime, timezone
            if isinstance(create_time, (int, float)):
                published_at = datetime.fromtimestamp(int(create_time), tz=timezone.utc).strftime("%Y-%m-%d")
            else:
                published_at = str(create_time)[:10]
        except Exception:
            pass
    return {
        "platform": "TikTok",
        "post_id": f"tt-{video_id}",
        "url": f"https://www.tiktok.com/@{author}/video/{video_id}",
        "published_at": published_at,
        "title": "",
        "caption": desc[:500],
        "description": desc[:2000],
        "hashtags": hashtags[:10],
        "media_type": "video",
        "views": int(row.get("video_play_count") or row.get("playCount") or 0),
        "likes": int(row.get("video_like_count") or row.get("diggCount") or 0),
        "comments_count": int(row.get("video_comment_count") or row.get("commentCount") or 0),
        "shares_count": int(row.get("video_share_count") or row.get("shareCount") or 0),
        "transcript": "",
        "summary": desc[:120].replace("\n", " "),
        "language": lang,
        "arabic_primary": arabic_primary,
        "source_name": f"Stars of Science TikTok (@{author})",
        "source_type": "scraped",
    }


def main() -> None:
    try:
        import pyktok as pyk
    except ImportError:
        logger.error("pyktok not installed. Run: pip install pyktok")
        sys.exit(1)

    # pyktok needs browser cookies from Chrome, Edge, or Firefox
    for browser in ("chrome", "firefox", "edge"):
        try:
            pyk.specify_browser(browser)
            logger.info("Using %s browser cookies for TikTok.", browser)
            break
        except Exception:
            continue
    else:
        logger.warning("Could not find a browser with TikTok cookies. Results may be limited.")

    all_posts: list[dict] = []
    seen: set[str] = set()

    for profile in TT_PROFILES:
        logger.info("Scraping TikTok @%s (up to %d videos) …", profile, TT_MAX)
        profile_url = f"https://www.tiktok.com/@{profile}"
        csv_path = _DATA / f"tt_{profile}_raw.csv"

        try:
            pyk.save_tiktok_user_video(profile_url, True, str(csv_path), "chrome")
        except Exception as exc:
            logger.warning("pyktok failed for @%s: %s — trying alternate method.", profile, exc)
            try:
                pyk.save_tiktok_user_video(profile_url, True, str(csv_path))
            except Exception as exc2:
                logger.error("Both attempts failed for @%s: %s", profile, exc2)
                continue

        if not csv_path.exists():
            logger.warning("No CSV output for @%s.", profile)
            continue

        import csv
        count = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if count >= TT_MAX:
                    break
                normalized = _normalize_row(dict(row))
                if normalized and normalized["post_id"] not in seen:
                    all_posts.append(normalized)
                    seen.add(normalized["post_id"])
                    count += 1

        logger.info("  @%s: %d videos", profile, count)
        time.sleep(2)

    if not all_posts:
        logger.warning("No TikTok videos scraped.")
        return

    out_file = _DATA / "scraped_tiktok.json"
    out_file.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))
    logger.info("Saved %d videos → %s", len(all_posts), out_file)

    from kb import stars_intelligence as kb
    inserted, updated = kb._upsert_posts(all_posts, mode="scraped")
    kb._update_platform_state("TikTok", "scraped", None)
    logger.info("DB: +%d inserted  %d updated", inserted, updated)


if __name__ == "__main__":
    main()
