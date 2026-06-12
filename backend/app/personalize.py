"""POST /api/personalize routing procedure."""
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
    EvidenceItem,
    IdeaSummary,
    PersonalizeRequest,
    PersonalizeResponse,
    PersonalizedReport,
)

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_LLM_ENRICHMENT = os.getenv("USE_LLM_ENRICHMENT", "false").lower() == "true"

_ARABIC_COUNTRY_NAMES = {
    "Egypt": "مصر",
    "Saudi Arabia": "السعودية",
    "UAE": "الإمارات",
    "Qatar": "قطر",
    "Algeria": "الجزائر",
    "Morocco": "المغرب",
    "Jordan": "الأردن",
    "Sudan": "السودان",
    "Iraq": "العراق",
    "Kuwait": "الكويت",
}

_GOAL_CTA = {
    "applications": "and invite the next builder to apply",
    "viewers": "and keep viewers watching to the payoff",
    "sponsors": "and show why it deserves ecosystem backing",
}

_GOAL_CTA_AR = {
    "applications": "وشجع المبتكرين على التقديم",
    "viewers": "وخلي المشاهد يكمل للنهاية",
    "sponsors": "وأظهر ليه الفكرة تستحق الدعم",
}

_PLATFORM_FORMATS = {
    "TikTok": "25-35s vertical cut with an immediate proof moment and text overlays",
    "Instagram": "20-30s Reel plus a saveable caption that reinforces the takeaway",
    "YouTube": "35-60s Shorts-style demo with one clear explanation beat before the payoff",
    "LinkedIn": "30-45s subtitled explainer cut framed around the problem, solution, and impact",
    "X": "15-25s native clip paired with a concise thread-style caption and one strong takeaway",
}

_PLATFORM_HOOKS = {
    "TikTok": "Show the working result before the setup so the scroll stops on proof.",
    "Instagram": "Open on the cleanest visual reveal and immediately label the problem being solved.",
    "YouTube": "Start with the before-versus-after moment, then explain what makes the idea work.",
    "LinkedIn": "Lead with the real-world problem and the measurable value of the solution.",
    "X": "Open on the most surprising frame and anchor it to a one-line statement of relevance.",
}

_PLATFORM_HASHTAGS = {
    "TikTok": "#TikTokMENA",
    "Instagram": "#Reels",
    "YouTube": "#YouTubeShorts",
    "LinkedIn": "#InnovationLeadership",
    "X": "#TechTalk",
}


def _topic_keywords(topic: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "from", "into", "about", "idea", "content",
        "video", "clip", "post", "student", "students",
    }
    words = []
    for raw in topic.replace("/", " ").replace("-", " ").split():
        word = raw.strip(".,:;!?()[]{}").lower()
        if len(word) < 3 or word in stop or word in words:
            continue
        words.append(word)
    return words[:4]


def _topic_phrase(idea_summary: IdeaSummary) -> str:
    words = _topic_keywords(idea_summary.topic)
    if words:
        return " ".join(words[:3])
    return idea_summary.content_type.replace("_", " ")


def _build_recommended_format(platform: str, goal: str, idea_summary: IdeaSummary) -> str:
    base = _PLATFORM_FORMATS.get(platform, f"Platform-native {platform} format")
    if idea_summary.content_type == "product_demo":
        return f"{base}; keep the working prototype visible throughout."
    if idea_summary.content_type == "educational":
        return f"{base}; structure it as a fast lesson with one practical takeaway."
    if goal == "sponsors":
        return f"{base}; add one concrete impact frame for credibility."
    return base + "."


def _build_hook(platform: str, goal: str, idea_summary: IdeaSummary) -> str:
    hook = _PLATFORM_HOOKS.get(platform, "Lead with the sharpest visual proof.")
    if idea_summary.content_type == "achievement_story":
        return f"{hook} Then connect the achievement to what becomes possible next."
    if idea_summary.content_type == "announcement":
        return f"{hook} Make the reveal happen in the first two seconds."
    if goal == "sponsors":
        return f"{hook} Name the problem solved so the impact is clear to decision-makers."
    return hook


def _build_caption(country_name: str, goal: str, idea_summary: IdeaSummary) -> str:
    topic = _topic_phrase(idea_summary)
    arabic_country = _ARABIC_COUNTRY_NAMES.get(country_name, country_name)
    english = f"{country_name}: {topic} turned into a real solution { _GOAL_CTA.get(goal, '') }".strip()
    english = english.replace("  ", " ")
    arabic = f"من {arabic_country}: {topic} يتحول إلى حل عملي { _GOAL_CTA_AR.get(goal, '') }".strip()
    arabic = arabic.replace("  ", " ")

    if idea_summary.suggested_language == "en":
        return english[:150]
    if idea_summary.suggested_language == "ar":
        return arabic[:150]
    return f"{arabic} | {english}"[:150]


