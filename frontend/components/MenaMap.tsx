"use client";

import { useMemo, useState } from "react";
import type { MapDatum, RouteOption } from "@/types/route";

const countryTiles: Array<{ code: string; x: number; y: number; label: string }> = [
  { code: "MA", x: 4, y: 48, label: "MA" },
  { code: "DZ", x: 18, y: 44, label: "DZ" },
  { code: "TN", x: 30, y: 38, label: "TN" },
  { code: "LY", x: 37, y: 49, label: "LY" },
  { code: "EG", x: 51, y: 49, label: "EG" },
  { code: "SD", x: 55, y: 67, label: "SD" },
  { code: "JO", x: 60, y: 39, label: "JO" },
  { code: "SA", x: 69, y: 55, label: "SA" },
  { code: "IQ", x: 69, y: 38, label: "IQ" },
  { code: "KW", x: 76, y: 45, label: "KW" },
  { code: "QA", x: 82, y: 54, label: "QA" },
  { code: "AE", x: 88, y: 57, label: "AE" }
];

type MenaMapProps = {
  data: MapDatum[];
  routes: RouteOption[];
};

export function MenaMap({ data, routes }: MenaMapProps) {
  const [selected, setSelected] = useState<MapDatum | null>(null);

  const byCountry = useMemo(
    () => new Map(data.map((datum) => [datum.country, datum])),
    [data]
  );

  const routesByCountry = useMemo(() => {
    const map = new Map<string, RouteOption[]>();
    for (const route of routes) {
      const existing = map.get(route.country) ?? [];
      map.set(route.country, [...existing, route]);
    }
    return map;
  }, [routes]);

  function handleTileClick(code: string) {
    const datum = byCountry.get(code) ?? null;
    setSelected((prev) => (prev?.country === code ? null : datum));
  }

  const selectedRoutes = selected ? (routesByCountry.get(selected.country) ?? []) : [];

  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board" aria-label="MENA interest map">
      <div>
        <h2 className="text-xl font-bold text-ink">MENA map</h2>
        <p className="text-sm text-muted">Click a country to see why it scored the way it did.</p>
      </div>

      <svg
        viewBox="0 0 100 78"
        role="img"
        aria-label="Simplified Arab countries choropleth map"
        className="mt-4 h-auto w-full rounded-md bg-paper"
      >
        <path
          d="M0 30 C18 20 29 26 41 20 C51 15 62 21 77 16 C91 12 98 20 100 29 L100 78 L0 78 Z"
          fill="#eef2f4"
        />
        {countryTiles.map((tile) => {
          const datum = byCountry.get(tile.code);
          const isSelected = selected?.country === tile.code;
          return (
            <g
              key={tile.code}
              onClick={() => handleTileClick(tile.code)}
              style={{ cursor: datum ? "pointer" : "default" }}
              role="button"
              aria-label={datum ? `${datum.country_name}, interest ${datum.interest}` : tile.code}
            >
              <rect
                x={tile.x}
                y={tile.y}
                width="10"
                height="8"
                rx="1.5"
                fill={isSelected ? "#0e7c66" : interestColor(datum?.interest ?? 10)}
                stroke={isSelected ? "#0a6355" : "#ffffff"}
                strokeWidth={isSelected ? "1.2" : "0.8"}
              />
              <text
                x={tile.x + 5}
                y={tile.y + 5.4}
                textAnchor="middle"
                fontSize="2.7"
                fontWeight="700"
                fill={isSelected ? "#ffffff" : "#17202a"}
              >
                {tile.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="mt-3 flex items-center gap-2 text-xs font-semibold text-muted">
        <span>Low</span>
        <span className="h-2 flex-1 rounded-full bg-gradient-to-r from-[#dce4e8] via-[#89b8aa] to-[#0e7c66]" />
        <span>High</span>
      </div>

      {selected && (
        <div className="mt-4 rounded-md border border-line bg-paper p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-bold text-ink text-base">{selected.country_name}</span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs font-semibold text-muted hover:text-ink"
              aria-label="Close"
            >
              close
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-md border border-line bg-white px-3 py-2">
              <div className="text-xs font-semibold text-muted">Interest score</div>
              <div className="mt-1 font-bold text-ink">{selected.interest} / 100</div>
              <div className="mt-1.5 h-1.5 rounded-full bg-slate-100">
                <div
                  className="h-1.5 rounded-full bg-accent"
                  style={{ width: `${selected.interest}%` }}
                />
              </div>
            </div>

            <div className="rounded-md border border-line bg-white px-3 py-2">
              <div className="text-xs font-semibold text-muted">Trend</div>
              <div className={`mt-1 font-bold ${trendColor(selected.trend_direction)}`}>
                {selected.trend_direction}
              </div>
            </div>

            <div className="col-span-2 rounded-md border border-line bg-white px-3 py-2">
              <div className="text-xs font-semibold text-muted">Best platform</div>
              <div className="mt-1 font-bold text-ink">{selected.best_platform}</div>
            </div>
          </div>

          {selectedRoutes.length > 0 ? (
            <div className="mt-3 space-y-2">
              {selectedRoutes.map((route) => (
                <div key={`${route.rank}-${route.platform}`} className="rounded-md border border-line bg-white px-3 py-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="rounded bg-ink px-2 py-0.5 text-xs font-bold text-white">Rank {route.rank}</span>
                    <span className="font-semibold text-ink">{route.platform}</span>
                    <span className="text-muted">{route.language}</span>
                    <span className="ml-auto font-bold text-accent">{route.match_score} pts</span>
                  </div>
                  <p className="mt-2 leading-6 text-ink">{route.why}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-muted">
              {data.length > 0
                ? "This country did not rank in the top routes for this request."
                : "Submit a request to see route reasons."}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function interestColor(interest: number) {
  if (interest >= 85) return "#0e7c66";
  if (interest >= 70) return "#3b9b83";
  if (interest >= 55) return "#89b8aa";
  if (interest >= 40) return "#b9c9c9";
  return "#dce4e8";
}

function trendColor(direction: MapDatum["trend_direction"]) {
  if (direction === "rising") return "text-accent";
  if (direction === "falling") return "text-red-500";
  return "text-muted";
}
