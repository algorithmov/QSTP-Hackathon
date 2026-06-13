"""Stars of Science content store, retrieval, and platform intelligence."""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from app.evidence_helpers import hash_idea_text, normalize_text

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "data"
_DB = _DATA / "kb.sqlite"
_SEED = _DATA / "stars_posts_seed.json"

_STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "from", "into", "about", "this", "that",
    "stars", "science", "starsofscience", "social", "media", "video", "post", "content",
    "show", "season", "episode", "idea", "arab", "arabic", "innovation", "innovators",
}

_GOAL_PLATFORM_FIT = {
    "applications": {"Instagram": 0.92, "TikTok": 0.95, "YouTube": 0.82, "LinkedIn": 0.64, "X": 0.60},
    "viewers": {"Instagram": 0.84, "TikTok": 0.94, "YouTube": 0.96, "LinkedIn": 0.50, "X": 0.72},
    "sponsors": {"Instagram": 0.66, "TikTok": 0.52, "YouTube": 0.84, "LinkedIn": 0.97, "X": 0.68},
}

_PLATFORM_NOTES = {
    "Instagram": "Reels and polished inventor spotlights consistently carry the strongest save and share behavior.",
    "TikTok": "Fast proof-first edits and build montages perform best when the working moment lands immediately.",
    "YouTube": "Longer explainers and full competition narratives work because viewers tolerate more setup for clarity.",
    "LinkedIn": "Impact framing, institutional credibility, and venture-building language align best with professional audiences.",
    "X": "Concise hooks, live reminders, and quote-led conversation posts work best when the point is immediately clear.",
}


def _con() -> sqlite3.Connection:
    return sqlite3.connect(_DB)


