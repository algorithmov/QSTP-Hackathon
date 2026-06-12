from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

VALID_GOALS = frozenset({"applications", "viewers", "sponsors", "buzz"})
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


class ScoreComponents(BaseModel):
    topic_relevance: float
    audience_fit: float
    platform_fit: float
    language_fit: float
    timing_fit: float


class EvidenceItem(BaseModel):
    claim: str
    source: str
    url: Optional[str] = None


class Ranking(BaseModel):
    rank: int
    country: str
    country_name: str
    platform: str
    fit_score: int
    confidence: str
    components: ScoreComponents
    why: str
    evidence: list[EvidenceItem]
    recommended_time_local: str
    timezone: str


class MapDatum(BaseModel):
    country: str
    country_name: str
    best_fit_score: int
    best_platform: str


class ReviewResponse(BaseModel):
    request_id: str
    idea_summary: IdeaSummary
    rankings: list[Ranking]
    map_data: list[MapDatum]
    methodology_note: str


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
