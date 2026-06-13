"""POST /api/review routing procedure."""
from __future__ import annotations

import json
import logging
import os
import uuid

import app.kb_client as kb
from app.evidence_helpers import (
    build_platform_note_evidence,
    build_usage_evidence,
    evidence_target_count,
    merge_evidence,
)
from app.scoring import confidence
from app.schemas import (
    CountryFitBreakdownItem,
    CountryFitInsight,
    CountryFitResponse,
    EvidenceItem,
    IdeaSummary,
    MediaAsset,
    PlatformReportRequest,
    PlatformReportResponse,
    Ranking,
    ReviewRequest,
    ReviewResponse,
    ScoreBreakdownItem,
)

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_LLM_ENRICHMENT = os.getenv("USE_LLM_ENRICHMENT", "false").lower() == "true"

METHODOLOGY_NOTE = (
    "The AI Reviewer ranks only the five official Stars of Science platforms. "
    "Each score blends semantic similarity to matched Stars of Science posts, historical format fit, "
    "relative post performance inside the local dataset, goal alignment, and language fit. "
    "When media is uploaded Gemini refines the content-type, language, and duration signals used in scoring. "
    "The score is directional and evidence-backed; it is not a forecast of guaranteed views."
)

_CONTENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "product_demo": ["demo", "prototype", "product", "invention", "device", "built", "filter", "machine", "gadget"],
    "talking_head": ["interview", "speaks", "talks", "explains", "discusses", "shares"],
    "educational": ["learn", "tutorial", "how to", "guide", "lesson", "teach", "explain", "explainer", "walks through"],
    "announcement": ["launch", "announce", "reveal", "introducing", "new", "release", "opening", "apply"],
    "behind_the_scenes": ["behind", "process", "making of", "preparation", "workshop", "lab"],
    "achievement_story": ["won", "award", "winner", "finalist", "achieved", "selected", "recognized", "celebrates"],
}

_GOAL_DEFAULT_LANGUAGE = {
    "applications": "mixed",
    "viewers": "ar",
    "sponsors": "mixed",
}


def _infer_content_type(text: str) -> str:
    text_lower = text.lower()
    for ct, keywords in _CONTENT_TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return ct
    return "talking_head"


def _infer_language(text: str) -> str:
    arabic_chars = sum(1 for char in text if "؀" <= char <= "ۿ")
    if arabic_chars > 5:
        return "ar"
    if arabic_chars > 0:
        return "mixed"
    return "en"


def _extract_idea_summary(idea_text: str, goal: str) -> IdeaSummary:
    content_type = _infer_content_type(idea_text)
    detected = _infer_language(idea_text)
    language = detected if detected == "ar" else _GOAL_DEFAULT_LANGUAGE.get(goal, "mixed")
    stopwords = {
        "a", "an", "the", "of", "in", "on", "at", "is", "are", "was", "by", "for",
        "to", "and", "or", "that", "this", "she", "he", "it", "about", "clip", "idea",
        "second", "post", "short", "video", "content",
    }
    words = [
        token.strip(".,:-")
        for token in idea_text.split()
        if token.strip(".,:-").lower() not in stopwords and len(token) > 2
    ]
    topic = " ".join(words[:6]) if words else "content idea"
    return IdeaSummary(
        topic=topic,
        content_type=content_type,
        primary_audience="young Arab innovators and students",
        suggested_language=language,
        key_themes=["innovation", "technology", "Arab youth"],
    )


def _apply_media_overrides(
    idea_summary: IdeaSummary,
    media_context: dict,
) -> tuple[IdeaSummary, str | None]:
    """Refine idea_summary inputs using Gemini media context.

    Returns (possibly-updated IdeaSummary, duration_hint | None).
    Only overrides when Gemini produced a valid value; text-only path is unchanged.
    """
    ict = media_context.get("inferred_content_type")
    il = media_context.get("inferred_language")
    ds = media_context.get("duration_signal")

    updated = idea_summary
    if ict and ict != idea_summary.content_type:
        updated = updated.model_copy(update={"content_type": ict})
    if il and il != idea_summary.suggested_language:
        updated = updated.model_copy(update={"suggested_language": il})

    return updated, ds or None