def _ensure_tables() -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    with _con() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS stars_posts (
                platform TEXT,
                post_id TEXT PRIMARY KEY,
                url TEXT,
                published_at TEXT,
                title TEXT,
                caption TEXT,
                description TEXT,
                hashtags_json TEXT,
                media_type TEXT,
                views INTEGER,
                likes INTEGER,
                comments_count INTEGER,
                shares_count INTEGER,
                transcript TEXT,
                summary TEXT,
                language TEXT,
                arabic_primary INTEGER,
                source_name TEXT,
                source_type TEXT,
                raw_json TEXT
            );

            CREATE TABLE IF NOT EXISTS stars_sync_runs (
                run_id TEXT PRIMARY KEY,
                synced_at TEXT,
                mode TEXT,
                inserted_count INTEGER,
                updated_count INTEGER,
                source_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS stars_sync_platform_state (
                platform TEXT PRIMARY KEY,
                last_synced_at TEXT,
                post_count INTEGER,
                last_error TEXT,
                last_mode TEXT
            );
        """)


def _seed_is_needed() -> bool:
    _ensure_tables()
    with _con() as con:
        row = con.execute("SELECT COUNT(*) FROM stars_posts").fetchone()
    return not row or int(row[0]) == 0


def _upsert_posts(posts: list[dict], mode: str) -> tuple[int, int]:
    """Upsert posts into stars_posts. Returns (inserted, updated)."""
    inserted = 0
    updated = 0
    with _con() as con:
        for post in posts:
            exists = con.execute(
                "SELECT 1 FROM stars_posts WHERE post_id=?",
                (post["post_id"],),
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
                    post.get("title", ""),
                    post.get("caption", ""),
                    post.get("description", ""),
                    json.dumps(post.get("hashtags", []), ensure_ascii=False),
                    post.get("media_type", ""),
                    int(post.get("views") or 0),
                    int(post.get("likes") or 0),
                    int(post.get("comments_count") or 0),
                    int(post.get("shares_count") or 0),
                    post.get("transcript", ""),
                    post.get("summary", ""),
                    post.get("language", "en"),
                    1 if post.get("arabic_primary") else 0,
                    post.get("source_name", "Stars of Science"),
                    post.get("source_type", mode),
                    json.dumps(post, ensure_ascii=False),
                ),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
    return inserted, updated


def _record_sync_run(mode: str, inserted: int, updated: int, source_count: int) -> None:
    with _con() as con:
        con.execute(
            "INSERT OR REPLACE INTO stars_sync_runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                mode,
                inserted,
                updated,
                source_count,
            ),
        )


def _update_platform_state(platform: str, mode: str, error: str | None) -> None:
    with _con() as con:
        count_row = con.execute(
            "SELECT COUNT(*) FROM stars_posts WHERE platform=?", (platform,)
        ).fetchone()
        count = int(count_row[0]) if count_row else 0
        con.execute(
            """INSERT OR REPLACE INTO stars_sync_platform_state
               (platform, last_synced_at, post_count, last_error, last_mode)
               VALUES (?, ?, ?, ?, ?)""",
            (
                platform,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                count,
                error,
                mode,
            ),
        )


def sync_seed_posts(mode: str = "seed") -> dict:
    _ensure_tables()
    posts = json.loads(_SEED.read_text())
    inserted, updated = _upsert_posts(posts, mode)
    _record_sync_run(mode, inserted, updated, len(posts))
    platforms = list({p["platform"] for p in posts})
    for platform in platforms:
        _update_platform_state(platform, mode, None)
    return {
        "mode": mode,
        "inserted_count": inserted,
        "updated_count": updated,
        "source_count": len(posts),
    }


def sync_all_platforms(mode: str = "adapter_sync") -> dict:
    """Sync posts via per-platform adapters, falling back to seed when no credentials exist."""
    from kb.platform_adapters import fetch_all_platforms

    _ensure_tables()
    all_seed_posts = json.loads(_SEED.read_text())
    seed_by_platform: dict[str, list[dict]] = {}
    for post in all_seed_posts:
        seed_by_platform.setdefault(post["platform"], []).append(post)

    adapter_results = fetch_all_platforms(seed_by_platform)

    total_inserted = 0
    total_updated = 0
    total_source = 0
    platform_summary: dict[str, dict] = {}

    for platform, (posts, error) in adapter_results.items():
        inserted, updated = _upsert_posts(posts, mode)
        _update_platform_state(platform, mode, error)
        total_inserted += inserted
        total_updated += updated
        total_source += len(posts)
        platform_summary[platform] = {
            "inserted": inserted,
            "updated": updated,
            "source_count": len(posts),
            "error": error,
        }

    _record_sync_run(mode, total_inserted, total_updated, total_source)
    return {
        "mode": mode,
        "inserted_count": total_inserted,
        "updated_count": total_updated,
        "source_count": total_source,
        "platforms": platform_summary,
    }


def get_platform_stats() -> list[dict]:
    """Return per-platform post counts and last sync state."""
    _ensure_tables()
    with _con() as con:
        count_rows = con.execute(
            "SELECT platform, COUNT(*) FROM stars_posts GROUP BY platform"
        ).fetchall()
        state_rows = con.execute(
            "SELECT platform, last_synced_at, post_count, last_error, last_mode "
            "FROM stars_sync_platform_state"
        ).fetchall()
    count_map = {row[0]: int(row[1]) for row in count_rows}
    state_map = {row[0]: row for row in state_rows}
    all_platforms = sorted(set(list(count_map.keys()) + list(state_map.keys())))
    result = []
    for platform in all_platforms:
        state = state_map.get(platform)
        result.append({
            "platform": platform,
            "post_count": count_map.get(platform, 0),
            "last_synced_at": state[1] if state else None,
            "last_error": state[3] if state else None,
            "last_mode": state[4] if state else None,
        })
    return result


def _count_posts_by_platform() -> dict[str, int]:
    """Return {platform: count} for all platforms in the store."""
    _ensure_tables()
    with _con() as con:
        rows = con.execute("SELECT platform, COUNT(*) FROM stars_posts GROUP BY platform").fetchall()
    return {row[0]: int(row[1]) for row in rows}


def _get_seed_posts_by_platform() -> dict[str, list[dict]]:
    """Return all current DB posts grouped by platform (for use as adapter input)."""
    _ensure_tables()
    with _con() as con:
        rows = con.execute(
            "SELECT platform, post_id, url, published_at, title, caption, description, "
            "hashtags_json, media_type, views, likes, comments_count, shares_count, "
            "transcript, summary, language, arabic_primary, source_name, source_type "
            "FROM stars_posts"
        ).fetchall()
    by_platform: dict[str, list[dict]] = {}
    for row in rows:
        post = {
            "platform": row[0], "post_id": row[1], "url": row[2], "published_at": row[3],
            "title": row[4], "caption": row[5], "description": row[6],
            "hashtags": json.loads(row[7] or "[]"),
            "media_type": row[8],
            "views": int(row[9] or 0), "likes": int(row[10] or 0),
            "comments_count": int(row[11] or 0), "shares_count": int(row[12] or 0),
            "transcript": row[13] or "", "summary": row[14] or "",
            "language": row[15] or "en", "arabic_primary": bool(row[16]),
            "source_name": row[17] or "", "source_type": row[18] or "",
        }
        by_platform.setdefault(row[0], []).append(post)
    return by_platform


def _row_to_post(row: tuple) -> dict:
    return {
        "platform": row[0],
        "post_id": row[1],
        "url": row[2],
        "published_at": row[3],
        "title": row[4],
        "caption": row[5],
        "description": row[6],
        "hashtags": json.loads(row[7] or "[]"),
        "media_type": row[8],
        "views": int(row[9] or 0),
        "likes": int(row[10] or 0),
        "comments_count": int(row[11] or 0),
        "shares_count": int(row[12] or 0),
        "transcript": row[13] or "",
        "summary": row[14] or "",
        "language": row[15] or "en",
        "arabic_primary": bool(row[16]),
        "source_name": row[17] or "Stars of Science",
        "source_type": row[18] or "seed",
        "raw_json": json.loads(row[19] or "{}"),
    }


def list_posts(platform: str | None = None) -> list[dict]:
    if _seed_is_needed():
        sync_seed_posts()
    with _con() as con:
        if platform:
            rows = con.execute(
                """
                SELECT platform, post_id, url, published_at, title, caption, description,
                       hashtags_json, media_type, views, likes, comments_count, shares_count,
                       transcript, summary, language, arabic_primary, source_name, source_type, raw_json
                FROM stars_posts WHERE platform=? ORDER BY published_at DESC
                """,
                (platform,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT platform, post_id, url, published_at, title, caption, description,
                       hashtags_json, media_type, views, likes, comments_count, shares_count,
                       transcript, summary, language, arabic_primary, source_name, source_type, raw_json
                FROM stars_posts ORDER BY platform, published_at DESC
                """
            ).fetchall()
    return [_row_to_post(row) for row in rows]


