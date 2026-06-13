#!/usr/bin/env python3
"""Seed or refresh the local Stars of Science content store."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from kb.stars_intelligence import sync_seed_posts  # noqa: E402


def main() -> int:
    result = sync_seed_posts(mode="manual_seed_sync")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
