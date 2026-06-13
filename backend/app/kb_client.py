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
from kb.stars_intelligence import (
    generate_platform_report_context,
    get_last_sync,
    get_platform_intelligence,
    get_platform_stats,
    list_posts,
    sync_all_platforms,
    sync_seed_posts,
)
from kb.stars_importer import (
    import_all_from_dir,
    import_file,
    get_import_stats,
)

__all__ = [
    "list_countries",
    "list_platforms",
    "get_usage",
    "get_content_platform_fit",
    "get_audience_goal_map",
    "get_country",
    "search_topic_evidence",
    "list_posts",
    "get_platform_intelligence",
    "generate_platform_report_context",
    "sync_seed_posts",
    "sync_all_platforms",
    "get_last_sync",
    "get_platform_stats",
    "import_all_from_dir",
    "import_file",
    "get_import_stats",
]
