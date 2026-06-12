"use client";

import { Clock, MapPin } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ComponentBars } from "@/components/ComponentBars";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EvidenceDisclosure } from "@/components/EvidenceDisclosure";
import { GoalSelector } from "@/components/GoalSelector";
import { IdeaSummaryCard } from "@/components/IdeaSummaryCard";
import { ErrorBlock, LoadingBlock } from "@/components/StatusBlock";
import { reviewIdea } from "@/lib/api";
import type { Goal, Ranking, ReviewResponse } from "@/types/route";

const starterText =
  "A 30-second clip idea: a Sudanese student demos a low-cost water purification filter she built from local materials.";

type Status = "idle" | "loading" | "success" | "error";

export default function ReviewPage() {
  const [ideaText, setIdeaText] = useState(starterText);
  const [goal, setGoal] = useState<Goal>("applications");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);

  const canSubmit = ideaText.trim().length > 0 && status !== "loading";

  async function handleSubmit() {
    if (!canSubmit) return;
    setStatus("loading");
    setError(null);
    try {
      const response = await reviewIdea({ idea_text: ideaText.trim(), goal });
      setResult(response);
      setStatus("success");
    } catch {
      setError("Review failed. Check the backend connection or mock file and try again.");
      setStatus("error");
    }
  }

  return (
    <AppShell>
      <section className="rounded-md border border-line bg-white p-5 shadow-board">
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <label className="block">
            <span className="text-sm font-semibold text-ink">Idea or post text</span>
            <textarea
              className="mt-2 min-h-40 w-full resize-y rounded-md border border-line bg-white px-4 py-3 text-base leading-7 text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:bg-slate-50"
              value={ideaText}
              disabled={status === "loading"}
              onChange={(event) => setIdeaText(event.target.value)}
              placeholder="Paste a campaign idea, caption, or post concept."
            />
            <span className="mt-2 block text-xs font-semibold text-muted">
              {ideaText.length} characters
            </span>
          </label>
          <div className="flex flex-col justify-between gap-4">
            <div>
              <span className="text-sm font-semibold text-ink">Goal</span>
              <div className="mt-2">
                <GoalSelector value={goal} disabled={status === "loading"} onChange={setGoal} />
              </div>
            </div>
            <button
              type="button"
              disabled={!canSubmit}
              className="rounded-md bg-accent px-6 py-3 text-sm font-bold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
              onClick={handleSubmit}
            >
              {status === "loading" ? "Reviewing..." : "Review my idea"}
            </button>
          </div>
        </div>
      </section>

      {status === "loading" ? <LoadingBlock label="Reviewing idea fit..." /> : null}
      {status === "error" && error ? <ErrorBlock message={error} /> : null}

      {result ? (
        <>
          <IdeaSummaryCard summary={result.idea_summary} />
          <MethodologyNote note={result.methodology_note} />
          <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
            <RankingBoard rankings={result.rankings} />
            <CountryOverview data={result.map_data} />
          </div>
        </>
      ) : (
        <section className="rounded-md border border-line bg-white p-6 text-muted shadow-board">
          Review results will appear here after you submit an idea.
        </section>
      )}
    </AppShell>
  );
}

function MethodologyNote({ note }: { note: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board">
      <button
        type="button"
        className="text-sm font-bold text-ink hover:text-accent"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        Methodology note
      </button>
      {open ? <p className="mt-3 max-w-4xl text-sm leading-6 text-muted">{note}</p> : null}
    </section>
  );
}

function RankingBoard({ rankings }: { rankings: Ranking[] }) {
  return (
    <section className="space-y-3" aria-label="Ranking board">
      {rankings.map((ranking) => (
        <RankingCard key={`${ranking.rank}-${ranking.country}-${ranking.platform}`} ranking={ranking} />
      ))}
    </section>
  );
}

function RankingCard({ ranking }: { ranking: Ranking }) {
  const lowFit = ranking.fit_score < 50;

  return (
    <article
      className={`rounded-md border bg-white p-5 shadow-board ${
        lowFit ? "border-low/40 opacity-75" : "border-line"
      }`}
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_180px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-ink px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">
              Rank {ranking.rank}
            </span>
            <h2 className="text-xl font-bold leading-tight text-ink">
              {ranking.platform} in {ranking.country_name}
            </h2>
            <ConfidenceBadge confidence={ranking.confidence} />
            {lowFit ? (
              <span className="rounded-md bg-low px-2.5 py-1 text-xs font-bold text-white">
                Low fit
              </span>
            ) : null}
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted">
            <span className="flex items-center gap-1.5">
              <Clock size={15} aria-hidden="true" />
              {ranking.recommended_time_local}
            </span>
            <span className="flex items-center gap-1.5">
              <MapPin size={15} aria-hidden="true" />
              {ranking.timezone}
            </span>
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-ink">{ranking.why}</p>
        </div>
        <div className="rounded-md border border-line bg-paper p-4 text-center">
          <div className={`text-5xl font-black leading-none ${lowFit ? "text-low" : "text-accent"}`}>
            {ranking.fit_score}
          </div>
          <div className="mt-1 text-xs font-semibold uppercase text-muted">fit score</div>
        </div>
      </div>
      <div className="mt-4 rounded-md border border-line bg-white p-3">
        <ComponentBars components={ranking.components} />
      </div>
      <EvidenceDisclosure evidence={ranking.evidence} />
    </article>
  );
}

function CountryOverview({ data }: { data: ReviewResponse["map_data"] }) {
  const rows = useMemo(
    () => [...data].sort((a, b) => b.best_fit_score - a.best_fit_score),
    [data]
  );

  return (
    <aside className="rounded-md border border-line bg-white p-5 shadow-board">
      <h2 className="text-lg font-bold text-ink">Country overview</h2>
      <div className="mt-4 overflow-hidden rounded-md border border-line">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-paper text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-2">Country</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">Platform</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.country}>
                <td className="px-3 py-3 font-semibold text-ink">{row.country_name}</td>
                <td className="px-3 py-3 text-accent font-bold">{row.best_fit_score}</td>
                <td className="px-3 py-3 text-muted">{row.best_platform}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </aside>
  );
}
