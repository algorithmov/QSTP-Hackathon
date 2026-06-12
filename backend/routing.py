"""Routing engine: weighted scoring + LLM orchestration."""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import pytz

import knowledge_base as kb
import live_signals
import model_client
from llm_client import get_llm_output
from app.schemas import (
    MapEntry, Route, RouteRequest, RouteResponse, ScoreComponents,
    TrendTicker, VisualProfile,
)

logger = logging.getLogger(__name__)

# Scoring weights (visible on slide)
W_PLATFORM = 0.20
W_AUDIENCE = 0.15
W_GEO      = 0.25
W_TIMING   = 0.10
W_LANGUAGE = 0.10
W_PREDICT  = 0.20

ENABLE_DIALECT_REWRITE = os.getenv("ENABLE_DIALECT_REWRITE", "false").lower() == "true"


def _fallback_analyze(content_text: str, topic_hint: Optional[str]) -> dict:
    """Rule-based fallback when Claude is unavailable."""
    text_lower = content_text.lower()
    if any(w in text_lower for w in ["demo", "prototype", "product", "invention", "device"]):
        content_type = "product_demo"
    elif any(w in text_lower for w in ["interview", "speaks", "talks with"]):
        content_type = "interview"
    elif any(w in text_lower for w in ["group", "team", "students", "people"]):
        content_type = "group_action"
    else:
        content_type = "talking_head"

    if any(w in text_lower for w in ["ا", "ل", "م", "ن", "و"]):
        language = "ar"
    elif any(w in text_lower for w in ["arabic", "arab", "jordan", "egypt", "saudi"]):
        language = "ar"
    else:
        language = "en"

    topic = topic_hint or " ".join(content_text.split()[:5]).strip(".,")
    summary = content_text[:100].rstrip() + ("..." if len(content_text) > 100 else "")
    return {
        "content_summary": summary,
        "topic": topic,
        "content_type": content_type,
        "caption_length": min(len(content_text), 300),
        "hashtag_count": 5,
        "language": language,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _infer_format(content_type: str) -> str:
    vertical = {"talking_head", "product_demo", "text_overlay"}
    if content_type in vertical:
        return "vertical_short"
    return "horizontal_long"


def _language_fit(country_dialect: str, preferred_languages: list[str]) -> float:
    if country_dialect in preferred_languages:
        return 1.0
    # Gulf Arabic matches Gulf Arabic preferred etc.
    family = {"Gulf Arabic", "Egyptian Arabic", "Levantine Arabic",
              "Algerian Darija", "Moroccan Darija", "Sudanese Arabic", "Iraqi Arabic"}
    for pref in preferred_languages:
        if pref in family and country_dialect in family:
            return 0.75
        if "Arabic" in pref and "Arabic" in country_dialect:
            return 0.75
    return 0.50


def _local_time_str(hour: int) -> str:
    return f"{hour:02d}:00"


def _fallback_why(r: dict, topic: str) -> str:
    trend_note = ""
    chg = r.get("trend_change_pct", 0) or 0
    if r.get("trend_direction") == "rising" and chg > 0:
        trend_note = f"; topic up {chg} percent this week"
    return (
        f"{r['platform']} reaches {r['audience']} in {r['country_name']}"
        f"{trend_note}."
    )


# ── main routing ─────────────────────────────────────────────────────────────

async def route_content(request: RouteRequest) -> RouteResponse:
    # 1. Analyze content for routing parameters (topic, content_type, etc.)
    analysis = _fallback_analyze(request.content_text, request.topic_hint)
    topic: str = request.topic_hint or analysis["topic"]
    content_type: str = analysis["content_type"]
    caption_length: int = analysis["caption_length"]
    hashtag_count: int = analysis["hashtag_count"]
    text_language: str = analysis["language"]

    # 2. Vision analysis if media_url present
    visual_profile: Optional[VisualProfile] = None
    raw_visual: Optional[dict] = None
    if request.media_url:
        raw_visual = await model_client.vision_analyze(request.media_url)
        if raw_visual:
            content_type = raw_visual.get("content_type", content_type)
            text_language = raw_visual.get("detected_text_language", text_language)
            visual_profile = VisualProfile(
                content_type=raw_visual["content_type"],
                format=raw_visual["format"],
                has_text_overlay=raw_visual["has_text_overlay"],
                detected_text_language=raw_visual["detected_text_language"],
                face_count=raw_visual["face_count"],
                motion_level=raw_visual["motion_level"],
                energy_score=raw_visual["energy_score"],
                aspect_ratio=raw_visual["aspect_ratio"],
                confidence=raw_visual["confidence"],
            )

    # 3. Map goal to audiences
    audience_infos = kb.get_audiences_for_goal(request.goal)
    if not audience_infos:
        audience_infos = [{
            "audience": "general_public",
            "preferred_platforms": ["TikTok", "Instagram", "YouTube"],
            "preferred_languages": ["Egyptian Arabic", "Modern Standard Arabic"],
            "audience_fit_score": 0.70,
        }]
    audience_info = audience_infos[0]

    # 4. Live interest across Arab countries, top 8
    country_interests = await live_signals.interest_by_country(topic)
    top_countries = sorted(
        [(c, v) for c, v in country_interests.items() if v > 0],
        key=lambda x: x[1], reverse=True
    )[:8]

    # 5. Build candidates
    candidates: list[dict] = []
    candidate_meta: list[dict] = []

    content_format = (
        raw_visual["format"] if raw_visual else _infer_format(content_type)
    )
    motion_level = raw_visual["motion_level"] if raw_visual else 0.50
    energy_score = raw_visual["energy_score"] if raw_visual else 0.50
    has_text_overlay = raw_visual["has_text_overlay"] if raw_visual else False

    for country_code, interest in top_countries:
        country_info = kb.get_country(country_code)
        if not country_info:
            continue
        trend_info = await live_signals.trend_direction(topic, country_code)

        tz = pytz.timezone(country_info["timezone"])
        day_of_week = datetime.now(tz).weekday()

        for platform in audience_info["preferred_platforms"]:
            pcu = kb.get_platform_country_usage(platform, country_code)
            if not pcu:
                continue

            best_hour = pcu["peak_hours"][0]
            platform_fit = kb.get_content_type_platform_fit(content_type, platform)

            candidates.append({
                "platform": platform,
                "country": country_code,
                "hour_local": best_hour,
                "day_of_week": day_of_week,
                "content_type": content_type,
                "format": content_format,
                "has_text_overlay": has_text_overlay,
                "text_language": text_language,
                "caption_length": caption_length,
                "hashtag_count": hashtag_count,
                "motion_level": motion_level,
                "energy_score": energy_score,
            })
            candidate_meta.append({
                "platform": platform,
                "country": country_code,
                "country_name": country_info["name"],
                "audience": audience_info["audience"],
                "language": country_info["dominant_dialect"],
                "timezone": country_info["timezone"],
                "best_hour": best_hour,
                "interest": interest,
                "trend_direction": trend_info.get("direction", "flat"),
                "trend_change_pct": trend_info.get("change_pct", 0),
                "platform_fit": platform_fit,
                "audience_fit": audience_info["audience_fit_score"],
                "language_fit": _language_fit(
                    country_info["dominant_dialect"],
                    audience_info["preferred_languages"]
                ),
                "timing_reliability": kb.get_platform_timing_reliability(platform),
            })

    if not candidates:
        logger.warning("No candidates built — returning empty routes")
        return RouteResponse(
            request_id=str(uuid.uuid4()),
            content_summary=content_summary,
            visual_profile=visual_profile,
            routes=[],
            map_data=[],
            trend_ticker=[],
        )

    # 6. Batch predict
    predictions = await model_client.predict_fit_batch(candidates)

    # 7. Score and rank
    scored: list[dict] = []
    for meta, pred in zip(candidate_meta, predictions):
        geo_fit = meta["interest"] / 100.0
        if meta["trend_direction"] == "rising":
            geo_fit = min(1.0, geo_fit * 1.10)

        components = {
            "platform_fit": meta["platform_fit"],
            "audience_fit": meta["audience_fit"],
            "geo_fit": round(geo_fit, 4),
            "timing_fit": meta["timing_reliability"],
            "language_fit": meta["language_fit"],
            "predicted_engagement": pred["predicted_engagement"],
        }
        match_score = round(100 * (
            W_PLATFORM * components["platform_fit"] +
            W_AUDIENCE * components["audience_fit"] +
            W_GEO      * components["geo_fit"] +
            W_TIMING   * components["timing_fit"] +
            W_LANGUAGE * components["language_fit"] +
            W_PREDICT  * components["predicted_engagement"]
        ))
        scored.append({**meta, "components": components, "match_score": match_score})

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    top_6 = scored[:6]

    # 8. LLM: content_summary + why lines (Fanar → Gemini → local → rule-based)
    routes_for_llm = [
        {
            "rank":           i + 1,
            "platform":       r["platform"],
            "country_name":   r["country_name"],
            "audience":       r["audience"],
            "language":       r["language"],
            "match_score":    r["match_score"],
            "components":     r["components"],
            "trend_direction": r["trend_direction"],
            "trend_change_pct": r.get("trend_change_pct"),
            "post_time_local": _local_time_str(r["best_hour"]),
            "timezone":       r["timezone"],
        }
        for i, r in enumerate(top_6)
    ]
    llm_out = await get_llm_output(
        content_text=request.content_text,
        goal=request.goal,
        routes=routes_for_llm,
    )
    content_summary: str    = llm_out["content_summary"]
    why_by_rank:     dict   = llm_out["why"]
    rewrites_by_rank: dict  = llm_out["dialect_rewrites"]
    logger.info("LLM provider: %s", llm_out["provider_used"])

    # 9. Build routes
    routes = []
    for rank, r in enumerate(top_6, 1):
        why     = why_by_rank.get(str(rank), _fallback_why(r, topic))
        rewrite = rewrites_by_rank.get(str(rank)) if ENABLE_DIALECT_REWRITE else None
        routes.append(Route(
            rank=rank,
            platform=r["platform"],
            audience=r["audience"],
            country=r["country"],
            country_name=r["country_name"],
            language=r["language"],
            post_time_local=_local_time_str(r["best_hour"]),
            timezone=r["timezone"],
            match_score=r["match_score"],
            components=ScoreComponents(**r["components"]),
            why=why,
            trend_direction=r["trend_direction"],
            trend_change_pct=r["trend_change_pct"] if r["trend_change_pct"] else None,
            dialect_rewrite=rewrite if ENABLE_DIALECT_REWRITE else None,
        ))

    # 10. map_data and trend_ticker
    map_data: list[MapEntry] = []
    trend_ticker: list[TrendTicker] = []

    for country_code, interest in country_interests.items():
        country_info = kb.get_country(country_code)
        if not country_info:
            continue
        trend_info = await live_signals.trend_direction(topic, country_code)
        country_routes = [r for r in top_6 if r["country"] == country_code]
        best_platform = country_routes[0]["platform"] if country_routes else "TikTok"

        map_data.append(MapEntry(
            country=country_code,
            country_name=country_info["name"],
            interest=int(interest),
            trend_direction=trend_info.get("direction", "flat"),
            best_platform=best_platform,
        ))

        chg = trend_info.get("change_pct", 0)
        if trend_info.get("direction") == "rising" and chg and chg > 0:
            trend_ticker.append(TrendTicker(
                topic=topic,
                country=country_code,
                change_pct=int(chg),
                direction="rising",
            ))

    trend_ticker.sort(key=lambda t: t.change_pct, reverse=True)

    return RouteResponse(
        request_id=str(uuid.uuid4()),
        content_summary=content_summary,
        visual_profile=visual_profile,
        routes=routes,
        map_data=map_data,
        trend_ticker=trend_ticker,
    )
