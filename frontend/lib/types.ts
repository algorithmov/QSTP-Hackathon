export interface RouteRequest {
  content_text: string;
  media_url?: string | null;
  goal: string;
  topic_hint?: string | null;
}

export interface VisualProfile {
  content_type: string;
  format: string;
  has_text_overlay: boolean;
  detected_text_language: string;
  face_count: number;
  motion_level: number;
  energy_score: number;
  aspect_ratio: string;
  confidence: number;
}

export interface ScoreComponents {
  platform_fit: number;
  audience_fit: number;
  geo_fit: number;
  timing_fit: number;
  language_fit: number;
  predicted_engagement: number;
}

export interface Route {
  rank: number;
  platform: string;
  audience: string;
  country: string;
  country_name: string;
  language: string;
  post_time_local: string;
  timezone: string;
  match_score: number;
  components: ScoreComponents;
  why: string;
  trend_direction: string;
  trend_change_pct?: number | null;
  dialect_rewrite?: string | null;
}

export interface MapEntry {
  country: string;
  country_name: string;
  interest: number;
  trend_direction: string;
  best_platform: string;
}

export interface TrendTickerItem {
  topic: string;
  country: string;
  change_pct: number;
  direction: string;
}

export interface RouteResponse {
  request_id: string;
  content_summary: string;
  visual_profile?: VisualProfile | null;
  routes: Route[];
  map_data: MapEntry[];
  trend_ticker: TrendTickerItem[];
}
