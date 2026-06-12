"""POST /api/review routing procedure."""
import json
import logging
import os
import re
import uuid
from typing import Any

from pydantic import BaseModel

import app.kb_client as kb
from app.evidence_helpers import (
    build_platform_note_evidence,
    build_usage_evidence,
    evidence_target_count,
    merge_evidence,
)
from app.scoring import compute_fit_score, confidence
from app.schemas import (
    EvidenceItem,
    IdeaSummary,
    MapDatum,
    Ranking,
    ReviewRequest,
    ReviewResponse,
    ReviewScope,
    ScoreComponents,
    VALID_CONTENT_TYPES,
)

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_LLM_ENRICHMENT = os.getenv("USE_LLM_ENRICHMENT", "false").lower() == "true"

METHODOLOGY_NOTE = (
    "Fit Score combines topic relevance, audience fit, platform fit, language fit, "
    "and timing fit using a transparent weighted formula. It is a directional fit "
    "ranking, not a prediction of views or engagement. Confidence reflects how much "
    "current evidence supports the topic relevance component."
)

_CONTENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "product_demo": ["demo", "prototype", "product", "invention", "device", "built", "filter", "machine", "gadget"],
    "talking_head": ["interview", "speaks", "talks", "explains", "discusses", "shares"],
    "educational": ["learn", "tutorial", "how to", "guide", "lesson", "teach", "explain"],
    "announcement": ["launch", "announce", "reveal", "introducing", "new", "release", "opening"],
    "behind_the_scenes": ["behind", "process", "making of", "preparation", "workshop", "lab"],
    "achievement_story": ["won", "award", "winner", "finalist", "achieved", "selected", "recognized", "star"],
}

_MOCK_IDEA_SUMMARY = IdeaSummary(
    topic="student innovation and technology",
    content_type="product_demo",
    primary_audience="young innovators and students",
    suggested_language="mixed",
    key_themes=["innovation", "technology", "youth"],
)

_GOAL_AUDIENCE_LABEL = {
    "applications": "student applicants",
    "viewers": "broad regional viewers",
    "sponsors": "innovation stakeholders",
}

_PLATFORM_STRENGTH = {
    "TikTok": "quick proof and first-second retention",
    "Instagram": "replayable reels and shareable saves",
    "YouTube": "explained demos and higher intent viewing",
    "LinkedIn": "credibility with professional and sponsor audiences",
    "X": "conversation hooks around timely ideas",
}


def _infer_content_type(text: str) -> str:
    text_lower = text.lower()
    for ct, keywords in _CONTENT_TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return ct
    return "talking_head"


def _infer_language(text: str) -> str:
    arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
    if arabic_chars > 5:
        return "ar"
    if arabic_chars > 0:
        return "mixed"
    return "en"


def _language_fit(suggested_language: str) -> float:
    return 1.0 if suggested_language in ("ar", "mixed") else 0.7


_GOAL_DEFAULT_LANGUAGE = {
    "applications": "mixed",
    "viewers": "ar",
    "sponsors": "mixed",
}

_COUNTRY_ALIASES: dict[str, list[str]] = {
    "EG": ["egypt", "egyptian", "cairo"],
    "SA": ["saudi", "saudi arabia", "riyadh", "jeddah"],
    "AE": ["uae", "u.a.e", "emirati", "emirates", "united arab emirates", "dubai", "abu dhabi"],
    "QA": ["qatar", "qatari", "doha"],
    "DZ": ["algeria", "algerian", "algiers"],
    "MA": ["morocco", "moroccan", "casablanca", "rabat"],
    "JO": ["jordan", "jordanian", "amman"],
    "SD": ["sudan", "sudanese", "khartoum"],
    "IQ": ["iraq", "iraqi", "baghdad"],
    "KW": ["kuwait", "kuwaiti"],
}


def _detect_country_scope(idea_text: str, countries: list[dict]) -> list[dict]:
    text = idea_text.lower()
    by_iso = {c["iso_code"]: c for c in countries}
    detected: list[dict] = []
    for iso, aliases in _COUNTRY_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias.lower())}\b", text) for alias in aliases):
            country = by_iso.get(iso)
            if country:
                detected.append(country)
    return detected


