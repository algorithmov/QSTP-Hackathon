"""Standalone Stars of Science ingestion script.

Run from the backend directory:
    .venv/bin/python scripts/ingest_stars.py

Fetches:
  - YouTube  : all videos from the official Stars of Science channel (YouTube Data API v3)
  - Instagram: Stars of Science posts discovered via Tavily/Serper web search
  - TikTok   : Stars of Science posts discovered via Tavily/Serper web search
  - LinkedIn : Stars of Science posts discovered via Tavily/Serper web search
  - X        : Stars of Science posts discovered via Tavily/Serper web search
"""
from __future__ import annotations

import sys
import os
import time
import logging
from pathlib import Path

# Ensure backend package is on the path when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_stars")


def main() -> None:
    from kb import stars_intelligence as kb
    from kb.platform_adapters import fetch_all_platforms

    # Ensure tables exist and seed is loaded
    kb.sync_seed_posts()
    before = kb._count_posts_by_platform()
    logger.info("Posts before ingestion: %s  total=%d", before, sum(before.values()))

    # Group current seed posts by platform for adapter input
    seed_by_platform = kb._get_seed_posts_by_platform()

    logger.info("Starting full platform ingestion…")
    t0 = time.time()

    results = fetch_all_platforms(seed_by_platform)

    # Upsert every platform's results
    total_inserted = 0
    total_updated = 0

    for platform, (posts, error) in results.items():
        if error:
            logger.warning("  %s: adapter reported error — %s", platform, error)
        if posts:
            inserted, updated = kb._upsert_posts(posts, mode="adapter_sync")
            kb._update_platform_state(platform, "adapter_sync", error)
            logger.info("  %s: %d posts  (+%d inserted  %d updated)",
                        platform, len(posts), inserted, updated)
            total_inserted += inserted
            total_updated += updated

    kb._record_sync_run("adapter_sync", total_inserted, total_updated, sum(len(p) for p, _ in results.values()))

    elapsed = time.time() - t0
    after = kb._count_posts_by_platform()
    logger.info("")
    logger.info("─" * 60)
    logger.info("Ingestion complete in %.1fs", elapsed)
    logger.info("Posts after ingestion: %s", after)
    logger.info("Total: %d posts  (+%d inserted  %d updated)", sum(after.values()), total_inserted, total_updated)
    logger.info("─" * 60)


if __name__ == "__main__":
    main()
