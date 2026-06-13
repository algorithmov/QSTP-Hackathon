"""Run all Stars of Science scrapers in sequence.

Set credentials in backend/.env then run:
    cd backend
    .venv/bin/python scripts/scrape_all.py
"""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("scrape_all")

_SCRAPERS = [
    ("Instagram", "scripts.scrape_instagram"),
    ("X",         "scripts.scrape_x"),
    ("LinkedIn",  "scripts.scrape_linkedin"),
    ("TikTok",    "scripts.scrape_tiktok"),
]


def main() -> None:
    from kb import stars_intelligence as kb

    before = kb._count_posts_by_platform()
    logger.info("Posts before scraping: %s  total=%d", before, sum(before.values()))
    logger.info("")

    for platform, module_path in _SCRAPERS:
        logger.info("=" * 60)
        logger.info("▶  %s", platform)
        logger.info("=" * 60)
        try:
            mod = importlib.import_module(module_path)
            mod.main()
        except SystemExit:
            logger.warning("%s scraper exited early (likely missing credentials).", platform)
        except Exception as exc:
            logger.error("%s scraper failed: %s", platform, exc)
        logger.info("")

    after = kb._count_posts_by_platform()
    logger.info("=" * 60)
    logger.info("All scrapers complete.")
    logger.info("Posts after:  %s  total=%d", after, sum(after.values()))
    delta = sum(after.values()) - sum(before.values())
    logger.info("Net new posts: +%d", delta)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
