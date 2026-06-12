"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ScoreComponents } from "@/types/route";

const labels: Record<keyof ScoreComponents, string> = {
  topic_relevance: "Topic",
  audience_fit: "Audience",
  platform_fit: "Platform",
  language_fit: "Language",
  timing_fit: "Timing"
};

export function ComponentBars({ components }: { components: ScoreComponents }) {
  const data = (Object.keys(labels) as Array<keyof ScoreComponents>).map((key) => ({
    name: labels[key],
    score: Math.round(components[key] * 100)
  }));

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 12, bottom: 8, left: 4 }}
        >
          <CartesianGrid stroke="#e5eaf0" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" width={74} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [`${value}%`, "Score"]} cursor={{ fill: "#f7f8f9" }} />
          <Bar dataKey="score" fill="#0e7c66" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