def get_last_sync() -> dict | None:
    _ensure_tables()
    with _con() as con:
        row = con.execute(
            "SELECT run_id, synced_at, mode, inserted_count, updated_count, source_count "
            "FROM stars_sync_runs ORDER BY synced_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        "run_id": row[0],
        "synced_at": row[1],
        "mode": row[2],
        "inserted_count": int(row[3] or 0),
        "updated_count": int(row[4] or 0),
        "source_count": int(row[5] or 0),
    }


def _terms(value: str) -> set[str]:
    return {
        token for token in normalize_text(value).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def _metric_strength(post: dict, max_values: dict[str, int]) -> float:
    # Log-scale normalization so a single viral outlier doesn't collapse every
    # other post's score. log(1+x)/log(1+max) maps 0→0 and max→1 smoothly.
    scores = []
    for key in ("views", "likes", "shares_count", "comments_count"):
        current = int(post.get(key) or 0)
        max_value = max(1, max_values.get(key, 1))
        scores.append(math.log1p(current) / math.log1p(max_value))
    return round(sum(scores) / len(scores), 4)


def _recency_score(published_at: str) -> float:
    try:
        post_date = datetime.strptime(published_at, "%Y-%m-%d").date()
    except ValueError:
        return 0.45
    days_old = max(0, (date.today() - post_date).days)
    if days_old <= 60:
        return 1.0
    if days_old <= 180:
        return 0.86
    if days_old <= 365:
        return 0.72
    if days_old <= 730:
        return 0.56
    return 0.42


def _sequence_bonus(query_terms: set[str], record_terms: set[str]) -> float:
    if not query_terms or not record_terms:
        return 0.0
    overlap = len(query_terms & record_terms)
    if overlap == 0:
        return 0.0
    return min(0.2, overlap / max(4, len(query_terms)))


def _goal_fit(goal: str, platform: str) -> float:
    return _GOAL_PLATFORM_FIT.get(goal, {}).get(platform, 0.7)


def _language_fit(suggested_language: str, post: dict) -> float:
    if suggested_language == "ar":
        return 1.0 if post.get("arabic_primary") else 0.55
    if suggested_language == "mixed":
        return 0.92 if post.get("arabic_primary") else 0.78
    return 0.9 if post.get("language") == "en" else 0.72


def _duration_fit(idea_text: str, platform: str) -> float:
    text = normalize_text(idea_text)
    long_form = any(phrase in text for phrase in ["six minute", "long form", "walks through", "deep dive", "full episode"])
    short_form = any(phrase in text for phrase in ["proof first", "vertical", "reel", "15 second", "30 second", "short clip"])
    if long_form:
        return {
            "YouTube": 1.0,
            "LinkedIn": 0.76,
            "Instagram": 0.54,
            "TikTok": 0.48,
            "X": 0.44,
        }.get(platform, 0.6)
    if short_form:
        return {
            "TikTok": 1.0,
            "Instagram": 0.92,
            "YouTube": 0.68,
            "X": 0.62,
            "LinkedIn": 0.55,
        }.get(platform, 0.6)
    return 0.7


def _build_match_text(post: dict) -> str:
    return " ".join(
        str(post.get(key, ""))
        for key in ("title", "caption", "description", "summary", "transcript")
    )


def search_platform_evidence(
    idea_text: str,
    topic: str,
    goal: str,
    platform: str,
    max_results: int = 5,
) -> list[dict]:
    posts = list_posts(platform)
    if not posts:
        return []

    query_terms = _terms(" ".join([idea_text, topic, goal, platform]))
    max_values = {
        "views": max(int(post.get("views") or 0) for post in posts) or 1,
        "likes": max(int(post.get("likes") or 0) for post in posts) or 1,
        "shares_count": max(int(post.get("shares_count") or 0) for post in posts) or 1,
        "comments_count": max(int(post.get("comments_count") or 0) for post in posts) or 1,
    }

    ranked: list[dict] = []
    for post in posts:
        record_terms = _terms(_build_match_text(post) + " " + " ".join(post.get("hashtags", [])))
        overlap = len(query_terms & record_terms)
        coverage = overlap / max(1, len(query_terms))
        density = overlap / max(1, len(record_terms))
        lexical = min(1.0, 0.72 * coverage + 0.18 * density + _sequence_bonus(query_terms, record_terms))
        performance = _metric_strength(post, max_values)
        recency = _recency_score(str(post.get("published_at", "")))
        goal_alignment = _goal_fit(goal, platform)
        score = round(0.48 * lexical + 0.24 * performance + 0.14 * recency + 0.14 * goal_alignment, 4)
        ranked.append({
            **post,
            "similarity_score": score,
            "performance_score": performance,
            "recency_score": recency,
            "goal_alignment": goal_alignment,
            "matched_text": _build_match_text(post),
        })

    ranked.sort(
        key=lambda item: (
            item["similarity_score"],
            item["performance_score"],
            item["recency_score"],
            item["published_at"],
            item["post_id"],
        ),
        reverse=True,
    )

    evidence: list[dict] = []
    for post in ranked[:max_results]:
        claim_bits = [post.get("title") or platform, post.get("summary") or post.get("caption")]
        claim = ". ".join(bit.strip().rstrip(".") for bit in claim_bits if bit).strip()
        evidence.append({
            "claim": claim[:220] + ("..." if len(claim) > 220 else ""),
            "source": post.get("source_name", f"Stars of Science {platform}"),
            "url": post.get("url"),
            "published_at": post.get("published_at"),
            "platform": platform,
            "metrics": {
                "views": int(post.get("views") or 0),
                "likes": int(post.get("likes") or 0),
                "shares": int(post.get("shares_count") or 0),
                "comments": int(post.get("comments_count") or 0),
            },
            "matched_text": post.get("matched_text", "")[:320],
            "evidence_type": "stars_post",
            "relevance_score": round(post["similarity_score"], 4),
        })
    return evidence


def get_platform_intelligence(
    idea_text: str,
    topic: str,
    content_type: str,
    suggested_language: str,
    goal: str,
    platform: str,
    content_platform_fit: float,
    duration_hint: str | None = None,
) -> dict:
    evidence = search_platform_evidence(idea_text, topic, goal, platform, max_results=5)
    posts = list_posts(platform)
    if not posts:
        return {
            "platform": platform,
            "fit_score": 0,
            "why": f"No Stars of Science records are available yet for {platform}.",
            "score_breakdown": [],
            "supporting_patterns": [],
            "top_evidence": [],
            "report_available": False,
        }

    top_matches = evidence[:5]
    semantic_match = round(sum(item.get("relevance_score", 0.0) for item in top_matches) / max(1, len(top_matches)), 4)
    top_post_ids = {item.get("url") for item in top_matches}
    matched_posts = [post for post in posts if post.get("url") in top_post_ids] or posts[:5]

    max_values = {
        "views": max(int(post.get("views") or 0) for post in posts) or 1,
        "likes": max(int(post.get("likes") or 0) for post in posts) or 1,
        "shares_count": max(int(post.get("shares_count") or 0) for post in posts) or 1,
        "comments_count": max(int(post.get("comments_count") or 0) for post in posts) or 1,
    }
    performance = round(sum(_metric_strength(post, max_values) for post in matched_posts) / max(1, len(matched_posts)), 4)
    language_fit = round(sum(_language_fit(suggested_language, post) for post in matched_posts) / max(1, len(matched_posts)), 4)
    goal_fit = _goal_fit(goal, platform)
    if duration_hint == "short_form":
        duration_fit = {"TikTok": 1.0, "Instagram": 0.92, "YouTube": 0.68, "X": 0.62, "LinkedIn": 0.55}.get(platform, 0.6)
    elif duration_hint == "long_form":
        duration_fit = {"YouTube": 1.0, "LinkedIn": 0.76, "Instagram": 0.54, "TikTok": 0.48, "X": 0.44}.get(platform, 0.6)
    else:
        duration_fit = _duration_fit(idea_text, platform)

    final = round(
        100
        * (
            0.30 * semantic_match
            + 0.20 * content_platform_fit
            + 0.16 * performance
            + 0.10 * language_fit
            + 0.10 * goal_fit
            + 0.14 * duration_fit
        )
    )

    media_counter = Counter(str(post.get("media_type") or "post") for post in matched_posts)
    top_media = media_counter.most_common(1)[0][0]
    arabic_ratio = sum(1 for post in matched_posts if post.get("arabic_primary")) / max(1, len(matched_posts))

    score_breakdown = [
        {
            "label": "Semantic match",
            "score": round(semantic_match, 3),
            "reason": f"Matched Stars of Science {platform} posts share overlapping themes with this {content_type.replace('_', ' ')} idea.",
        },
        {
            "label": "Format history",
            "score": round(content_platform_fit, 3),
            "reason": f"{platform} historically suits {content_type.replace('_', ' ')} content in the current Masar format model.",
        },
        {
            "label": "Performance strength",
            "score": round(performance, 3),
            "reason": f"Top matched {platform} posts show strong relative reach and engagement inside the Stars of Science dataset.",
        },
        {
            "label": "Goal alignment",
            "score": round(goal_fit, 3),
            "reason": f"{platform} aligns {'well' if goal_fit >= 0.8 else 'partially'} with the {goal} goal based on recent Stars of Science usage patterns.",
        },
        {
            "label": "Language fit",
            "score": round(language_fit, 3),
            "reason": "Matched posts reflect how Arabic, bilingual, or English delivery usually performs for this platform.",
        },
        {
            "label": "Duration intent",
            "score": round(duration_fit, 3),
            "reason": f"The idea framing implies a {'longer walkthrough' if duration_fit > 0.8 and platform == 'YouTube' else 'platform-native pacing'} pattern for {platform}.",
        },
    ]

    patterns = [
        f"{top_media.replace('_', ' ')} posts dominate the strongest similar {platform} examples in the Stars of Science dataset.",
        _PLATFORM_NOTES.get(platform, f"{platform} rewards clear content framing."),
        (
            "Arabic-primary posts are common among top matches."
            if arabic_ratio >= 0.6
            else "English-first or mixed-language posts appear more often among the strongest matches."
        ),
    ]

    strongest_signal = "semantic overlap" if semantic_match >= max(content_platform_fit, performance) else (
        "historical format success" if content_platform_fit >= performance else "post performance"
    )
    why = (
        f"{platform} ranks well because similar Stars of Science posts show strong {strongest_signal}, "
        f"and the platform's best examples already reward this kind of idea framing."
    )

    return {
        "platform": platform,
        "fit_score": final,
        "why": why,
        "score_breakdown": score_breakdown,
        "supporting_patterns": patterns,
        "top_evidence": top_matches,
        "report_available": bool(top_matches),
        "semantic_match": semantic_match,
        "performance_strength": performance,
        "goal_alignment": goal_fit,
        "language_fit": language_fit,
        "duration_fit": duration_fit,
        "content_platform_fit": content_platform_fit,
    }


def generate_platform_report_context(
    idea_text: str,
    topic: str,
    content_type: str,
    suggested_language: str,
    goal: str,
    platform: str,
    content_platform_fit: float,
    duration_hint: str | None = None,
) -> dict:
    intelligence = get_platform_intelligence(
        idea_text=idea_text,
        topic=topic,
        content_type=content_type,
        suggested_language=suggested_language,
        goal=goal,
        platform=platform,
        content_platform_fit=content_platform_fit,
        duration_hint=duration_hint,
    )
    evidence = intelligence.get("top_evidence", [])
    strengths = [
        f"Top matched {platform} records are centered on {topic.lower()[:60]}.",
        f"Recent {platform} posts show a {intelligence['performance_strength'] * 100:.0f}% relative performance strength inside the local dataset.",
        intelligence["supporting_patterns"][0] if intelligence.get("supporting_patterns") else _PLATFORM_NOTES.get(platform, ""),
    ]
    risks = []
    if intelligence["semantic_match"] < 0.55:
        risks.append("The current idea does not closely match the strongest historical Stars of Science examples on this platform.")
    if intelligence["goal_alignment"] < 0.7:
        risks.append(f"{platform} is not the strongest native fit for the {goal} goal compared with the rest of the platform set.")
    if intelligence["language_fit"] < 0.75:
        risks.append("Language choice may need adaptation because the strongest matched posts skew differently.")
    if not risks:
        risks.append("The main risk is execution quality: the opening seconds and proof moment still need to land quickly.")

    recommendations = [
        f"Lead with the clearest proof moment in the first beat so the {platform} creative pattern matches the strongest records.",
        f"Shape the asset like the best-performing {platform} {evidence[0]['platform'].lower() if evidence else platform.lower()} examples: concise hook, visible outcome, then context.",
        f"Keep the caption and CTA tuned to {goal} rather than explaining the whole story in copy.",
    ]
    return {
        **intelligence,
        "strengths": strengths,
        "risks": risks,
        "recommendations": recommendations,
        "cache_key": f"{hash_idea_text(idea_text)}::{platform}::{goal}",
    }


if _seed_is_needed():
    sync_seed_posts()
