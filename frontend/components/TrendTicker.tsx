"use client";

import type { TrendDatum } from "@/types/route";

type TrendTickerProps = {
  trends: TrendDatum[];
};

export function TrendTicker({ trends }: TrendTickerProps) {
  if (trends.length === 0) return null;

  const loop = [...trends, ...trends];

  return (
    <section className="overflow-hidden rounded-md border border-line bg-ink py-3 text-white shadow-board" aria-label="Trend ticker">
      <div className="ticker-track flex w-max gap-3">
        {loop.map((trend, index) => (
          <div key={`${trend.topic}-${trend.country}-${index}`} className="flex items-center gap-2 whitespace-nowrap px-4 text-sm">
            <span className="font-bold">{trend.topic}</span>
            <span className="text-white/55">{trend.country}</span>
            <span className="rounded-md bg-white/10 px-2 py-1 text-xs font-bold">
              {trend.direction} {trend.change_pct}%
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
