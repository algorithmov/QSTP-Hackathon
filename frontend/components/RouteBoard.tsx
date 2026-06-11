'use client';
import { useState } from 'react';
import { Route } from '../lib/types';

const TREND_STYLES: Record<string, { label: string; cls: string }> = {
  rising:  { label: 'rising',  cls: 'text-green-700 bg-green-50 border-green-200' },
  flat:    { label: 'flat',    cls: 'text-gray-500 bg-gray-100 border-gray-200' },
  falling: { label: 'falling', cls: 'text-red-600 bg-red-50 border-red-200' },
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-gray-400 shrink-0">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div
          className="bg-blue-400 h-1.5 rounded-full"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="w-8 text-right text-gray-500">{Math.round(value * 100)}</span>
    </div>
  );
}

function RouteCard({ route }: { route: Route }) {
  const [showComponents, setShowComponents] = useState(false);
  const isWeak = route.match_score < 50;
  const trend = TREND_STYLES[route.trend_direction] ?? TREND_STYLES.flat;

  return (
    <div
      className={`bg-white border rounded-lg p-5 transition-opacity ${
        isWeak ? 'opacity-50 border-gray-200' : 'border-gray-200 shadow-sm'
      }`}
    >
      {isWeak && (
        <div className="mb-2 text-xs font-semibold text-gray-400 uppercase tracking-widest">
          wrong room
        </div>
      )}

      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-xs text-gray-400 font-mono tabular-nums">#{route.rank}</span>
            <span className="text-base font-semibold text-gray-900">{route.platform}</span>
            <span className="text-gray-600">{route.country_name}</span>
            <span className="text-sm text-gray-400">{route.audience}</span>
          </div>

          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-gray-500">
            <span>{route.language}</span>
            <span>{route.post_time_local}</span>
            <span className="text-gray-400">{route.timezone}</span>
          </div>

          <p className="mt-2 text-sm text-gray-700 leading-relaxed">{route.why}</p>

          {route.dialect_rewrite && (
            <details className="mt-2">
              <summary className="text-xs text-gray-400 cursor-pointer select-none hover:text-gray-600">
                Dialect rewrite
              </summary>
              <p dir="rtl" lang="ar" className="mt-1.5 text-sm text-gray-800 leading-relaxed bg-gray-50 rounded p-2">
                {route.dialect_rewrite}
              </p>
            </details>
          )}

          <button
            type="button"
            onClick={() => setShowComponents(v => !v)}
            className="mt-3 text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2"
          >
            {showComponents ? 'Hide' : 'Show'} score breakdown
          </button>

          {showComponents && (
            <div className="mt-2 space-y-1.5">
              <ScoreBar label="platform fit"  value={route.components.platform_fit} />
              <ScoreBar label="audience fit"  value={route.components.audience_fit} />
              <ScoreBar label="geo fit"       value={route.components.geo_fit} />
              <ScoreBar label="timing fit"    value={route.components.timing_fit} />
              <ScoreBar label="language fit"  value={route.components.language_fit} />
              <ScoreBar label="predicted eng" value={route.components.predicted_engagement} />
            </div>
          )}
        </div>

        <div className="shrink-0 text-right">
          <div className={`text-4xl font-bold tabular-nums ${isWeak ? 'text-gray-300' : 'text-blue-600'}`}>
            {route.match_score}
          </div>
          <div className="text-xs text-gray-400">/ 100</div>
          <div className="mt-1.5">
            <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${trend.cls}`}>
              {trend.label}
              {route.trend_change_pct != null && route.trend_change_pct !== 0
                ? ` ${route.trend_change_pct > 0 ? '+' : ''}${route.trend_change_pct}%`
                : ''}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RouteBoard({ routes }: { routes: Route[] }) {
  if (routes.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-8 text-center">
        No routes returned for this request.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {routes.map(route => (
        <RouteCard key={route.rank} route={route} />
      ))}
    </div>
  );
}
