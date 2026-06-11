'use client';
import { useState } from 'react';
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from 'react-simple-maps';
import { MapEntry } from '../lib/types';

const GEO_URL =
  'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';

// ISO numeric → alpha-2 for Arab countries we cover
const NUMERIC_TO_ALPHA2: Record<string, string> = {
  '818': 'EG',
  '682': 'SA',
  '784': 'AE',
  '634': 'QA',
  '12':  'DZ',
  '504': 'MA',
  '400': 'JO',
  '729': 'SD',
  '368': 'IQ',
  '414': 'KW',
};

function interestToColor(interest: number): string {
  // 0 → #e2e8f0 (light gray-blue), 100 → #1d4ed8 (blue-700)
  const t = interest / 100;
  const r = Math.round(226 + (29 - 226) * t);
  const g = Math.round(232 + (78 - 232) * t);
  const b = Math.round(240 + (216 - 240) * t);
  return `rgb(${r},${g},${b})`;
}

interface Props {
  mapData: MapEntry[];
}

export default function MenaMap({ mapData }: Props) {
  const [tooltip, setTooltip] = useState<{
    content: string;
    x: number;
    y: number;
  } | null>(null);

  const byCode = Object.fromEntries(mapData.map(d => [d.country, d]));

  return (
    <div className="relative bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ center: [40, 25], scale: 380 }}
        style={{ width: '100%', height: '320px' }}
      >
        <ZoomableGroup>
          <Geographies geography={GEO_URL}>
            {({ geographies }: { geographies: any[] }) =>
              geographies.map((geo: any) => {
                const numericId = String(geo.id);
                const alpha2 = NUMERIC_TO_ALPHA2[numericId];
                const entry = alpha2 ? byCode[alpha2] : undefined;

                const isArab = Boolean(alpha2 && entry);
                const fill = isArab
                  ? interestToColor(entry!.interest)
                  : '#e5e7eb';
                const stroke = isArab ? '#cbd5e1' : '#d1d5db';

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={0.5}
                    style={{
                      default: { outline: 'none' },
                      hover: {
                        outline: 'none',
                        fill: isArab ? '#2563eb' : '#e5e7eb',
                        cursor: isArab ? 'pointer' : 'default',
                      },
                      pressed: { outline: 'none' },
                    }}
                    onMouseEnter={(e: React.MouseEvent) => {
                      if (!entry) return;
                      setTooltip({
                        content: `${entry.country_name} · interest ${entry.interest} · ${entry.trend_direction} · ${entry.best_platform}`,
                        x: e.clientX,
                        y: e.clientY,
                      });
                    }}
                    onMouseMove={(e: React.MouseEvent) => {
                      if (!entry) return;
                      setTooltip(prev =>
                        prev ? { ...prev, x: e.clientX, y: e.clientY } : null
                      );
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })
            }
          </Geographies>
        </ZoomableGroup>
      </ComposableMap>

      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none bg-gray-900 text-white text-xs px-2.5 py-1.5 rounded shadow-lg"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          {tooltip.content}
        </div>
      )}

      <div className="px-4 pb-3 flex items-center gap-3 text-xs text-gray-500">
        <span>Low interest</span>
        <div className="flex h-2 flex-1 rounded overflow-hidden">
          {Array.from({ length: 20 }, (_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                background: interestToColor((i / 19) * 100),
              }}
            />
          ))}
        </div>
        <span>High</span>
      </div>
    </div>
  );
}
