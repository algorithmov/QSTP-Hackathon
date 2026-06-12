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

function RouteCard({ route }: { route: RouteOption }) {
  const [expanded, setExpanded] = useState(false);
  const lowMatch = route.match_score < 50;
  const direction = route.trend_direction;

  return (
    <article className={`rounded-md border bg-white p-5 shadow-board ${lowMatch ? "border-low/40 opacity-70" : "border-line"}`}>
      <div className="grid gap-4 md:grid-cols-[1fr_148px] md:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-ink px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">Rank {route.rank}</span>
            <h3 className="text-xl font-bold leading-tight text-ink">
              {route.platform} in {route.country_name}
            </h3>
            {lowMatch ? <span className="rounded-md bg-low px-2.5 py-1 text-xs font-bold text-white">wrong room</span> : null}
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
        </div>

        <div className="rounded-md border border-line bg-paper p-4 text-center">
          <div className={`text-5xl font-black leading-none ${lowMatch ? "text-low" : "text-accent"}`}>{route.match_score}</div>
          <div className="mt-1 text-xs font-semibold uppercase text-muted">match score</div>
          <div className={`mt-3 rounded-md px-2 py-1 text-xs font-bold ${directionClass(direction)}`}>
            {direction}
            {route.trend_change_pct !== null ? ` ${route.trend_change_pct}%` : ""}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {Object.entries(route.components).map(([key, value]) => (
          <div key={key} className="rounded-md border border-line bg-white px-3 py-2">
            <div className="text-xs font-semibold capitalize text-muted">{key.replaceAll("_", " ")}</div>
            <div className="mt-1 h-1.5 rounded-full bg-slate-100">
              <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.round(value * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>

      {route.dialect_rewrite ? (
        <div className="mt-4">
          <button
            type="button"
            className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:border-accent/60"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
          >
            Dialect rewrite
            <ChevronDown size={16} className={expanded ? "rotate-180 transition" : "transition"} aria-hidden="true" />
          </button>
          {expanded ? (
            <div className="mt-3 rounded-md border border-line bg-paper p-4 text-right text-lg leading-9 text-ink" dir="rtl">
              {route.dialect_rewrite}
            </div>
          ) : null}
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