def _extract_idea_summary(idea_text: str, goal: str) -> IdeaSummary:
    from app.llm_client import llm_available

    if MOCK_MODE or not USE_LLM_ENRICHMENT or not llm_available():
        content_type = _infer_content_type(idea_text)
        detected = _infer_language(idea_text)
        language = detected if detected in ("ar",) else _GOAL_DEFAULT_LANGUAGE.get(goal, "mixed")
        _stop = {"a", "an", "the", "of", "in", "on", "at", "is", "are", "was", "by", "for",
                 "to", "and", "or", "that", "this", "she", "he", "it", "about", "clip", "idea",
                 "second", "post", "short", "video", "content"}
        words = [w.strip(".,:-") for w in idea_text.split() if w.strip(".,:-").lower() not in _stop and len(w) > 2]
        topic = " ".join(words[:6]) if words else "content idea"
        return IdeaSummary(
            topic=topic,
            content_type=content_type,
            primary_audience="young Arab innovators and students",
            suggested_language=language,
            key_themes=["innovation", "technology", "Arab youth"],
        )

    from app.llm_client import call_llm_json

    system = (
        "You are a social media strategy assistant. Extract a structured summary from the idea text. "
        "Return only a JSON object, no markdown, no commentary."
    )
    user = (
        f"Idea: {idea_text}\nGoal: {goal}\n\n"
        "Return this JSON object exactly:\n"
        '{"topic": "concise topic in 6 to 10 words", '
        '"content_type": "one of: product_demo, talking_head, educational, announcement, behind_the_scenes, achievement_story", '
        '"primary_audience": "who this content primarily reaches, 5 to 10 words", '
        '"suggested_language": "one of: ar, en, mixed", '
        '"key_themes": ["theme1", "theme2", "theme3"]}'
    )

    try:
        raw = call_llm_json(system, user)
        ct = raw.get("content_type", "talking_head")
        if ct not in VALID_CONTENT_TYPES:
            ct = _infer_content_type(idea_text)
        themes = raw.get("key_themes", [])
        if not isinstance(themes, list):
            themes = [str(themes)]
        return IdeaSummary(
            topic=str(raw.get("topic", "content idea"))[:120],
            content_type=ct,
            primary_audience=str(raw.get("primary_audience", "general audience"))[:100],
            suggested_language=raw.get("suggested_language", "mixed") if raw.get("suggested_language") in ("ar", "en", "mixed") else "mixed",
            key_themes=themes[:4],
        )
    except Exception as exc:
        logger.warning("idea_summary LLM call failed: %s", exc)
        return IdeaSummary(
            topic=idea_text[:80],
            content_type=_infer_content_type(idea_text),
            primary_audience="general Arab audience",
            suggested_language=_infer_language(idea_text),
            key_themes=["innovation", "content", "social media"],
        )


