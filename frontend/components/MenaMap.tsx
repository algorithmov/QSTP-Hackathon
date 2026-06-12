"use client";

import { useMemo, useState } from "react";
import type { MapDatum } from "@/types/route";

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
};

export function MenaMap({ data }: MenaMapProps) {
  const [hovered, setHovered] = useState<MapDatum | null>(null);
  const byCountry = useMemo(() => new Map(data.map((datum) => [datum.country, datum])), [data]);

  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board" aria-label="MENA interest map">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-ink">MENA map</h2>
          <p className="text-sm text-muted">Darker countries show stronger content interest.</p>
        </div>
        <div className="text-sm font-semibold text-muted">{hovered ? tooltipText(hovered) : "Hover a country"}</div>
      </div>

      <svg viewBox="0 0 100 78" role="img" aria-label="Simplified Arab countries choropleth map" className="mt-4 h-auto w-full rounded-md bg-paper">
        <path d="M0 30 C18 20 29 26 41 20 C51 15 62 21 77 16 C91 12 98 20 100 29 L100 78 L0 78 Z" fill="#eef2f4" />
        {countryTiles.map((tile) => {
          const datum = byCountry.get(tile.code);
          return (
            <g key={tile.code} onMouseEnter={() => setHovered(datum ?? null)} onMouseLeave={() => setHovered(null)}>
              <rect
                x={tile.x}
                y={tile.y}
                width="10"
                height="8"
                rx="1.5"
                fill={interestColor(datum?.interest ?? 10)}
                stroke="#ffffff"
                strokeWidth="0.8"
              />
              <text x={tile.x + 5} y={tile.y + 5.4} textAnchor="middle" fontSize="2.7" fontWeight="700" fill="#17202a">
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

function tooltipText(datum: MapDatum) {
  return `${datum.country_name}: ${datum.interest}, ${datum.trend_direction}, ${datum.best_platform}`;
}
