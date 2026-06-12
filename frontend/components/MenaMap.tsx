"use client";

import { useMemo, useState } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from "react-simple-maps";
import type { MapDatum, RouteOption } from "@/types/route";

// ISO 3166-1 numeric → alpha-2 for MENA countries
const NUMERIC_TO_ALPHA2: Record<string, string> = {
  "12": "DZ",   // Algeria
  "818": "EG",  // Egypt
  "368": "IQ",  // Iraq
  "400": "JO",  // Jordan
  "414": "KW",  // Kuwait
  "422": "LB",  // Lebanon
  "434": "LY",  // Libya
  "504": "MA",  // Morocco
  "512": "OM",  // Oman
  "634": "QA",  // Qatar
  "682": "SA",  // Saudi Arabia
  "729": "SD",  // Sudan
  "760": "SY",  // Syria
  "788": "TN",  // Tunisia
  "784": "AE",  // UAE
  "887": "YE",  // Yemen
  "275": "PS",  // Palestine
};

const FLAGS: Record<string, string> = {
  SA: "🇸🇦", EG: "🇪🇬", AE: "🇦🇪", QA: "🇶🇦", KW: "🇰🇼",
  JO: "🇯🇴", IQ: "🇮🇶", MA: "🇲🇦", DZ: "🇩🇿", SD: "🇸🇩",
  LY: "🇱🇾", TN: "🇹🇳", LB: "🇱🇧", SY: "🇸🇾", YE: "🇾🇪",
};

const GEO_URL = "/world-110m.json";

type MenaMapProps = {
  data: MapDatum[];
  routes: RouteOption[];
};

export function MenaMap({ data, routes }: MenaMapProps) {
  const [selected, setSelected] = useState<string | null>(null);

  const byAlpha2 = useMemo(
    () => new Map(data.map((d) => [d.country, d])),
    [data]
  );

  const routesByCountry = useMemo(() => {
    const m = new Map<string, RouteOption[]>();
    for (const r of routes) {
      m.set(r.country, [...(m.get(r.country) ?? []), r]);
    }
    return m;
  }, [routes]);

  const maxInterest = useMemo(
    () => Math.max(...data.map((d) => d.interest), 1),
    [data]
  );

  function fillColor(alpha2: string): string {
    const datum = byAlpha2.get(alpha2);
    if (selected === alpha2) return "#0a6355";
    if (!datum) return "#d4e0e8";
    const t = datum.interest / maxInterest;
    if (t >= 0.9) return "#0e7c66";
    if (t >= 0.7) return "#2d9f84";
    if (t >= 0.5) return "#5dbfa6";
    if (t >= 0.3) return "#99d4c4";
    return "#c7e8df";
  }

  const selectedDatum = selected ? byAlpha2.get(selected) : null;
  const selectedRoutes = selected ? (routesByCountry.get(selected) ?? []) : [];

  if (data.length === 0) {
    return (
      <section className="rounded-md border border-line bg-white p-5 shadow-board">
        <h2 className="text-xl font-bold text-ink">Region signals</h2>
        <p className="mt-1 text-sm text-muted">Submit a request to see the map.</p>
      </section>
    );
  }

  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board" aria-label="Region choropleth">
      <h2 className="text-xl font-bold text-ink">Region signals</h2>
      <p className="mt-1 text-sm text-muted">Click a country to see route details.</p>

      <div className="mt-3 overflow-hidden rounded-md border border-line" style={{ background: "#c8dde8" }}>
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ center: [40, 25], scale: 420 }}
          width={480}
          height={280}
          style={{ width: "100%", height: "auto" }}
        >
          <ZoomableGroup zoom={1} minZoom={0.8} maxZoom={4}>
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies
                  .filter((geo) => geo.id in NUMERIC_TO_ALPHA2)
                  .map((geo) => {
                    const alpha2 = NUMERIC_TO_ALPHA2[geo.id];
                    const hasDatum = byAlpha2.has(alpha2);
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        fill={fillColor(alpha2)}
                        stroke="#ffffff"
                        strokeWidth={0.5}
                        style={{
                          default: { outline: "none" },
                          hover: {
                            outline: "none",
                            fill: hasDatum ? "#0a6355" : "#c2d4dc",
                            cursor: hasDatum ? "pointer" : "default",
                          },
                          pressed: { outline: "none" },
                        }}
                        onClick={() => {
                          if (!hasDatum) return;
                          setSelected((prev) => (prev === alpha2 ? null : alpha2));
                        }}
                      />
                    );
                  })
              }
            </Geographies>
          </ZoomableGroup>
        </ComposableMap>
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-muted">
        <span>Low interest</span>
        <span className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-[#c7e8df] to-[#0e7c66]" />
        <span>High</span>
      </div>

      {selectedDatum && (
        <div className="mt-3 rounded-md border border-line bg-paper p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-base font-bold text-ink">
              <span aria-hidden="true">{FLAGS[selectedDatum.country] ?? ""}</span>
              {selectedDatum.country_name}
            </span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs font-semibold text-muted hover:text-ink"
            >
              close
            </button>
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="rounded-md border border-line bg-white px-3 py-2 text-center">
              <div className="text-xs font-semibold text-muted">Interest</div>
              <div className="mt-0.5 text-lg font-black text-accent">{selectedDatum.interest}</div>
            </div>
            <div className="rounded-md border border-line bg-white px-3 py-2 text-center">
              <div className="text-xs font-semibold text-muted">Trend</div>
              <div className={`mt-0.5 text-sm font-bold ${selectedDatum.trend_direction === "rising" ? "text-accent" : selectedDatum.trend_direction === "falling" ? "text-red-500" : "text-muted"}`}>
                {selectedDatum.trend_direction}
              </div>
            </div>
            <div className="rounded-md border border-line bg-white px-3 py-2 text-center">
              <div className="text-xs font-semibold text-muted">Best platform</div>
              <div className="mt-0.5 text-sm font-bold text-ink">{selectedDatum.best_platform}</div>
            </div>
          </div>

          {selectedRoutes.length > 0 ? (
            <div className="mt-3 space-y-2">
              {selectedRoutes.map((route) => (
                <div key={`${route.rank}-${route.platform}`} className="rounded-md border border-line bg-white px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-ink px-2 py-0.5 text-xs font-bold text-white">#{route.rank}</span>
                    <span className="font-semibold text-ink">{route.platform}</span>
                    <span className="text-xs text-muted">{route.language}</span>
                    <span className="ml-auto font-bold text-accent">{route.match_score}</span>
                  </div>
                  <p className="mt-1.5 leading-6 text-ink">{route.why}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-muted">No top routes for this country in this request.</p>
          )}
        </div>
      )}
    </section>
  );
}
