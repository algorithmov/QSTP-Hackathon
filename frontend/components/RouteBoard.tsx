"use client";

import { ChevronDown, Clock, MapPin } from "lucide-react";
import { useState } from "react";
import type { RouteOption } from "@/types/route";

type RouteBoardProps = {
  routes: RouteOption[];
};

export function RouteBoard({ routes }: RouteBoardProps) {
  if (routes.length === 0) {
    return (
      <section className="rounded-md border border-line bg-white p-6 text-muted shadow-board">
        Route recommendations will appear here after you submit content.
      </section>
    );
  }

  return (
    <section className="space-y-3" aria-label="Route board">
      {routes.map((route) => (
        <RouteCard key={`${route.rank}-${route.platform}-${route.country}`} route={route} />
      ))}
    </section>
  );
}

type GuideSection = {
  format: string;
  framing: string;
  tips: string[];
};

const platformGuide: Record<string, GuideSection> = {
  TikTok: {
    format: "9:16 vertical, 15–60 seconds (source: TikTok Creator Center 2024)",
    framing:
      "Open with a visual hook in the first 2 seconds — TikTok data shows most drop-offs happen in the first 3 s. Add captions: DataReportal 2024 reports the majority of MENA mobile video is viewed without sound. Close with one clear call to action.",
    tips: [
      "TikTok Creator Center data: watch-completion rate is the primary ranking signal — keep content tight.",
      "Early comment replies matter: TikTok surfaces posts with rapid early engagement in For You feeds (TikTok Business, 2024).",
      "Duet or Stitch an existing post — it inherits the original audience rather than starting from zero.",
    ],
  },
  Instagram: {
    format: "Reels 9:16 under 90 s, or carousel 1:1 with 3–10 slides (source: Meta Creator Center 2024)",
    framing:
      "Lead with the most striking visual frame — cover image drives click-through rate. Meta reports Reels reach significantly more non-followers than feed posts in the MENA region (Meta Insights, 2024).",
    tips: [
      "Meta data shows carousels generate higher saves and shares than single images — use them for multi-step stories.",
      "Tag 3–5 relevant accounts to surface the post in their tagged sections.",
      "Post a supporting Story with a poll within 2 h to feed Instagram's cross-format ranking signal.",
    ],
  },
  YouTube: {
    format: "16:9 landscape, 3–10 min; Shorts: vertical under 60 s (source: Google MENA Insights 2024)",
    framing:
      "Thumbnail and title are the primary click drivers — YouTube's own data puts them as the top factor in watch decisions. State the video value in the first 30 s to reduce drop-off.",
    tips: [
      "YouTube data: end-screen cards in the final 20 s meaningfully increase subscribe conversion.",
      "Auto-translated captions expand reach across Arabic dialects — YouTube Studio enables them in one click.",
      "Use YouTube Studio's A/B thumbnail test (launched 2023) — the tool reports which variant earns more impressions.",
    ],
  },
  LinkedIn: {
    format: "1:1 or 16:9 video, 1–3 min; text posts also reach well (source: LinkedIn Marketing Solutions 2024)",
    framing:
      "Open with the outcome or impact, not the backstory. LinkedIn's algorithm prioritises dwell time — give the reader a reason to pause immediately.",
    tips: [
      "Tag relevant institutions or funders — they often reshare, extending reach to their follower base.",
      "LinkedIn data shows document (PDF carousel) posts drive higher engagement rates than image posts.",
      "End with a direct question — LinkedIn's feed ranks posts with active comment threads higher.",
    ],
  },
  Facebook: {
    format: "Any format; native square video (1:1) and link posts both work (source: Meta Business, 2024)",
    framing:
      "Facebook supports longer captions than other platforms — tell the full story. Auto-playing video means the first frame must be self-explanatory without audio.",
    tips: [
      "Post in relevant regional Groups — Group content receives priority in members' feeds (Meta, 2024).",
      "Facebook Live consistently outperforms pre-recorded video on engagement metrics per Meta's own benchmarks.",
      "Location tagging surfaces the post in local discovery and Maps feeds.",
    ],
  },
  Twitter: {
    format: "16:9 or 1:1 video under 2 min 20 s; threads for detail (source: X Business, Sprout Social Index 2024)",
    framing:
      "Lead with a specific or surprising claim. Sprout Social data shows tweets with a question or bold statement earn higher initial engagement than neutral openers.",
    tips: [
      "Sprout Social Index 2024: threads earn more impressions than single tweets for complex topics.",
      "Optimal posting time for MENA: 8–10 AM local time per Hootsuite MENA benchmarks.",
      "Quote-tweeting a related account attaches your content to an existing conversation and its traffic.",
    ],
  },
};

const defaultGuide: GuideSection = {
  format: "Match the platform's preferred aspect ratio and duration",
  framing: "Lead with the strongest hook in the first 2–3 seconds, state the value clearly, and close with one call to action.",
  tips: [
    "Post at the time shown on the card — platform-country peak hours are sourced from DataReportal Digital 2024.",
    "Use the language shown on the card to maximise resonance with the local audience.",
    "Respond to early comments promptly — all major platforms use early-engagement velocity as a ranking signal.",
  ],
};

