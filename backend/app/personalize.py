"""POST /api/personalize routing procedure."""
import json
import logging
import os
import uuid

import app.kb_client as kb
from app.scoring import confidence
from app.schemas import (
    EvidenceItem,
    IdeaSummary,
    PersonalizeRequest,
    PersonalizeResponse,
    PersonalizedReport,
)

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"


def _language_direction(dialect: str, suggested_language: str) -> str:
    if suggested_language == "en":
        return "ltr"
    return "rtl"


def _mock_report(
    country_info: dict,
    platform: str,
    idea_summary: IdeaSummary,
    usage: dict,
    ev_list: list[dict],
) -> PersonalizedReport:
    iso = country_info["iso_code"]
    name = country_info["name"]
    dialect = country_info["dominant_dialect"]
    tz = country_info["timezone"]
    peak = usage["peak_hours_local"]
    peak_hour = peak[0] if peak else 20
    lang_dir = _language_direction(dialect, idea_summary.suggested_language)
    conf = confidence(bool(ev_list), usage["usage_score"])

    short_topic = " ".join(idea_summary.topic.split()[:5]).rstrip(".,")
    topic_tag = idea_summary.topic.split()[:3]
    topic_tag_str = "_".join(w.capitalize() for w in topic_tag)
    if lang_dir == "rtl":
        caption = f"محتوى مميز عن {short_topic}"
        hashtags = [f"#{topic_tag_str}", "#StarsOfScience", "#نجوم_العلوم"]
    else:
        caption = f"Innovative content: {short_topic}"
        hashtags = [f"#{topic_tag_str}", "#StarsOfScience", "#Innovation"]

    return PersonalizedReport(
        country=iso,
        country_name=name,
        platform=platform,
        language=dialect,
        language_direction=lang_dir,
        recommended_format=f"Standard {platform} format optimized for {name}",
        hook=f"Open with the most compelling visual moment in the first 3 seconds.",
        caption=caption,
        hashtags=hashtags,
        post_time_local=f"{peak_hour:02d}:00",
        timezone=tz,
        dos=[
            f"Post at {peak_hour:02d}:00 {tz} for peak {name} engagement.",
            f"Use {dialect} captions to maximize resonance with local audience.",
        ],
        donts=[
            "Do not post during Friday prayer times.",
            "Avoid overly formal language that feels distant from the audience.",
        ],
        why=f"{platform} in {name} is a strong fit based on platform usage data and audience profile.",
        evidence=[EvidenceItem(**e) for e in ev_list],
        confidence=conf,
    )


def _llm_generate_reports(
    idea_summary: IdeaSummary,
    goal: str,
    pairs: list[dict],
    evidence_map: dict[str, list[dict]],
) -> list[dict] | None:
    if MOCK_MODE or not os.getenv("GROQ_API_KEY"):
        return None

    from app.llm_client import call_llm_json

    pairs_block = json.dumps(
        [
            {
                "country": p["country"],
                "country_name": p["country_name"],
                "platform": p["platform"],
                "dialect": p["dialect"],
                "language_direction": p["language_direction"],
                "peak_hour": p["peak_hour"],
                "timezone": p["timezone"],
                "usage_score": p["usage_score"],
                "evidence": evidence_map.get(p["country_name"], []),
            }
            for p in pairs
        ],
        ensure_ascii=False,
    )

    system = (
        "You are a social media strategy assistant for Stars of Science, an Arab innovation TV show. "
        "Write culturally aware, dialect-appropriate content delivery plans. "
        "Return only a JSON object, no markdown, no commentary."
    )
    user = (
        f"Content topic: {idea_summary.topic}\n"
        f"Content type: {idea_summary.content_type}\n"
        f"Primary audience: {idea_summary.primary_audience}\n"
        f"Suggested language: {idea_summary.suggested_language}\n"
        f"Goal: {goal}\n\n"
        f"Pairs: {pairs_block}\n\n"
        "For each country/platform pair, generate a delivery plan. "
        "Write caption in the country dialect if language_direction is rtl, "
        "bilingual (Arabic/English) if suggested_language is mixed, or English if en. "
        "Return JSON: "
        "{\"reports\": [{"
        "\"country\": \"ISO\", \"platform\": \"name\", "
        "\"recommended_format\": \"...\", \"hook\": \"...\", "
        "\"caption\": \"...\", \"hashtags\": [\"#tag\"], "
        "\"dos\": [\"...\"], \"donts\": [\"...\"], "
        "\"why\": \"...\", \"evidence_indices\": [0, 1], "
        "\"confidence_override\": null"
        "}]}"
    )

    try:
        return call_llm_json(system, user).get("reports")
    except Exception as exc:
        logger.warning("personalize LLM call failed: %s", exc)
        return None


async def handle_personalize(
    request: PersonalizeRequest,
    idea_summary: IdeaSummary,
) -> PersonalizeResponse:
    countries_data = kb.list_countries()
    country_map = {c["iso_code"]: c for c in countries_data}

    unique_countries = list(dict.fromkeys(request.countries))
    evidence_map: dict[str, list[dict]] = {}
    for iso in unique_countries:
        info = country_map.get(iso)
        if info:
            ev = kb.search_topic_evidence(idea_summary.topic, info["name"])
            evidence_map[info["name"]] = ev

    pairs: list[dict] = []
    for iso in request.countries:
        info = country_map.get(iso)
        if not info:
            continue
        for platform in request.platforms:
            usage = kb.get_usage(platform, iso)
            lang_dir = _language_direction(info["dominant_dialect"], idea_summary.suggested_language)
            peak = usage["peak_hours_local"]
            pairs.append({
                "country": iso,
                "country_name": info["name"],
                "platform": platform,
                "dialect": info["dominant_dialect"],
                "language_direction": lang_dir,
                "peak_hour": peak[0] if peak else 20,
                "timezone": info["timezone"],
                "usage_score": usage["usage_score"],
            })

    llm_reports = _llm_generate_reports(idea_summary, request.goal, pairs, evidence_map)

    reports: list[PersonalizedReport] = []
    for i, pair in enumerate(pairs):
        iso = pair["country"]
        info = country_map[iso]
        usage = kb.get_usage(pair["platform"], iso)
        ev_list = evidence_map.get(pair["country_name"], [])

        if llm_reports and i < len(llm_reports):
            lr = llm_reports[i]
            ev_indices = lr.get("evidence_indices", [])
            used_ev = [ev_list[j] for j in ev_indices if isinstance(j, int) and 0 <= j < len(ev_list)]
            evidence_used = bool(used_ev)
            conf = lr.get("confidence_override") or confidence(evidence_used, usage["usage_score"])
            reports.append(PersonalizedReport(
                country=iso,
                country_name=pair["country_name"],
                platform=pair["platform"],
                language=pair["dialect"],
                language_direction=pair["language_direction"],
                recommended_format=lr.get("recommended_format", "Standard format"),
                hook=lr.get("hook", "Open with the strongest visual moment."),
                caption=lr.get("caption", ""),
                hashtags=lr.get("hashtags", []),
                post_time_local=f"{pair['peak_hour']:02d}:00",
                timezone=pair["timezone"],
                dos=lr.get("dos", []),
                donts=lr.get("donts", []),
                why=lr.get("why", ""),
                evidence=[EvidenceItem(**e) for e in used_ev],
                confidence=conf,
            ))
        else:
            reports.append(_mock_report(info, pair["platform"], idea_summary, usage, ev_list))

    return PersonalizeResponse(
        request_id=str(uuid.uuid4()),
        idea_summary=idea_summary,
        reports=reports,
    )