def _build_hashtags(country_name: str, platform: str, goal: str, idea_summary: IdeaSummary) -> list[str]:
    words = _topic_keywords(idea_summary.topic)
    english_topic = "#" + "".join(word.capitalize() for word in words[:2]) if words else "#Innovation"
    arabic_goal = {
        "applications": "#فرصة_للمبتكرين",
        "viewers": "#ابتكار_ملهم",
        "sponsors": "#دعم_الابتكار",
    }.get(goal, "#نجوم_العلوم")
    country_tag = "#" + country_name.replace(" ", "")
    tags = [english_topic, "#StarsOfScience", arabic_goal, country_tag, _PLATFORM_HASHTAGS.get(platform, "#MENA")]
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:5]


def _build_dos(platform: str, country_name: str, peak_hour: int, goal: str, idea_summary: IdeaSummary) -> list[str]:
    topic = _topic_phrase(idea_summary)
    return [
        f"Post at {peak_hour:02d}:00 local time when {platform} usage peaks in {country_name}.",
        f"Keep the opening tied to {topic} and the {goal} goal instead of using a generic intro.",
    ]


def _build_donts(platform: str, goal: str) -> list[str]:
    platform_warning = {
        "TikTok": "Do not spend the first seconds on logos before the working proof appears.",
        "Instagram": "Do not bury the payoff after a slow aesthetic setup.",
        "YouTube": "Do not open with a long preamble before showing what the idea does.",
        "LinkedIn": "Do not make the cut feel too casual if the goal is sponsor credibility.",
        "X": "Do not rely on context-free visuals that need a long explanation to make sense.",
    }.get(platform, "Do not hide the main point behind a long setup.")
    goal_warning = {
        "applications": "Avoid vague calls to action; clearly signal who should apply or respond.",
        "viewers": "Avoid jargon-heavy framing that reduces watch-through for a broad audience.",
        "sponsors": "Avoid overclaiming impact without showing the practical use case.",
    }.get(goal, "Avoid generic wording.")
    return [platform_warning, goal_warning]


def _build_why(platform: str, country_name: str, goal: str, usage_score: float, idea_summary: IdeaSummary) -> str:
    topic = _topic_phrase(idea_summary)
    intensity = "strong" if usage_score >= 0.8 else "solid"
    return (
        f"{platform} is a {intensity} fit in {country_name} for {topic} because the format matches "
        f"how Masar needs to reach {goal} audiences."
    )


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
    caption = _build_caption(name, "applications", idea_summary)
    hashtags = _build_hashtags(name, platform, "applications", idea_summary)

    return PersonalizedReport(
        country=iso,
        country_name=name,
        platform=platform,
        language=dialect,
        language_direction=lang_dir,
        recommended_format=_build_recommended_format(platform, "applications", idea_summary),
        hook=_build_hook(platform, "applications", idea_summary),
        caption=caption,
        hashtags=hashtags,
        post_time_local=f"{peak_hour:02d}:00",
        timezone=tz,
        dos=_build_dos(platform, name, peak_hour, "applications", idea_summary),
        donts=_build_donts(platform, "applications"),
        why=_build_why(platform, name, "applications", usage["usage_score"], idea_summary),
        evidence=[EvidenceItem(**e) for e in ev_list],
        confidence=conf,
    )


