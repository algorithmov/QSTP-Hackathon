"""Thin wrapper that imports from backend/kb/ and exposes it to app/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kb.knowledge_base import (
    get_audience_goal_map,
    get_content_platform_fit,
    get_country,
    get_usage,
    list_countries,
    list_platforms,
)
from kb.evidence import search_topic_evidence

__all__ = [
    "list_countries",
    "list_platforms",
    "get_usage",
    "get_content_platform_fit",
    "get_audience_goal_map",
    "get_country",
    "search_topic_evidence",
]
