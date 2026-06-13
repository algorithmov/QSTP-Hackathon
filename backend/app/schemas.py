from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

VALID_GOALS = frozenset({"applications", "viewers", "sponsors"})
VALID_COUNTRIES = frozenset({"EG", "SA", "AE", "QA", "DZ", "MA", "JO", "SD", "IQ", "KW"})
VALID_PLATFORMS = frozenset({"Instagram", "LinkedIn", "X", "YouTube", "TikTok"})
VALID_CONTENT_TYPES = frozenset({
    "product_demo", "talking_head", "educational",
    "announcement", "behind_the_scenes", "achievement_story",
})

ContentType = Literal[
    "product_demo", "talking_head", "educational",
    "announcement", "behind_the_scenes", "achievement_story",
]
SuggestedLanguage = Literal["ar", "en", "mixed"]
Confidence = Literal["high", "medium", "low"]
LanguageDirection = Literal["rtl", "ltr"]


class ReviewRequest(BaseModel):
    idea_text: str
    goal: str


class PersonalizeRequest(BaseModel):
    idea_text: str
    goal: str
    countries: list[str]
    platforms: list[str]


class IdeaSummary(BaseModel):
    topic: str
    content_type: str
    primary_audience: str
    suggested_language: str
    key_themes: list[str]


class EvidenceItem(BaseModel):
    claim: str
    source: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    platform: Optional[str] = None
    metrics: Optional[dict] = None
    matched_text: Optional[str] = None
    evidence_type: Optional[str] = None
    relevance_score: Optional[float] = None


class ScoreBreakdownItem(BaseModel):
    label: str
    score: float
    reason: str


class Ranking(BaseModel):
    rank: int
    platform: str
    fit_score: int
    confidence: str
    why: str
    score_breakdown: list[ScoreBreakdownItem]
    supporting_patterns: list[str]
    top_evidence: list[EvidenceItem]
    report_available: bool


# ── Media upload types ──────────────────────────────────────────────────────

class MediaAsset(BaseModel):
    media_id: str
    review_id: str
    original_filename: str
    mime_type: str
    file_size: int
    uploaded_at: str


class MediaContext(BaseModel):
    media_kind: str
    detected_language: Optional[str] = None
    transcript_or_audio_summary: Optional[str] = None
    scene_summary: Optional[str] = None
    subjects: list[str] = []
    visual_proof_moments: list[str] = []
    format_signals: list[str] = []
    tone: Optional[str] = None
    production_style: Optional[str] = None
    cta_presence: bool = False
    hook_strength: Optional[str] = None
    platform_cues: list[str] = []
    caption_drafts: list[str] = []
    confidence_notes: Optional[str] = None
    inferred_content_type: Optional[str] = None
    inferred_language: Optional[str] = None
    duration_signal: Optional[str] = None


# ── Review response ──────────────────────────────────────────────────────────

class ReviewResponse(BaseModel):
    request_id: str
    idea_summary: IdeaSummary
    rankings: list[Ranking]
    methodology_note: str
    media_context_used: bool = False
    media_assets: list[MediaAsset] = []
    media_summary: Optional[str] = None
    transcript_excerpt: Optional[str] = None
    caption_drafts: list[str] = []
    media_context: Optional[dict] = None


class PlatformReportRequest(BaseModel):
    idea_text: str
    goal: str
    platform: str
    media_context: Optional[dict] = None


class PlatformReportResponse(BaseModel):
    request_id: str
    platform: str
    fit_score: int
    confidence: str
    why: str
    analysis: str
    strengths: list[str]
    risks: list[str]
    recommendations: list[str]
    evidence: list[EvidenceItem]
    media_summary: Optional[str] = None


class PersonalizedReport(BaseModel):
    country: str
    country_name: str
    platform: str
    language: str
    language_direction: str
    recommended_format: str
    hook: str
    caption: str
    hashtags: list[str]
    post_time_local: str
    recommended_day_window: str
    timing_rationale: str
    timezone: str
    dos: list[str]
    donts: list[str]
    why: str
    evidence: list[EvidenceItem]
    confidence: str


class PersonalizeResponse(BaseModel):
    request_id: str
    idea_summary: IdeaSummary
    reports: list[PersonalizedReport]


class StarsSyncResponse(BaseModel):
    status: str
    sync: dict


class StarsStatusResponse(BaseModel):
    last_sync: Optional[dict] = None
    platform_stats: list[dict]
    total_posts: int
    import_stats: Optional[dict] = None


# ── Import types ─────────────────────────────────────────────────────────────

class ImportRunResult(BaseModel):
    run_id: str
    filename: str
    row_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    per_platform: dict


class ImportResponse(BaseModel):
    status: str
    runs: list[ImportRunResult]
    total_inserted: int
    total_updated: int
    total_skipped: int
