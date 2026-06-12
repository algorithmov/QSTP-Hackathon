export type Goal = "applications" | "viewers" | "sponsors";

export type Confidence = "high" | "medium" | "low";
export type LanguageDirection = "rtl" | "ltr";
export type SuggestedLanguage = "ar" | "en" | "mixed";

export type EvidenceItem = {
  claim: string;
  source: string;
  url: string | null;
};

export type IdeaSummary = {
  topic: string;
  content_type: string;
  primary_audience: string;
  suggested_language: SuggestedLanguage;
  key_themes: string[];
};

export type ScoreComponents = {
  topic_relevance: number;
  audience_fit: number;
  platform_fit: number;
  language_fit: number;
  timing_fit: number;
};

export type ReviewRequest = {
  idea_text: string;
  goal: Goal;
};

export type Ranking = {
  rank: number;
  country: string;
  country_name: string;
  platform: Platform;
  fit_score: number;
  confidence: Confidence;
  components: ScoreComponents;
  why: string;
  evidence: EvidenceItem[];
  recommended_time_local: string;
  timezone: string;
};

export type MapDatum = {
  country: string;
  country_name: string;
  best_fit_score: number;
  best_platform: Platform;
};

export type ReviewScope = {
  mode: "country_focus" | "regional";
  country: CountryCode | null;
  country_name: string | null;
  reason: string;
};

export type ReviewResponse = {
  request_id: string;
  idea_summary: IdeaSummary;
  review_scope?: ReviewScope | null;
  rankings: Ranking[];
  map_data: MapDatum[];
  methodology_note: string;
};

export type CountryCode = "EG" | "SA" | "AE" | "QA" | "DZ" | "MA" | "JO" | "SD" | "IQ" | "KW";
export type Platform = "Instagram" | "LinkedIn" | "X" | "YouTube" | "TikTok";

export type PersonalizeRequest = {
  idea_text: string;
  goal: Goal;
  countries: CountryCode[];
  platforms: Platform[];
};

export type PersonalizedReport = {
  country: CountryCode;
  country_name: string;
  platform: Platform;
  language: string;
  language_direction: LanguageDirection;
  recommended_format: string;
  hook: string;
  caption: string;
  hashtags: string[];
  post_time_local: string;
  timezone: string;
  dos: string[];
  donts: string[];
  why: string;
  evidence: EvidenceItem[];
  confidence: Confidence;
};

export type PersonalizeResponse = {
  request_id: string;
  idea_summary: IdeaSummary;
  reports: PersonalizedReport[];
};

export const goals: Array<{ label: string; value: Goal }> = [
  { label: "Applications", value: "applications" },
  { label: "Viewers", value: "viewers" },
  { label: "Sponsors", value: "sponsors" }
];

export const supportedCountries: Array<{ code: CountryCode; name: string }> = [
  { code: "EG", name: "Egypt" },
  { code: "SA", name: "Saudi Arabia" },
  { code: "AE", name: "UAE" },
  { code: "QA", name: "Qatar" },
  { code: "DZ", name: "Algeria" },
  { code: "MA", name: "Morocco" },
  { code: "JO", name: "Jordan" },
  { code: "SD", name: "Sudan" },
  { code: "IQ", name: "Iraq" },
  { code: "KW", name: "Kuwait" }
];

export const supportedPlatforms: Platform[] = ["Instagram", "LinkedIn", "X", "YouTube", "TikTok"];

// Legacy exports kept temporarily so old unused components still type-check
// while the rebuild swaps the app to the v2 contracts.
export type RouteRequest = {
  content_text: string;
  media_url: string | null;
  goal: Goal;
  topic_hint: string | null;
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
  components: Record<string, number>;
  why: string;
  tips: string[];
  trend_direction: "rising" | "flat" | "falling";
  trend_change_pct: number | null;
  dialect_rewrite: string | null;
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
  map_data: Array<{
    country: string;
    country_name: string;
    interest: number;
    trend_direction: "rising" | "flat" | "falling";
    best_platform: string;
  }>;
  trend_ticker: TrendDatum[];
  data_mode: "live" | "cache" | "fallback";
};
