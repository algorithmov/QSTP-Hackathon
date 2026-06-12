"""POST /api/review routing procedure."""
import json
import logging
import os
import uuid
from typing import Any

from pydantic import BaseModel

import app.kb_client as kb
from app.scoring import compute_fit_score, confidence
from app.schemas import (
    EvidenceItem,
    IdeaSummary,
    MapDatum,
    Ranking,
    ReviewRequest,
    ReviewResponse,
    ScoreComponents,
    VALID_CONTENT_TYPES,
)

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

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
    "buzz": "mixed",
}


def _extract_idea_summary(idea_text: str, goal: str) -> IdeaSummary:
    if MOCK_MODE or not os.getenv("GROQ_API_KEY"):
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
    if MOCK_MODE or not os.getenv("GROQ_API_KEY"):
        result: dict[str, Any] = {}
        for c in candidates:
            key = f"{c['country']}__{c['platform']}"
            result[key] = {
                "why": (
                    f"{c['platform']} in {c['country_name']} scores well for "
                    f"{idea_summary.content_type} content reaching {idea_summary.primary_audience}."
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
        "For each candidate, write a why line (max 25 words, name the platform and country), "
        "a relevance_adjustment between -0.15 and 0.15 (only non-zero if evidence supports it), "
        "and evidence_indices listing which evidence items were used (e.g. [\"Egypt:0\"]).\n"
        "Return JSON: {\"<country>__<platform>\": {\"why\": \"...\", \"relevance_adjustment\": 0.0, \"evidence_indices\": []}, ...}"
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
    platforms = kb.list_platforms()
    goal_map = kb.get_audience_goal_map(request.goal)
    preferred_platforms = goal_map.get("preferred_platforms", [p["name"] for p in platforms])

    lang_fit = _language_fit(idea_summary.suggested_language)
    timing_fit = 0.8

    all_candidates: list[dict] = []
    for country in countries:
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

    top3_countries: list[str] = []
    for c in all_candidates:
        if c["country"] not in top3_countries:
            top3_countries.append(c["country"])
        if len(top3_countries) == 3:
            break

    evidence_map: dict[str, list[dict]] = {}
    for iso in top3_countries:
        country_info = next((c for c in countries if c["iso_code"] == iso), None)
        if country_info:
            ev = kb.search_topic_evidence(idea_summary.topic, country_info["name"])
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
        evidence_used = bool(ev_list) and abs(adj) > 0.001
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
        final_candidates.append({
            **c,
            "topic_relevance": topic_relevance,
            "fit_score": fit,
            "confidence": confidence(evidence_used, c["usage_score"]),
            "why": why_data.get("why", f"{c['platform']} fits this content type in {c['country_name']}."),
            "evidence": used_evidence,
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
        rankings=rankings,
        map_data=map_data,
        methodology_note=METHODOLOGY_NOTE,
    )
