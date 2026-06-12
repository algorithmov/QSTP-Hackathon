from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class RouteRequest(BaseModel):
    content_text: str
    media_url: Optional[str] = None
    goal: str
    topic_hint: Optional[str] = None


class VisualProfile(BaseModel):
    content_type: str
    format: str
    has_text_overlay: bool
    detected_text_language: str
    face_count: int
    motion_level: float
    energy_score: float
    aspect_ratio: str
    confidence: float


class ScoreComponents(BaseModel):
    platform_fit: float
    audience_fit: float
    geo_fit: float
    timing_fit: float
    language_fit: float
    predicted_engagement: float


class Route(BaseModel):
    rank: int
    platform: str
    audience: str
    country: str
    country_name: str
    language: str
    post_time_local: str
    timezone: str
    match_score: int
    components: ScoreComponents
    why: str
    tips: list[str] = []
    trend_direction: str
    trend_change_pct: Optional[int] = None
    dialect_rewrite: Optional[str] = None


class MapEntry(BaseModel):
    country: str
    country_name: str
    interest: int
    trend_direction: str
    best_platform: str


class TrendTicker(BaseModel):
    topic: str
    country: str
    change_pct: int
    direction: str


class RouteResponse(BaseModel):
    request_id: str
    content_summary: str
    visual_profile: Optional[VisualProfile] = None
    routes: list[Route]
    map_data: list[MapEntry]
    trend_ticker: list[TrendTicker]
    data_mode: str = "fallback"
