"use client";

import type { TrendDatum } from "@/types/route";

type TrendTickerProps = {
  trends: TrendDatum[];
  dataMode: "live" | "cache" | "fallback";
};

const modeLabel: Record<string, string> = {
  live: "Data: live",
  cache: "Data: cached",
  fallback: "Data: fallback",
};

const modeClass: Record<string, string> = {
  live: "bg-accent/15 text-accent",
  cache: "bg-amber-100 text-amber-700",
  fallback: "bg-slate-100 text-muted",
};

export function TrendTicker({ trends, dataMode }: TrendTickerProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-md border border-line bg-white px-4 py-2.5 shadow-board"
      aria-label="Trend ticker"
    >
      <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${modeClass[dataMode] ?? modeClass.fallback}`}>
        {modeLabel[dataMode] ?? "Data: fallback"}
      </span>

      {trends.length > 0 ? (
        <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto scrollbar-none">
          {trends.map((t) => (
            <span
              key={`${t.topic}-${t.country}`}
              className="flex shrink-0 items-center gap-1.5 rounded-md bg-paper px-3 py-1 text-xs"
            >
              <span className="font-semibold text-ink">{t.topic}</span>
              <span className="text-muted">{t.country}</span>
              <span className={`font-bold ${t.direction === "rising" ? "text-accent" : "text-muted"}`}>
                {t.direction === "rising" ? "+" : ""}{t.change_pct}%
              </span>
            </span>
          ))}
        </div>
      ) : (
        <span className="text-xs text-muted">
          {dataMode === "live" ? "No rising trends for this topic right now." : "Google Trends rate-limited — using static fallback scores."}
        </span>
      )}
    </div>
  );
}
