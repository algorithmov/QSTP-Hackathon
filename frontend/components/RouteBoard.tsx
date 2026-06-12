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
    format: "9:16 vertical, 15–60 seconds",
    framing:
      "Open with a visual hook in the first 2 seconds — no intro, no logo. Add captions to every word (85 % is watched muted). Close with one clear call to action on screen.",
    tips: [
      "Jump-cut edits every 2–3 s and trending audio multiply organic reach significantly.",
      "Reply to every comment within the first 30 min — TikTok's algorithm rewards early engagement velocity.",
      "Duet or Stitch a relevant post to tap into existing traffic rather than starting from zero.",
    ],
  },
  Instagram: {
    format: "Reels 9:16 under 90 s, or carousel 1:1 with 3–10 slides",
    framing:
      "Lead with the most striking visual frame — the cover image determines click-through. Keep on-screen text to 3–5 words per frame. Follow with a Story within 2 hours.",
    tips: [
      "Carousels earn roughly 2× more reach than single-image posts on average.",
      "Tag 3–5 relevant accounts in the post to appear in their tagged section.",
      "Post a supporting Story with a sticker poll within 2 h to boost Reel visibility.",
    ],
  },
  YouTube: {
    format: "16:9 landscape, 3–10 min; Shorts: vertical under 60 s",
    framing:
      "Thumbnail and title decide 90 % of clicks — design both before filming. The first 30 s must clearly state the value or viewers drop off. Use chapters for anything over 5 min.",
    tips: [
      "End-screen cards in the last 20 s double the subscribe conversion rate.",
      "Subtitles and auto-translated captions extend reach to non-native speakers across the region.",
      "A/B test two thumbnails in YouTube Studio in the first 48 h after publishing.",
    ],
  },
  LinkedIn: {
    format: "1:1 or 16:9 video, 1–3 min; text posts also get strong organic reach",
    framing:
      "Open with the business impact or outcome — not the backstory. Cite a specific number in the first sentence. Conversational but professional tone outperforms formal corporate language.",
    tips: [
      "Tag the relevant university, organisation, or funder to appear in their followers' feeds.",
      "PDF document carousels outperform images on LinkedIn feeds — convert your slides.",
      "End with a direct question to drive comments, which LinkedIn's algorithm rewards heavily.",
    ],
  },
  Facebook: {
    format: "Any format; native square video (1:1) and link posts both work",
    framing:
      "Longer captions outperform short ones on Facebook, unlike other platforms. Tell the full story in the post text. Video auto-plays — make the first frame self-explanatory without sound.",
    tips: [
      "Post in relevant regional Facebook Groups for additional non-follower reach.",
      "Facebook Live generates roughly 6× more interactions than pre-recorded video.",
      "Tag a specific city or venue to surface the post in local discovery feeds.",
    ],
  },
  Twitter: {
    format: "16:9 or 1:1 video under 2 min 20 s; threads for detailed content",
    framing:
      "Lead with the most surprising or specific claim you can make. Threads work better than long captions for complex stories. Engage existing trending hashtags rather than creating new ones.",
    tips: [
      "Threads get more impressions than single tweets when the topic needs depth.",
      "Post between 8–10 AM local time for maximum initial velocity.",
      "Quote-tweet a related account to attach your content to an existing conversation.",
    ],
  },
};

const defaultGuide: GuideSection = {
  format: "Match the platform's preferred aspect ratio and length",
  framing: "Lead with the strongest hook, state the value clearly, close with one call to action.",
  tips: [
    "Post at the time shown on the card for peak audience activity.",
    "Use the language shown to maximise resonance with the local audience.",
    "Engage comments in the first hour to signal quality to the platform algorithm.",
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
              {guide.tips.map((tip, i) => (
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