def _build_rank_candidates(
    idea_text: str,
    goal: str,
    idea_summary: IdeaSummary,
    duration_hint: str | None = None,
) -> list[dict]:
    candidates: list[dict] = []
    for platform_meta in kb.list_platforms():
        platform = platform_meta["name"]
        content_platform_fit = kb.get_content_platform_fit(idea_summary.content_type, platform)
        intelligence = kb.get_platform_intelligence(
            idea_text=idea_text,
            topic=idea_summary.topic,
            content_type=idea_summary.content_type,
            suggested_language=idea_summary.suggested_language,
            goal=goal,
            platform=platform,
            content_platform_fit=content_platform_fit,
            duration_hint=duration_hint,
        )
        conf = confidence(bool(intelligence["top_evidence"]), max(
            intelligence.get("semantic_match", 0.0),
            intelligence.get("performance_strength", 0.0),
        ))
        candidates.append({
            **intelligence,
            "confidence": conf,
        })
    candidates.sort(key=_ranking_sort_key, reverse=True)
    return candidates


def _country_fit_reason(country_name: str, strongest_platform: str, fit_score: int) -> str:
    if fit_score >= 78:
        tone = "very strong"
    elif fit_score >= 66:
        tone = "strong"
    else:
        tone = "moderate"
    return (
        f"{country_name} is a {tone} audience match for this idea, led by {strongest_platform} "
        "and supported by the current Stars of Science platform patterns."
    )


async def handle_country_fit(request: ReviewRequest) -> CountryFitResponse:
    idea_summary = _extract_idea_summary(request.idea_text, request.goal)
    candidates = _build_rank_candidates(request.idea_text, request.goal, idea_summary)
    platform_meta_map = {platform["name"]: platform for platform in kb.list_platforms()}
    platform_weight_total = sum(max(candidate["fit_score"], 1) for candidate in candidates) or 1

    countries: list[CountryFitInsight] = []
    for country in kb.list_countries():
        breakdown: list[CountryFitBreakdownItem] = []
        evidence_groups: list[list[dict]] = []
        top_platform = candidates[0]["platform"]
        top_contribution = -1.0
        weighted_sum = 0.0

        for candidate in candidates:
            usage = kb.get_usage(candidate["platform"], country["iso_code"])
            platform_weight = max(candidate["fit_score"], 1) / platform_weight_total
            contribution = platform_weight * usage["usage_score"] * 100
            weighted_sum += contribution
            if contribution > top_contribution:
                top_contribution = contribution
                top_platform = candidate["platform"]

            evidence_groups.append(candidate["top_evidence"])
            evidence_groups.append(build_usage_evidence(country["name"], candidate["platform"], usage))
            evidence_groups.append(build_platform_note_evidence(platform_meta_map.get(candidate["platform"], {})))
            breakdown.append(
                CountryFitBreakdownItem(
                    platform=candidate["platform"],
                    platform_fit_score=candidate["fit_score"],
                    country_usage_score=round(float(usage["usage_score"]), 2),
                    blended_contribution=round(contribution, 1),
                    reason=(
                        f"{candidate['platform']} review fit ({candidate['fit_score']}) is blended with "
                        f"{country['name']}'s local usage score ({usage['usage_score']:.2f})."
                    ),
                )
            )

        breakdown.sort(key=lambda item: item.blended_contribution, reverse=True)
        audience_fit_score = max(1, min(100, round(weighted_sum)))
        merged_evidence = merge_evidence(*evidence_groups, limit=evidence_target_count(country["iso_code"]))
        country_confidence = confidence(bool(merged_evidence), audience_fit_score / 100)
        countries.append(
            CountryFitInsight(
                country=country["iso_code"],
                country_name=country["name"],
                audience_fit_score=audience_fit_score,
                confidence=country_confidence,
                strongest_platform=top_platform,
                why=_country_fit_reason(country["name"], top_platform, audience_fit_score),
                breakdown=breakdown,
                evidence=[EvidenceItem(**item) for item in merged_evidence],
            )
        )

    countries.sort(
        key=lambda item: (item.audience_fit_score, item.breakdown[0].blended_contribution, item.country_name),
        reverse=True,
    )
    return CountryFitResponse(request_id=str(uuid.uuid4()), countries=countries)


