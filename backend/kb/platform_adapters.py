"""Per-platform content adapters for Stars of Science post ingestion.

Each adapter returns (posts, error_or_none). When no credentials exist the
adapter falls back to the seed slice so the store always has data.
Wire live fetches here when platform credentials become available.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

_YT_BASE = "https://www.googleapis.com/youtube/v3"
_SOS_CHANNEL_ID = "UCQ36ixRyMdlCuQDeMIJ8lqg"   # Stars Of Science official channel


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _url_id(url: str) -> str:
    """Stable short ID derived from a URL."""
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _detect_language(text: str) -> tuple[str, bool]:
    """Return (language_code, arabic_primary) from text content."""
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    ratio = arabic / max(len(text), 1)
    if ratio > 0.35:
        return "ar", True
    if ratio > 0.08:
        return "mixed", False
    return "en", False


def _parse_iso_duration(duration: str) -> int:
    """Parse YouTube ISO 8601 duration (PT1H2M3S) to seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mn, s = m.groups()
    return int(h or 0) * 3600 + int(mn or 0) * 60 + int(s or 0)


def _tavily_search(query: str, max_results: int = 10) -> list[dict]:
    """Run a Tavily search and return raw result dicts."""
    if not TAVILY_API_KEY:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results, search_depth="basic")
        return response.get("results", [])
    except Exception as exc:
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return []


def _serper_search(query: str, max_results: int = 10) -> list[dict]:
    """Run a Serper (Google) search and return normalised result dicts."""
    if not SERPER_API_KEY:
        return []
    try:
        r = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("organic", [])
        return [
            {"url": i.get("link", ""), "title": i.get("title", ""), "content": i.get("snippet", ""),
             "published_date": i.get("date", "")}
            for i in items
        ]
    except Exception as exc:
        logger.warning("Serper search failed for %r: %s", query, exc)
        return []


def _web_search(query: str, max_results: int = 10) -> list[dict]:
    """Try Tavily first, fall back to Serper."""
    results = _tavily_search(query, max_results)
    if not results:
        results = _serper_search(query, max_results)
    return results


def _dedupe(posts: list[dict]) -> list[dict]:
    """Remove posts with duplicate post_ids, keeping first occurrence."""
    seen: set[str] = set()
    out = []
    for p in posts:
        pid = p.get("post_id", "")
        if pid and pid not in seen:
            seen.add(pid)
            out.append(p)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# YouTube Adapter (YouTube Data API v3)
# ──────────────────────────────────────────────────────────────────────────────

