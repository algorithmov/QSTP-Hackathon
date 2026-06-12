export type Goal = "applications" | "viewers" | "sponsors" | "buzz";

export type RouteRequest = {
  content_text: string;
  media_url: string | null;
  goal: Goal;
  topic_hint: string | null;
};

export type VisualProfile = {
  content_type: string;
  format: string;
  has_text_overlay: boolean;
  detected_text_language: string | null;
  face_count: number;
  motion_level: number;
  energy_score: number;
  aspect_ratio: string;
  confidence: number;
};

export type RouteOption = {
  rank: number;
  platform: string;
  audience: string;
  country: string;
  country_name: string;
  language: string;
  post_time_local: string;
  timezone: string;
  match_score: number;
  components: {
    platform_fit: number;
    audience_fit: number;
    geo_fit: number;
    timing_fit: number;
    language_fit: number;
    predicted_engagement: number;
  };
  why: string;
  trend_direction: "rising" | "flat" | "falling";
  trend_change_pct: number | null;
  dialect_rewrite: string | null;
};

export type MapDatum = {
  country: string;
  country_name: string;
  interest: number;
  trend_direction: "rising" | "flat" | "falling";
  best_platform: string;
};

export type TrendDatum = {
  topic: string;
  country: string;
  change_pct: number;
  direction: "rising" | "flat" | "falling";
};

export type RouteResponse = {
  request_id: string;
  content_summary: string;
  visual_profile: VisualProfile | null;
  routes: RouteOption[];
  map_data: MapDatum[];
  trend_ticker: TrendDatum[];
};