def _ranking_sort_key(candidate: dict) -> tuple:
    return (
        candidate["fit_score"],
        candidate["semantic_match"],
        candidate["performance_strength"],
        candidate["content_platform_fit"],
        candidate["platform"],
    )


def _fallback_platform_report(platform: str, context: dict, idea_summary: IdeaSummary, goal: str, media_context: dict | None = None) -> str:
    evidence = context.get("top_evidence", [])
    strongest = evidence[0] if evidence else None
    lead = (
        f"{platform} is a strong fit for this {idea_summary.content_type.replace('_', ' ')} idea because "
        f"the closest Stars of Science records already reward similar framing."
        if context["fit_score"] >= 75 else
        f"{platform} can work, but the idea needs adaptation because the best Stars of Science examples on this platform are narrower."
    )
    if strongest:
        lead += (
            f" The strongest matched record is '{strongest['claim'][:90]}' "
            f"with visible platform traction and a relevance score of {strongest.get('relevance_score', 0):.2f}."
        )
    lead += (
        f" For the {goal} goal, keep the opening tuned to the platform's native pattern, "
        "use one visible proof moment, and avoid pushing context before payoff."
    )
    if media_context and media_context.get("media_kind") != "none":
        scene = media_context.get("scene_summary") or media_context.get("transcript_or_audio_summary")
        if scene:
            lead += f" The uploaded media shows: {scene[:120].rstrip('.')}."
    return lead


def _generate_platform_report_analysis(
    platform: str,
    goal: str,
    idea_text: str,
    idea_summary: IdeaSummary,
    context: dict,
    media_context: dict | None = None,
) -> str:
    from app.llm_client import call_llm_json, llm_available

    if MOCK_MODE or not USE_LLM_ENRICHMENT or not llm_available():
        return _fallback_platform_report(platform, context, idea_summary, goal, media_context)

    system = (
        "You are a social media strategist for Stars of Science. "
        "Write a grounded, evidence-led platform analysis and return only JSON."
    )
    payload: dict = {
        "platform": platform,
        "goal": goal,
        "idea_text": idea_text,
        "idea_summary": idea_summary.model_dump(),
        "fit_score": context["fit_score"],
        "score_breakdown": context["score_breakdown"],
        "supporting_patterns": context["supporting_patterns"],
        "strengths": context["strengths"],
        "risks": context["risks"],
        "recommendations": context["recommendations"],
        "evidence": context["top_evidence"],
        "task": (
            "Write one detailed paragraph explaining exactly why this idea would or would not work on this platform. "
            "Reference the evidence and platform patterns directly. Do not invent metrics or unsupported claims."
        ),
    }
    if media_context and media_context.get("media_kind") != "none":
        payload["media_context"] = {k: v for k, v in media_context.items() if k != "caption_drafts"}
    user = json.dumps(payload, ensure_ascii=False)

    try:
        raw = call_llm_json(system, user)
        analysis = str(raw.get("analysis", "")).strip()
        return analysis or _fallback_platform_report(platform, context, idea_summary, goal, media_context)
    except Exception as exc:
        logger.warning("platform report LLM call failed: %s", exc)
        return _fallback_platform_report(platform, context, idea_summary, goal, media_context)


