import type { Confidence } from "@/types/route";

const classes: Record<Confidence, string> = {
  high: "border-emerald-200 bg-emerald-50 text-emerald-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-slate-200 bg-slate-100 text-slate-700"
};

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return (
    <span className={`rounded-md border px-2.5 py-1 text-xs font-bold uppercase ${classes[confidence]}`}>
      {confidence} confidence
    </span>
  );
}
