import type { IdeaSummary } from "@/types/route";

export function IdeaSummaryCard({ summary }: { summary: IdeaSummary }) {
  return (
    <section className="rounded-md border border-line bg-white/95 p-5 shadow-board">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-wide text-muted">Idea summary</div>
          <h2 className="mt-2 max-w-3xl text-xl font-bold leading-tight text-ink">
            {summary.topic}
          </h2>
          <div className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-3">
            <span>
              <span className="font-semibold text-ink">Type:</span> {summary.content_type}
            </span>
            <span>
              <span className="font-semibold text-ink">Audience:</span>{" "}
              {summary.primary_audience}
            </span>
            <span>
              <span className="font-semibold text-ink">Language:</span>{" "}
              {summary.suggested_language}
            </span>
          </div>
        </div>
        <div className="flex max-w-xl flex-wrap gap-2">
          {summary.key_themes.map((theme) => (
            <span
              key={theme}
              className="rounded-md border border-line bg-paper px-2.5 py-1 text-xs font-semibold text-ink"
            >
              {theme}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