async def handle_review(
    request: ReviewRequest,
    saved_assets: list[dict] | None = None,
    media_context: dict | None = None,
) -> ReviewResponse:
    idea_summary = _extract_idea_summary(request.idea_text, request.goal)

    # Apply Gemini-derived overrides to scoring inputs (text-only path unchanged when no media)
    duration_hint: str | None = None
    if media_context and media_context.get("media_kind") != "none":
        idea_summary, duration_hint = _apply_media_overrides(idea_summary, media_context)

    candidates = _build_rank_candidates(request.idea_text, request.goal, idea_summary, duration_hint)
    rankings: list[Ranking] = []
    for index, candidate in enumerate(candidates[:5], start=1):
        rankings.append(
            Ranking(
                rank=index,
                platform=candidate["platform"],
                fit_score=candidate["fit_score"],
                confidence=candidate["confidence"],
                why=candidate["why"],
                score_breakdown=[ScoreBreakdownItem(**item) for item in candidate["score_breakdown"]],
                supporting_patterns=candidate["supporting_patterns"],
                top_evidence=[EvidenceItem(**item) for item in candidate["top_evidence"]],
                report_available=bool(candidate["report_available"]),
            )
        )

    # Build media metadata for the response
    media_context_used = bool(media_context and media_context.get("media_kind") != "none")
    media_summary: str | None = None
    transcript_excerpt: str | None = None
    caption_drafts: list[str] = []

    if media_context_used and media_context:
        scene = media_context.get("scene_summary")
        audio = media_context.get("transcript_or_audio_summary")
        media_summary = scene or audio
        if audio and audio != scene:
            transcript_excerpt = audio[:300] if audio else None
        caption_drafts = (media_context.get("caption_drafts") or [])[:3]

    media_assets = [MediaAsset(**a) for a in (saved_assets or [])]

    return ReviewResponse(
        request_id=str(uuid.uuid4()),
        idea_summary=idea_summary,
        rankings=rankings,
        methodology_note=METHODOLOGY_NOTE,
        media_context_used=media_context_used,
        media_assets=media_assets,
        media_summary=media_summary,
        transcript_excerpt=transcript_excerpt,
        caption_drafts=caption_drafts,
        media_context=media_context if media_context_used else None,
    )


async def handle_platform_report(request: PlatformReportRequest) -> PlatformReportResponse:
    idea_summary = _extract_idea_summary(request.idea_text, request.goal)

    media_context = request.media_context or {}
    duration_hint: str | None = None
    if media_context.get("media_kind") and media_context["media_kind"] != "none":
        idea_summary, duration_hint = _apply_media_overrides(idea_summary, media_context)

    content_platform_fit = kb.get_content_platform_fit(idea_summary.content_type, request.platform)
    context = kb.generate_platform_report_context(
        idea_text=request.idea_text,
        topic=idea_summary.topic,
        content_type=idea_summary.content_type,
        suggested_language=idea_summary.suggested_language,
        goal=request.goal,
        platform=request.platform,
        content_platform_fit=content_platform_fit,
        duration_hint=duration_hint,
    )
    analysis = _generate_platform_report_analysis(
        platform=request.platform,
        goal=request.goal,
        idea_text=request.idea_text,
        idea_summary=idea_summary,
        context=context,
        media_context=media_context or None,
    )

    media_summary: str | None = None
    if media_context.get("media_kind") and media_context["media_kind"] != "none":
        media_summary = media_context.get("scene_summary") or media_context.get("transcript_or_audio_summary")

    return PlatformReportResponse(
        request_id=str(uuid.uuid4()),
        platform=request.platform,
        fit_score=context["fit_score"],
        confidence=confidence(bool(context["top_evidence"]), max(
            context.get("semantic_match", 0.0),
            context.get("performance_strength", 0.0),
        )),
        why=context["why"],
        analysis=analysis,
        strengths=context["strengths"],
        risks=context["risks"],
        recommendations=context["recommendations"],
        evidence=[EvidenceItem(**item) for item in context["top_evidence"]],
        media_summary=media_summary,
    )