class YouTubeAdapter:
    """Fetch all Stars of Science videos from the official YouTube channel."""

    def fetch(self, seed_posts: list[dict]) -> tuple[list[dict], str | None]:
        if not YOUTUBE_API_KEY:
            return seed_posts, None
        try:
            uploads_playlist = self._get_uploads_playlist()
            video_ids = self._get_all_video_ids(uploads_playlist)
            logger.info("YouTube: found %d video IDs", len(video_ids))
            videos = self._fetch_video_details(video_ids)
            posts = [self._normalize(v) for v in videos]
            # Preserve hand-crafted seed posts not already covered by the API
            api_ids = {p["post_id"] for p in posts}
            for s in seed_posts:
                if s["post_id"] not in api_ids:
                    posts.append(s)
            logger.info("YouTube: returning %d posts (%d from API, %d seed)", len(posts), len(videos), len(posts) - len(videos))
            return _dedupe(posts), None
        except Exception as exc:
            logger.exception("YouTube live fetch failed")
            return seed_posts, str(exc)

    def _get_uploads_playlist(self) -> str:
        r = httpx.get(
            f"{_YT_BASE}/channels",
            params={"id": _SOS_CHANNEL_ID, "part": "contentDetails", "key": YOUTUBE_API_KEY},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            raise RuntimeError("Stars of Science YouTube channel not found")
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def _get_all_video_ids(self, playlist_id: str) -> list[str]:
        ids: list[str] = []
        page_token: str | None = None
        while True:
            params: dict = {
                "playlistId": playlist_id,
                "part": "contentDetails",
                "maxResults": 50,
                "key": YOUTUBE_API_KEY,
            }
            if page_token:
                params["pageToken"] = page_token
            r = httpx.get(f"{_YT_BASE}/playlistItems", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            for item in data.get("items", []):
                ids.append(item["contentDetails"]["videoId"])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return ids

    def _fetch_video_details(self, video_ids: list[str]) -> list[dict]:
        videos: list[dict] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            r = httpx.get(
                f"{_YT_BASE}/videos",
                params={
                    "id": ",".join(batch),
                    "part": "snippet,statistics,contentDetails",
                    "key": YOUTUBE_API_KEY,
                },
                timeout=30,
            )
            r.raise_for_status()
            videos.extend(r.json().get("items", []))
        return videos

    def _normalize(self, v: dict) -> dict:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        content = v.get("contentDetails", {})
        video_id = v["id"]

        title = snippet.get("title", "")
        description = snippet.get("description", "") or ""
        published_raw = snippet.get("publishedAt", "")
        published_at = published_raw[:10] if published_raw else ""
        tags = snippet.get("tags", []) or []

        lang, arabic_primary = _detect_language(title + " " + description[:300])
        duration_secs = _parse_iso_duration(content.get("duration", ""))

        caption = description[:500].strip() if description.strip() else title

        return {
            "platform": "YouTube",
            "post_id": f"yt-{video_id}",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": published_at,
            "title": title,
            "caption": caption,
            "description": description[:2000],
            "hashtags": [f"#{t}" for t in tags[:10]],
            "media_type": "video",
            "views": int(stats.get("viewCount") or 0),
            "likes": int(stats.get("likeCount") or 0),
            "comments_count": int(stats.get("commentCount") or 0),
            "shares_count": 0,
            "transcript": "",
            "summary": title,
            "language": lang,
            "arabic_primary": arabic_primary,
            "source_name": "Stars of Science YouTube",
            "source_type": "youtube_api",
            "duration_seconds": duration_secs,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Instagram Adapter (Tavily/Serper web search)
# ──────────────────────────────────────────────────────────────────────────────

_IG_QUERIES = [
    'site:instagram.com "Stars of Science"',
    'site:instagram.com starsofscience',
    'site:instagram.com "نجوم العلوم" Stars Science',
    'site:instagram.com "#StarsOfScience"',
    'site:instagram.com "Stars of Science" innovator Qatar',
]


class InstagramAdapter:
    """Collect Instagram posts via Tavily/Serper web search."""

    def fetch(self, seed_posts: list[dict]) -> tuple[list[dict], str | None]:
        if not TAVILY_API_KEY and not SERPER_API_KEY:
            return seed_posts, None
        try:
            posts = list(seed_posts)  # start with seed
            seen_ids = {p["post_id"] for p in posts}
            new_count = 0
            for query in _IG_QUERIES:
                for result in _web_search(query, max_results=10):
                    url = result.get("url", "")
                    if "instagram.com" not in url:
                        continue
                    post = _normalize_web_result(result, "Instagram")
                    if post and post["post_id"] not in seen_ids:
                        posts.append(post)
                        seen_ids.add(post["post_id"])
                        new_count += 1
                time.sleep(0.3)
            logger.info("Instagram: %d new posts from web search", new_count)
            return _dedupe(posts), None
        except Exception as exc:
            logger.exception("Instagram web search failed")
            return seed_posts, str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# TikTok Adapter (no credentials yet)
# ──────────────────────────────────────────────────────────────────────────────

_TIKTOK_QUERIES = [
    'site:tiktok.com "Stars of Science"',
    'site:tiktok.com starsofscience',
    'site:tiktok.com "نجوم العلوم"',
]


class TikTokAdapter:
    """Collect TikTok posts via Tavily/Serper web search."""

    def fetch(self, seed_posts: list[dict]) -> tuple[list[dict], str | None]:
        if not TAVILY_API_KEY and not SERPER_API_KEY:
            return seed_posts, None
        try:
            posts = list(seed_posts)
            seen_ids = {p["post_id"] for p in posts}
            new_count = 0
            for query in _TIKTOK_QUERIES:
                for result in _web_search(query, max_results=10):
                    url = result.get("url", "")
                    if "tiktok.com" not in url:
                        continue
                    post = _normalize_web_result(result, "TikTok")
                    if post and post["post_id"] not in seen_ids:
                        posts.append(post)
                        seen_ids.add(post["post_id"])
                        new_count += 1
                time.sleep(0.3)
            logger.info("TikTok: %d new posts from web search", new_count)
            return _dedupe(posts), None
        except Exception as exc:
            logger.exception("TikTok web search failed")
            return seed_posts, str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# LinkedIn Adapter (Tavily/Serper web search)
# ──────────────────────────────────────────────────────────────────────────────

_LI_QUERIES = [
    'site:linkedin.com "Stars of Science"',
    'site:linkedin.com "Qatar Foundation" "Stars of Science"',
    'site:linkedin.com starsofscience innovation Arab',
    'site:linkedin.com "Stars of Science" season',
]


class LinkedInAdapter:
    """Collect LinkedIn posts via Tavily/Serper web search."""

    def fetch(self, seed_posts: list[dict]) -> tuple[list[dict], str | None]:
        if not TAVILY_API_KEY and not SERPER_API_KEY:
            return seed_posts, None
        try:
            posts = list(seed_posts)
            seen_ids = {p["post_id"] for p in posts}
            new_count = 0
            for query in _LI_QUERIES:
                for result in _web_search(query, max_results=10):
                    url = result.get("url", "")
                    if "linkedin.com" not in url:
                        continue
                    post = _normalize_web_result(result, "LinkedIn")
                    if post and post["post_id"] not in seen_ids:
                        posts.append(post)
                        seen_ids.add(post["post_id"])
                        new_count += 1
                time.sleep(0.3)
            logger.info("LinkedIn: %d new posts from web search", new_count)
            return _dedupe(posts), None
        except Exception as exc:
            logger.exception("LinkedIn web search failed")
            return seed_posts, str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# X Adapter (Tavily/Serper web search)
# ──────────────────────────────────────────────────────────────────────────────

_X_QUERIES = [
    'site:twitter.com "Stars of Science"',
    'site:x.com "Stars of Science"',
    'site:twitter.com starsofscience',
    'site:twitter.com "#StarsOfScience"',
    'site:twitter.com "نجوم العلوم" science Qatar',
]


class XAdapter:
    """Collect X/Twitter posts via Tavily/Serper web search."""

    def fetch(self, seed_posts: list[dict]) -> tuple[list[dict], str | None]:
        if not TAVILY_API_KEY and not SERPER_API_KEY:
            return seed_posts, None
        try:
            posts = list(seed_posts)
            seen_ids = {p["post_id"] for p in posts}
            new_count = 0
            for query in _X_QUERIES:
                for result in _web_search(query, max_results=10):
                    url = result.get("url", "")
                    if "twitter.com" not in url and "x.com" not in url:
                        continue
                    post = _normalize_web_result(result, "X")
                    if post and post["post_id"] not in seen_ids:
                        posts.append(post)
                        seen_ids.add(post["post_id"])
                        new_count += 1
                time.sleep(0.3)
            logger.info("X: %d new posts from web search", new_count)
            return _dedupe(posts), None
        except Exception as exc:
            logger.exception("X web search failed")
            return seed_posts, str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# Web result normalizer
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_web_result(result: dict, platform: str) -> dict | None:
    url = result.get("url", "").strip()
    if not url:
        return None

    title = (result.get("title") or "").strip()
    content = (result.get("content") or result.get("snippet") or "").strip()
    caption = content[:500] if content else title

    if not caption:
        return None

    published_raw = result.get("published_date") or result.get("date") or ""
    published_at = published_raw[:10] if published_raw else ""

    lang, arabic_primary = _detect_language(caption + " " + title)

    media_type_map = {
        "Instagram": "post",
        "TikTok": "video",
        "LinkedIn": "article",
        "X": "tweet",
    }

    return {
        "platform": platform,
        "post_id": f"{platform.lower()[:2]}-ws-{_url_id(url)}",
        "url": url,
        "published_at": published_at,
        "title": title,
        "caption": caption,
        "description": content[:2000],
        "hashtags": _extract_hashtags(caption + " " + title),
        "media_type": media_type_map.get(platform, "post"),
        "views": 0,
        "likes": 0,
        "comments_count": 0,
        "shares_count": 0,
        "transcript": "",
        "summary": title or caption[:120],
        "language": lang,
        "arabic_primary": arabic_primary,
        "source_name": f"Stars of Science {platform}",
        "source_type": "web_search",
    }


def _extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"#\w+", text)))[:10]


# ──────────────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────────────

_ADAPTERS: dict[str, object] = {
    "Instagram": InstagramAdapter(),
    "TikTok": TikTokAdapter(),
    "YouTube": YouTubeAdapter(),
    "LinkedIn": LinkedInAdapter(),
    "X": XAdapter(),
}


def fetch_all_platforms(
    seed_by_platform: dict[str, list[dict]],
) -> dict[str, tuple[list[dict], str | None]]:
    """Run all adapters and return {platform: (posts, error_or_none)}."""
    results: dict[str, tuple[list[dict], str | None]] = {}
    for platform, adapter in _ADAPTERS.items():
        seed = seed_by_platform.get(platform, [])
        try:
            posts, error = adapter.fetch(seed)  # type: ignore[attr-defined]
            results[platform] = (posts, error)
        except Exception as exc:
            logger.exception("Adapter %s raised an unexpected error", platform)
            results[platform] = (seed, str(exc))
    return results