const audienceTip: Record<string, string> = {
  applicants:
    "Include the application deadline and a direct link to the submission page. Urgency drives conversion.",
  sponsors:
    "Lead with audience reach and social proof. Name the programme's key existing partners or backers.",
  viewers:
    "Prioritise entertainment and emotional hook over information density. Shareability is the primary metric.",
  buzz:
    "Create a strong opinion, surprising reveal, or contrast to drive shares. High-emotion content outperforms neutral content on reach.",
};

function RouteCard({ route }: { route: RouteOption }) {
  const [expanded, setExpanded] = useState(false);
  const [dialectOpen, setDialectOpen] = useState(false);
  const lowMatch = route.match_score < 50;
  const direction = route.trend_direction;
  const guide = platformGuide[route.platform] ?? defaultGuide;
  const audTip = audienceTip[route.audience] ?? null;
  const llmTips = route.tips && route.tips.length > 0 ? route.tips : null;

  return (
    <article
      className={`rounded-md border bg-white p-5 shadow-board ${
        lowMatch ? "border-low/40 opacity-70" : "border-line"
      }`}
    >
      <div className="grid gap-4 md:grid-cols-[1fr_148px] md:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-ink px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">
              Rank {route.rank}
            </span>
            <h3 className="text-xl font-bold leading-tight text-ink">
              {route.platform} in {route.country_name}
            </h3>
            {lowMatch ? (
              <span className="rounded-md bg-low px-2.5 py-1 text-xs font-bold text-white">
                wrong room
              </span>
            ) : null}
          </div>

          <div className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-2 lg:grid-cols-4">
            <span>{route.audience}</span>
            <span>{route.language}</span>
            <span className="flex items-center gap-1.5">
              <Clock size={15} aria-hidden="true" />
              {route.post_time_local}
            </span>
            <span className="flex items-center gap-1.5">
              <MapPin size={15} aria-hidden="true" />
              {route.timezone}
            </span>
          </div>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-ink">{route.why}</p>

          <p className="mt-2 text-xs text-muted">
            <span className="font-semibold">Format:</span> {guide.format}
          </p>
        </div>

        <div className="rounded-md border border-line bg-paper p-4 text-center">
          <div
            className={`text-5xl font-black leading-none ${
              lowMatch ? "text-low" : "text-accent"
            }`}
          >
            {route.match_score}
          </div>
          <div className="mt-1 text-xs font-semibold uppercase text-muted">match score</div>
          <div
            className={`mt-3 rounded-md px-2 py-1 text-xs font-bold ${directionClass(direction)}`}
          >
            {direction}
            {route.trend_change_pct !== null ? ` ${route.trend_change_pct}%` : ""}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {Object.entries(route.components).map(([key, value]) => (
          <div key={key} className="rounded-md border border-line bg-white px-3 py-2">
            <div className="text-xs font-semibold capitalize text-muted">
              {key.replaceAll("_", " ")}
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-slate-100">
              <div
                className="h-1.5 rounded-full bg-accent"
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:border-accent/60"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          Implementation guide
          <ChevronDown
            size={16}
            className={expanded ? "rotate-180 transition" : "transition"}
            aria-hidden="true"
          />
        </button>

        {route.dialect_rewrite ? (
          <button
            type="button"
            className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:border-accent/60"
            onClick={() => setDialectOpen((v) => !v)}
            aria-expanded={dialectOpen}
          >
            Dialect rewrite
            <ChevronDown
              size={16}
              className={dialectOpen ? "rotate-180 transition" : "transition"}
              aria-hidden="true"
            />
          </button>
        ) : null}
      </div>

      {expanded && (
        <div className="mt-3 rounded-md border border-line bg-paper p-4 text-sm space-y-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted mb-1">
              How to frame the content
            </div>
            <p className="leading-6 text-ink">{guide.framing}</p>
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
              Implementation steps
            </div>
            <ol className="space-y-2">
              {(llmTips ?? guide.tips).map((tip, i) => (
                <li key={i} className="flex gap-2 leading-6 text-ink">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/10 text-xs font-bold text-accent">
                    {i + 1}
                  </span>
                  {tip}
                </li>
              ))}
            </ol>
          </div>

          {audTip && (
            <div className="rounded-md border border-accent/20 bg-accent/5 px-3 py-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-accent mb-1">
                {route.audience} audience note
              </div>
              <p className="leading-6 text-ink">{audTip}</p>
            </div>
          )}
        </div>
      )}

      {dialectOpen && route.dialect_rewrite ? (
        <div
          className="mt-3 rounded-md border border-line bg-paper p-4 text-right text-lg leading-9 text-ink"
          dir="rtl"
        >
          {route.dialect_rewrite}
        </div>
      ) : null}
    </article>
  );
}

function directionClass(direction: RouteOption["trend_direction"]) {
  if (direction === "rising") return "bg-accent/10 text-accent";
  if (direction === "falling") return "bg-low/15 text-low";
  return "bg-slate-100 text-muted";
}
