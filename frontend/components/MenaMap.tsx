"use client";

import { useMemo, useState } from "react";
import type { MapDatum, RouteOption } from "@/types/route";

type CountryShape = {
  code: string;
  label: string;
  cx: number;
  cy: number;
  points: string;
};

const countryShapes: CountryShape[] = [
  { code: "MA", label: "MA", cx: 7,  cy: 23, points: "1,9 14,9 15,20 12,32 7,40 1,32" },
  { code: "DZ", label: "DZ", cx: 22, cy: 34, points: "14,9 32,8 32,60 14,60 12,32 15,20" },
  { code: "TN", label: "TN", cx: 34, cy: 16, points: "32,8 37,8 39,15 36,24 32,22" },
  { code: "LY", label: "LY", cx: 43, cy: 36, points: "32,22 36,24 39,15 37,8 54,8 54,60 32,60" },
  { code: "EG", label: "EG", cx: 61, cy: 34, points: "54,8 65,8 69,14 72,18 70,30 65,33 64,58 54,58" },
  { code: "SD", label: "SD", cx: 59, cy: 70, points: "54,58 66,58 68,74 67,82 54,82" },
  { code: "JO", label: "JO", cx: 70, cy: 24, points: "69,14 74,14 76,20 74,34 66,34 65,33 70,30 72,18" },
  { code: "IQ", label: "IQ", cx: 81, cy: 16, points: "74,6 90,6 90,24 83,28 77,24 76,20 74,14" },
  { code: "KW", label: "KW", cx: 85, cy: 30, points: "83,28 87,28 87,32 83,32" },
  { code: "SA", label: "SA", cx: 82, cy: 50, points: "66,34 74,34 77,24 83,28 87,28 91,32 96,40 94,58 88,62 79,64 70,58" },
  { code: "QA", label: "QA", cx: 92, cy: 37, points: "91,34 94,34 93,40 91,40" },
  { code: "AE", label: "AE", cx: 95, cy: 42, points: "94,32 100,30 100,50 90,50 90,40 93,40 94,34" },
];

type MenaMapProps = {
  data: MapDatum[];
  routes: RouteOption[];
};

export function MenaMap({ data, routes }: MenaMapProps) {
  const [selected, setSelected] = useState<MapDatum | null>(null);

  const byCountry = useMemo(
    () => new Map(data.map((d) => [d.country, d])),
    [data]
  );

  const routesByCountry = useMemo(() => {
    const map = new Map<string, RouteOption[]>();
    for (const r of routes) {
      map.set(r.country, [...(map.get(r.country) ?? []), r]);
    }
    return map;
  }, [routes]);

  function handleClick(code: string) {
    const datum = byCountry.get(code);
    if (!datum) return;
    setSelected((prev) => (prev?.country === code ? null : datum));
  }

  const selectedRoutes = selected ? (routesByCountry.get(selected.country) ?? []) : [];

  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board" aria-label="MENA interest map">
      <h2 className="text-xl font-bold text-ink">MENA map</h2>
      <p className="text-sm text-muted">
        {data.length > 0 ? "Click a country to see why it scored the way it did." : "Submit a request to see the map."}
      </p>

      <svg
        viewBox="0 0 100 82"
        role="img"
        aria-label="MENA region choropleth map"
        className="mt-4 h-auto w-full rounded-md"
        style={{ background: "#c8dce8" }}
      >
        {countryShapes.map((shape) => {
          const datum = byCountry.get(shape.code);
          const isSelected = selected?.country === shape.code;
          const hasData = !!datum;

          return (
            <g
              key={shape.code}
              onClick={() => handleClick(shape.code)}
              style={{ cursor: hasData ? "pointer" : "default" }}
              aria-label={datum ? `${datum.country_name}, interest ${datum.interest}` : shape.code}
            >
              <polygon
                points={shape.points}
                fill={
                  isSelected
                    ? "#0a6355"
                    : hasData
                    ? interestColor(datum.interest)
                    : "#dde4e8"
                }
                stroke="#ffffff"
                strokeWidth="0.6"
                strokeLinejoin="round"
              />
              <text
                x={shape.cx}
                y={shape.cy + 1}
                textAnchor="middle"
                fontSize={shape.code === "KW" || shape.code === "QA" ? "2.0" : "2.6"}
                fontWeight="700"
                fill={isSelected ? "#ffffff" : hasData ? "#17202a" : "#9aacb6"}
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {shape.label}
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
            <span className="text-base font-bold text-ink">{selected.country_name}</span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs font-semibold text-muted hover:text-ink"
            >
              close
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-md border border-line bg-white px-3 py-2">
              <div className="text-xs font-semibold text-muted">Interest score</div>
              <div className="mt-1 font-bold text-ink">{selected.interest} / 100</div>
              <div className="mt-1.5 h-1.5 rounded-full bg-slate-100">
                <div className="h-1.5 rounded-full bg-accent" style={{ width: `${selected.interest}%` }} />
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
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-ink px-2 py-0.5 text-xs font-bold text-white">
                      Rank {route.rank}
                    </span>
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
              This country did not rank in the top routes for this request.
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
