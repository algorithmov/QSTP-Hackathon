import type { IdeaSummary } from "@/types/route";

export function IdeaSummaryCard({ summary }: { summary: IdeaSummary }) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-board">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">Idea summary</div>
      <h2 className="mt-1.5 text-lg font-bold text-ink">{summary.topic}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        <Pill label="Type" value={summary.content_type} />
        <Pill label="Audience" value={summary.primary_audience} />
        <Pill label="Language" value={summary.suggested_language} />
        {summary.key_themes.map((theme) => (
          <span key={theme} className="rounded border border-line bg-paper/60 px-2.5 py-1 text-xs text-muted">
            {theme}
          </span>
        ))}
      </div>
    </section>
  );
}

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded border border-line bg-paper/60 px-2.5 py-1 text-xs text-ink">
      <span className="font-semibold">{label}:</span> {value}
    </span>
  );
}
