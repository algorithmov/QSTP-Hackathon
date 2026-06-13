export type Goal = "applications" | "viewers" | "sponsors";

export type Confidence = "high" | "medium" | "low";
export type LanguageDirection = "rtl" | "ltr";
export type SuggestedLanguage = "ar" | "en" | "mixed";

export type EvidenceItem = {
  claim: string;
  source: string;
  url: string | null;
  published_at?: string | null;
  platform?: Platform | null;
  metrics?: Record<string, number> | null;
  matched_text?: string | null;
  evidence_type?: string | null;
  relevance_score?: number | null;
};

export type IdeaSummary = {
  topic: string;
  content_type: string;
  primary_audience: string;
  suggested_language: SuggestedLanguage;
  key_themes: string[];
};

export type ScoreBreakdownItem = {
  label: string;
  score: number;
  reason: string;
};

export type MediaAsset = {
  media_id: string;
  review_id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  uploaded_at: string;
};

export type ReviewRequest = {
  idea_text: string;
  goal: Goal;
  files?: File[];
};

export type Ranking = {
  rank: number;
  platform: Platform;
  fit_score: number;
  confidence: Confidence;
  why: string;
  score_breakdown: ScoreBreakdownItem[];
  supporting_patterns: string[];
  top_evidence: EvidenceItem[];
  report_available: boolean;
};

export type ReviewResponse = {
  request_id: string;
  idea_summary: IdeaSummary;
  rankings: Ranking[];
  methodology_note: string;
  media_context_used: boolean;
  media_assets: MediaAsset[];
  media_summary: string | null;
  transcript_excerpt: string | null;
  caption_drafts: string[];
  media_context: Record<string, unknown> | null;
};

export type PlatformReportRequest = {
  idea_text: string;
  goal: Goal;
  platform: Platform;
  media_context?: Record<string, unknown> | null;
};

export type PlatformReportResponse = {
  request_id: string;
  platform: Platform;
  fit_score: number;
  confidence: Confidence;
  why: string;
  analysis: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
  evidence: EvidenceItem[];
  media_summary: string | null;
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
  recommended_day_window: string;
  timing_rationale: string;
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