def _llm_generate_reports(
    idea_summary: IdeaSummary,
    goal: str,
    pairs: list[dict],
    evidence_map: dict[str, list[dict]],
) -> list[dict] | None:
    from app.llm_client import llm_available

    if MOCK_MODE or not USE_LLM_ENRICHMENT or not llm_available():
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
        "For each country/platform pair, generate a culturally appropriate delivery plan. "
        "- recommended_format: 1 sentence describing format, length, and orientation.\n"
        "- hook: 1 sentence on what to show in the first 2-3 seconds.\n"
        "- caption: write in the country's dialect (Arabic script if language_direction is rtl). "
        "If suggested_language is 'mixed', write bilingual. If 'en', write English. Keep it under 150 chars.\n"
        "- hashtags: 3 to 5 relevant hashtags, in Arabic script if rtl.\n"
        "- dos: 2 concrete actionable instructions for this platform and country.\n"
        "- donts: 2 concrete warnings specific to this platform and country.\n"
        "- why: 1 sentence (12-20 words) explaining why this platform fits this content in that country.\n"
        "- evidence_indices: list of integer indices into this pair's evidence list that support the why.\n"
        "- confidence_override: null (let the system compute it).\n"
        "Return only a JSON object with key 'reports' containing an array, no markdown.\n"
        "Example format: {\"reports\": [{\"country\": \"EG\", \"platform\": \"TikTok\", "
        "\"recommended_format\": \"Vertical short 30-45s\", \"hook\": \"Open on the filter working.\", "
        "\"caption\": \"مهندسة شابة تبتكر حلاً للمياه النظيفة\", \"hashtags\": [\"#ابتكار\", \"#StarsOfScience\"], "
        "\"dos\": [\"Lead with visual proof\"], \"donts\": [\"Avoid long intros\"], "
        "\"why\": \"TikTok in Egypt has the highest youth engagement for quick visual demos.\", "
        "\"evidence_indices\": [], \"confidence_override\": null}]}"
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
    platform_map = {platform["name"]: platform for platform in kb.list_platforms()}

    unique_countries = list(dict.fromkeys(request.countries))
    evidence_map: dict[str, list[dict]] = {}
    for iso in unique_countries:
        info = country_map.get(iso)
        if info:
            ev = kb.search_topic_evidence(
                idea_summary.topic,
                info["name"],
                max_results=evidence_target_count(iso),
            )
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
            if not used_ev and ev_list:
                used_ev = ev_list[: max(1, evidence_target_count(iso) - 2)]
            combined_evidence = merge_evidence(
                used_ev,
                ev_list,
                build_usage_evidence(pair["country_name"], pair["platform"], usage),
                build_platform_note_evidence(platform_map.get(pair["platform"], {})),
                limit=evidence_target_count(iso),
            )
            evidence_used = bool(combined_evidence)
            conf = lr.get("confidence_override") or confidence(evidence_used, usage["usage_score"])
            reports.append(PersonalizedReport(
                country=iso,
                country_name=pair["country_name"],
                platform=pair["platform"],
                language=pair["dialect"],
                language_direction=pair["language_direction"],
                recommended_format=lr.get("recommended_format") or _build_recommended_format(pair["platform"], request.goal, idea_summary),
                hook=lr.get("hook") or _build_hook(pair["platform"], request.goal, idea_summary),
                caption=lr.get("caption") or _build_caption(pair["country_name"], request.goal, idea_summary),
                hashtags=lr.get("hashtags") or _build_hashtags(pair["country_name"], pair["platform"], request.goal, idea_summary),
                post_time_local=f"{pair['peak_hour']:02d}:00",
                timezone=pair["timezone"],
                dos=lr.get("dos") or _build_dos(pair["platform"], pair["country_name"], pair["peak_hour"], request.goal, idea_summary),
                donts=lr.get("donts") or _build_donts(pair["platform"], request.goal),
                why=lr.get("why") or _build_why(pair["platform"], pair["country_name"], request.goal, usage["usage_score"], idea_summary),
                evidence=[EvidenceItem(**e) for e in combined_evidence],
                confidence=conf,
            ))
        else:
            combined_evidence = merge_evidence(
                ev_list,
                build_usage_evidence(pair["country_name"], pair["platform"], usage),
                build_platform_note_evidence(platform_map.get(pair["platform"], {})),
                limit=evidence_target_count(iso),
            )
            reports.append(PersonalizedReport(
                country=iso,
                country_name=pair["country_name"],
                platform=pair["platform"],
                language=pair["dialect"],
                language_direction=pair["language_direction"],
                recommended_format=_build_recommended_format(pair["platform"], request.goal, idea_summary),
                hook=_build_hook(pair["platform"], request.goal, idea_summary),
                caption=_build_caption(pair["country_name"], request.goal, idea_summary),
                hashtags=_build_hashtags(pair["country_name"], pair["platform"], request.goal, idea_summary),
                post_time_local=f"{pair['peak_hour']:02d}:00",
                timezone=pair["timezone"],
                dos=_build_dos(pair["platform"], pair["country_name"], pair["peak_hour"], request.goal, idea_summary),
                donts=_build_donts(pair["platform"], request.goal),
                why=_build_why(pair["platform"], pair["country_name"], request.goal, usage["usage_score"], idea_summary),
                evidence=[EvidenceItem(**e) for e in combined_evidence],
                confidence=confidence(bool(combined_evidence), usage["usage_score"]),
            ))

    return PersonalizeResponse(
        request_id=str(uuid.uuid4()),
        idea_summary=idea_summary,
        reports=reports,
    )