def _generate_why_lines(
    idea_summary: IdeaSummary,
    goal: str,
    candidates: list[dict],
    evidence_map: dict[str, list[dict]],
) -> dict[str, Any]:
    from app.llm_client import llm_available

    if MOCK_MODE or not USE_LLM_ENRICHMENT or not llm_available():
        result: dict[str, Any] = {}
        for c in candidates:
            key = f"{c['country']}__{c['platform']}"
            audience_label = _GOAL_AUDIENCE_LABEL.get(goal, idea_summary.primary_audience)
            topic_slice = " ".join(idea_summary.topic.split()[:4]).rstrip(".,")
            result[key] = {
                "why": (
                    f"{c['platform']} in {c['country_name']} fits {topic_slice} because it rewards "
                    f"{_PLATFORM_STRENGTH.get(c['platform'], 'clear storytelling')} for {audience_label}."
                ),
                "relevance_adjustment": 0.0,
                "evidence_indices": [],
            }
        return result

    from app.llm_client import call_llm_json

    ev_blocks = []
    for country_name, ev_list in evidence_map.items():
        for i, e in enumerate(ev_list):
            ev_blocks.append(f"[{country_name}:{i}] {e['claim']} ({e['source']})")

    candidates_block = json.dumps(
        [{"country": c["country"], "country_name": c["country_name"], "platform": c["platform"],
          "baseline_fit": round(c["baseline_score"], 2)} for c in candidates[:12]],
        ensure_ascii=False,
    )

    system = (
        "You are a social media strategy assistant for Stars of Science, an Arab innovation TV show. "
        "Return only a JSON object, no markdown, no commentary."
    )
    user = (
        f"Content topic: {idea_summary.topic}\n"
        f"Content type: {idea_summary.content_type}\n"
        f"Goal: {goal}\n"
        f"Candidates: {candidates_block}\n"
        f"Evidence items: {chr(10).join(ev_blocks) or 'none'}\n\n"
        "For each candidate produce a one-sentence explanation (12 to 20 words) of WHY this platform "
        "fits this content in that country — mention the audience type, content format advantage, "
        "or cultural fit. Do not just repeat the platform and country names. "
        "Also output relevance_adjustment in [-0.15, 0.15] (non-zero only when evidence supports), "
        "and evidence_indices listing which evidence items support it.\n"
        "Return a JSON object like this (one key per candidate, key format exactly <COUNTRY_ISO>__<Platform>):\n"
        "{\"EG__YouTube\": {\"why\": \"YouTube in Egypt reaches the largest student audience for demo-style innovation content.\", "
        "\"relevance_adjustment\": 0.0, \"evidence_indices\": []}, ...}\n"
        "Return only a JSON object, no markdown, no commentary."
    )

    try:
        return call_llm_json(system, user)
    except Exception as exc:
        logger.warning("why-lines LLM call failed: %s", exc)
        result = {}
        for c in candidates:
            key = f"{c['country']}__{c['platform']}"
            result[key] = {
                "why": f"{c['platform']} in {c['country_name']} is a strong fit based on audience and platform data.",
                "relevance_adjustment": 0.0,
                "evidence_indices": [],
            }
        return result


