'use client';
import { useEffect, useRef } from 'react';
import { TrendTickerItem } from '../lib/types';

interface Props {
  items: TrendTickerItem[];
}

export default function TrendTicker({ items }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || items.length === 0) return;
    let frame: number;
    let pos = 0;
    const speed = 0.4; // px per frame
    const totalWidth = track.scrollWidth / 2;

    const tick = () => {
      pos += speed;
      if (pos >= totalWidth) pos = 0;
      track.style.transform = `translateX(-${pos}px)`;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [items]);

  if (items.length === 0) return null;

  const doubled = [...items, ...items];

  return (
    <div className="bg-gray-900 text-white overflow-hidden rounded-lg">
      <div className="flex items-center">
        <div className="shrink-0 px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-widest border-r border-gray-700">
          Trends
        </div>
        <div className="flex-1 overflow-hidden py-2">
          <div ref={trackRef} className="flex gap-0 whitespace-nowrap" style={{ willChange: 'transform' }}>
            {doubled.map((item, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-5 text-sm text-gray-200 border-r border-gray-700 last:border-0"
              >
                <span className="text-green-400 font-medium">+{item.change_pct}%</span>
                <span>{item.topic}</span>
                <span className="text-gray-500">/</span>
                <span className="text-gray-400">{item.country}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
