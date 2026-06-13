"""Shared evidence assembly helpers for review and personalization flows."""
from __future__ import annotations

import hashlib
from typing import Iterable

COUNTRY_DIGITAL_REPORT_URLS = {
    "Egypt": "https://datareportal.com/digital-in-egypt",
    "Saudi Arabia": "https://datareportal.com/digital-in-saudi-arabia",
    "UAE": "https://datareportal.com/digital-in-the-united-arab-emirates",
    "Qatar": "https://datareportal.com/reports/digital-2026-qatar",
    "Algeria": "https://datareportal.com/digital-in-algeria",
    "Morocco": "https://datareportal.com/digital-in-morocco",
    "Jordan": "https://datareportal.com/digital-in-jordan",
    "Sudan": "https://datareportal.com/digital-in-sudan",
    "Iraq": "https://datareportal.com/digital-in-iraq",
    "Kuwait": "https://datareportal.com/digital-in-kuwait",
}

PLATFORM_REFERENCE_URLS = {
    "TikTok": "https://www.tiktok.com/business/en/blog",
    "Instagram": "https://creators.instagram.com/",
    "YouTube": "https://blog.youtube/",
    "LinkedIn": "https://business.linkedin.com/marketing-solutions",
    "X": "https://business.x.com/en",
}

_SOURCE_URLS = {
    "LinkedIn Marketing Solutions 2024": "https://business.linkedin.com/marketing-solutions",
    "Google MENA Insights 2025": "https://blog.youtube/",
    "Sprout Social Index 2024": "https://sproutsocial.com/insights/data/",
}


def evidence_target_count(country_iso: str) -> int:
    return 8 if country_iso in {"QA", "AE"} else 5


def normalize_text(value: str) -> str:
    normalized = " ".join(value.lower().split())
    return "".join(char if char.isalnum() or char.isspace() else " " for char in normalized)


def hash_idea_text(idea_text: str) -> str:
    normalized = " ".join(normalize_text(idea_text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def build_usage_evidence(country_name: str, platform: str, usage: dict) -> list[dict]:
    note = str(usage.get("source_note", "")).strip()
    if not note:
        return []

    source = note.split(",")[0].strip() or f"{platform} usage reference"
    url = None
    if source.startswith("DataReportal"):
        url = COUNTRY_DIGITAL_REPORT_URLS.get(country_name)
    else:
        url = _SOURCE_URLS.get(source)

    claim = note.rstrip(".") + "."
    return [{
        "claim": claim,
        "source": source,
        "url": url,
        "snippet": note,
    }]


def build_platform_note_evidence(platform_meta: dict) -> list[dict]:
    note = str(platform_meta.get("notes", "")).strip()
    platform = str(platform_meta.get("name", "")).strip()
    if not note or not platform:
        return []

    source = {
        "TikTok": "TikTok platform notes",
        "Instagram": "Instagram platform notes",
        "YouTube": "YouTube platform notes",
        "LinkedIn": "LinkedIn platform notes",
        "X": "X platform notes",
    }.get(platform, f"{platform} platform notes")

    return [{
        "claim": note.rstrip(".") + ".",
        "source": source,
        "url": PLATFORM_REFERENCE_URLS.get(platform),
        "snippet": note,
    }]


def merge_evidence(*collections: Iterable[dict], limit: int) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for collection in collections:
        for item in collection:
            claim = str(item.get("claim", "")).strip()
            source = str(item.get("source", "")).strip()
            url = str(item.get("url") or "").strip()
            if not claim or not source:
                continue
            key = (claim.lower(), source.lower(), url.lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append({
                "claim": claim,
                "source": source,
                "url": item.get("url"),
                "snippet": item.get("snippet", ""),
            })
            if len(merged) >= limit:
                return merged

    return merged