async def handle_review(request: ReviewRequest) -> ReviewResponse:
    idea_summary = _extract_idea_summary(request.idea_text, request.goal)

    countries = kb.list_countries()
    detected_countries = _detect_country_scope(request.idea_text, countries)
    scoring_countries = detected_countries or countries
    platforms = kb.list_platforms()
    platform_map = {platform["name"]: platform for platform in platforms}
    goal_map = kb.get_audience_goal_map(request.goal)
    preferred_platforms = goal_map.get("preferred_platforms", [p["name"] for p in platforms])

    lang_fit = _language_fit(idea_summary.suggested_language)
    timing_fit = 0.8

    all_candidates: list[dict] = []
    for country in scoring_countries:
        iso = country["iso_code"]
        for plat in platforms:
            pname = plat["name"]
            usage = kb.get_usage(pname, iso)
            platform_fit = kb.get_content_platform_fit(idea_summary.content_type, pname)
            usage_score = usage["usage_score"]
            audience_fit = usage_score if pname in preferred_platforms else usage_score * 0.6
            topic_relevance = usage_score
            baseline = compute_fit_score(
                topic_relevance, audience_fit, platform_fit, lang_fit, timing_fit
            )
            peak = usage["peak_hours_local"]
            all_candidates.append({
                "country": iso,
                "country_name": country["name"],
                "platform": pname,
                "usage_score": usage_score,
                "platform_fit": platform_fit,
                "audience_fit": audience_fit,
                "language_fit": lang_fit,
                "timing_fit": timing_fit,
                "topic_relevance": topic_relevance,
                "baseline_score": baseline,
                "peak_hours": peak,
                "timezone": country["timezone"],
                "source_note": usage["source_note"],
            })

    all_candidates.sort(key=lambda x: x["baseline_score"], reverse=True)

    top3_countries: list[str] = [c["iso_code"] for c in detected_countries]
    if not top3_countries:
        for c in all_candidates:
            if c["country"] not in top3_countries:
                top3_countries.append(c["country"])
            if len(top3_countries) == 3:
                break

    evidence_map: dict[str, list[dict]] = {}
    for iso in top3_countries:
        country_info = next((c for c in countries if c["iso_code"] == iso), None)
        if country_info:
            ev = kb.search_topic_evidence(
                idea_summary.topic,
                country_info["name"],
                max_results=evidence_target_count(iso),
            )
            evidence_map[country_info["name"]] = ev

    top_candidates = [c for c in all_candidates if c["country"] in top3_countries]
    why_lines = _generate_why_lines(idea_summary, request.goal, top_candidates, evidence_map)

    final_candidates: list[dict] = []
    for c in all_candidates:
        key = f"{c['country']}__{c['platform']}"
        ev_list = evidence_map.get(c["country_name"], [])
        why_data = why_lines.get(key, {})
        adj = float(why_data.get("relevance_adjustment", 0.0))
        adj = max(-0.15, min(0.15, adj))
        evidence_used = bool(ev_list)
        if evidence_used:
            topic_relevance = max(0.0, min(1.0, c["usage_score"] + adj))
        else:
            topic_relevance = c["usage_score"]
        fit = compute_fit_score(
            topic_relevance, c["audience_fit"], c["platform_fit"], c["language_fit"], c["timing_fit"]
        )
        ev_indices = why_data.get("evidence_indices", [])
        used_evidence: list[dict] = []
        for idx_str in (ev_indices if isinstance(ev_indices, list) else []):
            try:
                parts = str(idx_str).split(":")
                ev_country = parts[0] if len(parts) > 1 else c["country_name"]
                ev_idx = int(parts[-1])
                ev_pool = evidence_map.get(ev_country, [])
                if 0 <= ev_idx < len(ev_pool):
                    used_evidence.append(ev_pool[ev_idx])
            except Exception:
                pass
        if not used_evidence and ev_list:
            used_evidence = ev_list[: max(1, evidence_target_count(c["country"]) - 2)]
        contextual_evidence = merge_evidence(
            used_evidence,
            ev_list,
            build_usage_evidence(c["country_name"], c["platform"], {
                "source_note": c["source_note"],
            }),
            build_platform_note_evidence(platform_map.get(c["platform"], {})),
            limit=evidence_target_count(c["country"]),
        )
        final_candidates.append({
            **c,
            "topic_relevance": topic_relevance,
            "fit_score": fit,
            "confidence": confidence(evidence_used, c["usage_score"]),
            "why": why_data.get(
                "why",
                f"{c['platform']} fits {idea_summary.content_type} content in {c['country_name']}.",
            ),
            "evidence": contextual_evidence,
        })

    final_candidates.sort(key=lambda x: x["fit_score"], reverse=True)
    top8 = final_candidates[:8]

    rankings: list[Ranking] = []
    for rank, c in enumerate(top8, 1):
        peak_hour = c["peak_hours"][0] if c["peak_hours"] else 20
        rankings.append(Ranking(
            rank=rank,
            country=c["country"],
            country_name=c["country_name"],
            platform=c["platform"],
            fit_score=c["fit_score"],
            confidence=c["confidence"],
            components=ScoreComponents(
                topic_relevance=round(c["topic_relevance"], 3),
                audience_fit=round(c["audience_fit"], 3),
                platform_fit=round(c["platform_fit"], 3),
                language_fit=round(c["language_fit"], 3),
                timing_fit=round(c["timing_fit"], 3),
            ),
            why=c["why"],
            evidence=[EvidenceItem(**e) for e in c["evidence"]],
            recommended_time_local=f"{peak_hour:02d}:00",
            timezone=c["timezone"],
        ))

    map_data: list[MapDatum] = []
    best_by_country: dict[str, dict] = {}
    for c in final_candidates:
        iso = c["country"]
        if iso not in best_by_country or c["fit_score"] > best_by_country[iso]["fit_score"]:
            best_by_country[iso] = c
    for iso, c in sorted(best_by_country.items(), key=lambda x: x[1]["fit_score"], reverse=True):
        map_data.append(MapDatum(
            country=iso,
            country_name=c["country_name"],
            best_fit_score=c["fit_score"],
            best_platform=c["platform"],
        ))

    return ReviewResponse(
        request_id=str(uuid.uuid4()),
        idea_summary=idea_summary,
        review_scope=(
            ReviewScope(
                mode="country_focus",
                country=detected_countries[0]["iso_code"],
                country_name=detected_countries[0]["name"],
                reason=f"Country focus detected from the idea text: {detected_countries[0]['name']}.",
            )
            if len(detected_countries) == 1 else
            ReviewScope(
                mode="regional",
                country=None,
                country_name=None,
                reason="No single supported country was detected, so Masar compared all supported markets.",
            )
        ),
        rankings=rankings,
        map_data=map_data,
        methodology_note=METHODOLOGY_NOTE,
    )
