"use client";

import { FileImage, FileText, FileVideo, Loader2, Sparkles, X as XIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EvidenceDisclosure } from "@/components/EvidenceDisclosure";
import { GoalSelector } from "@/components/GoalSelector";
import { IdeaSummaryCard } from "@/components/IdeaSummaryCard";
import { ErrorBlock, LoadingBlock } from "@/components/StatusBlock";
import { fetchPlatformReport, reviewIdea } from "@/lib/api";
import { usePersistentState } from "@/lib/usePersistentState";
import type {
  Goal,
  PlatformReportResponse,
  Ranking,
  ReviewResponse
} from "@/types/route";

const starterText =
  "A 30-second clip idea: a student founder shows a compact desalination prototype solving water access for remote clinics.";

type Status = "idle" | "uploading" | "extracting" | "matching" | "scoring" | "done" | "error";
type ModalView = "breakdown" | "report";

const LOADING_STEPS: Record<Status, string> = {
  idle: "",
  uploading: "Uploading media...",
  extracting: "Extracting Gemini context from media...",
  matching: "Matching Stars of Science records...",
  scoring: "Scoring platforms...",
  done: "",
  error: "",
};

function normalizeGoal(value: Goal | string): Goal {
  return value === "viewers" || value === "sponsors" ? value : "applications";
}

function mediaIcon(mime: string) {
  if (mime.startsWith("image/")) return <FileImage size={14} className="shrink-0 text-muted" />;
  if (mime.startsWith("video/")) return <FileVideo size={14} className="shrink-0 text-muted" />;
  return <FileText size={14} className="shrink-0 text-muted" />;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ReviewPage() {
  const [ideaText, setIdeaText] = usePersistentState("masar.review.ideaText", starterText);
  const [goal, setGoal] = usePersistentState<Goal>(
    "masar.review.goal",
    "applications",
    normalizeGoal,
  );
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = usePersistentState<ReviewResponse | null>("masar.review.result.v4", null);
  const [activeRanking, setActiveRanking] = useState<Ranking | null>(null);
  const [modalView, setModalView] = useState<ModalView>("breakdown");
  const [report, setReport] = useState<PlatformReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [mediaFiles, setMediaFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // One-time migration: remove stale data from all old localStorage keys
  useEffect(() => {
    try {
      ["masar.review.result", "masar.review.result.v2", "masar.review.result.v3"].forEach(
        (k) => localStorage.removeItem(k)
      );
    } catch { /* ignore */ }
  }, []);

  const isLoading = status !== "idle" && status !== "done" && status !== "error";
  const canSubmit = ideaText.trim().length > 0 && !isLoading;

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    const ALLOWED = ["image/", "video/", "audio/"];
    const MAX = 18 * 1024 * 1024;
    const valid = Array.from(incoming).filter(
      (f) => ALLOWED.some((p) => f.type.startsWith(p)) && f.size <= MAX
    );
    setMediaFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      return [...prev, ...valid.filter((f) => !existingNames.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setMediaFiles((prev) => prev.filter((f) => f.name !== name));
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    setError(null);

    if (mediaFiles.length > 0) {
      setStatus("uploading");
      await new Promise((r) => setTimeout(r, 300));
      setStatus("extracting");
      await new Promise((r) => setTimeout(r, 400));
    }

    setStatus("matching");
    try {
      const response = await reviewIdea({ idea_text: ideaText.trim(), goal, files: mediaFiles });
      setResult(response);
      setStatus("done");
    } catch {
      setError("Review failed. Check the backend connection or try again.");
      setStatus("error");
    }
  }

  function openBreakdown(ranking: Ranking) {
    setActiveRanking(ranking);
    setModalView("breakdown");
    setReport(null);
  }

  async function openReport(ranking: Ranking) {
    setActiveRanking(ranking);
    setModalView("report");
    setReport(null);
    setReportLoading(true);
    try {
      const response = await fetchPlatformReport({
        idea_text: ideaText.trim(),
        goal,
        platform: ranking.platform,
        media_context: result?.media_context ?? null,
      });
      setReport(response);
    } catch {
      // report stays null — the modal shows a retry state
    } finally {
      setReportLoading(false);
    }
  }

  async function retryReport(ranking: Ranking) {
    await openReport(ranking);
  }

  return (
    <AppShell>
      <section className="rounded-md border border-line/90 bg-white/95 p-5 shadow-board ring-1 ring-white/60">
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <label className="block">
            <span className="text-sm font-semibold text-ink">Idea or post text</span>
            <textarea
              className="mt-2 min-h-40 w-full resize-y rounded-md border border-line/90 bg-[linear-gradient(180deg,#ffffff,rgba(245,243,243,0.65))] px-4 py-3 text-base leading-7 text-ink outline-none transition duration-200 focus:border-accent focus:shadow-[0_0_0_4px_rgba(14,124,102,0.12)] disabled:bg-slate-50"
              value={ideaText}
              disabled={isLoading}
              onChange={(event) => setIdeaText(event.target.value)}
              placeholder="Paste a Stars of Science campaign idea, caption, or post concept."
            />
            <span className="mt-2 block text-xs font-semibold text-muted">
              {ideaText.length} characters
            </span>
          </label>
          <div className="flex flex-col justify-between gap-4">
            <div>
              <span className="text-sm font-semibold text-ink">Goal</span>
              <div className="mt-2">
                <GoalSelector value={goal} disabled={isLoading} onChange={setGoal} />
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">
                The reviewer compares only the five official Stars of Science platforms and grounds every score in matched content records.
              </p>
            </div>
            <button
              type="button"
              disabled={!canSubmit}
              className="rounded-md border border-accent bg-accent px-6 py-3 text-sm font-bold text-white shadow-[0_16px_30px_rgba(241,90,33,0.2)] transition duration-200 hover:-translate-y-0.5 hover:bg-accent/90 disabled:translate-y-0 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300 disabled:text-slate-600 disabled:shadow-none"
              onClick={handleSubmit}
            >
              {isLoading ? LOADING_STEPS[status] || "Reviewing..." : "Review for Stars of Science"}
            </button>
          </div>
        </div>

        <div className="mt-4 rounded-md border border-dashed border-line/90 bg-[linear-gradient(180deg,rgba(245,243,243,0.45),rgba(255,255,255,0.92))] p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ink">
              Media{" "}
              <span className="text-xs font-normal text-muted">(optional — image, video, or audio)</span>
            </span>
            <button
              type="button"
              disabled={isLoading}
              className="rounded-md border-2 border-accent/70 bg-white px-3.5 py-2 text-xs font-black uppercase tracking-wide text-accent shadow-sm transition hover:-translate-y-0.5 hover:border-accent hover:bg-accent hover:text-white disabled:cursor-not-allowed disabled:border-line disabled:text-muted disabled:opacity-70"
              onClick={() => fileInputRef.current?.click()}
            >
              Add file
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*,audio/*"
              multiple
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {mediaFiles.length > 0 ? (
            <ul className="mt-3 space-y-2">
              {mediaFiles.map((file) => (
                <li
                  key={file.name}
                  className="flex items-center gap-2 rounded-md border border-line/90 bg-white px-3 py-2 text-xs shadow-sm"
                >
                  {mediaIcon(file.type)}
                  <span className="flex-1 truncate text-ink">{file.name}</span>
                  <span className="shrink-0 text-muted">{formatBytes(file.size)}</span>
                  <button
                    type="button"
                    className="shrink-0 text-muted transition hover:text-ink"
                    onClick={() => removeFile(file.name)}
                    aria-label={`Remove ${file.name}`}
                    disabled={isLoading}
                  >
                    <XIcon size={12} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-xs text-muted">
              Gemini will extract content type, language, visual cues, and caption drafts from uploaded media.
            </p>
          )}
        </div>
      </section>

      {isLoading ? <LoadingBlock label={LOADING_STEPS[status] || "Reviewing..."} /> : null}
      {status === "error" && error ? <ErrorBlock message={error} /> : null}

      {result ? (
        <>
          <IdeaSummaryCard summary={result.idea_summary} />
          {result.media_context_used ? (
            <MediaAnalysisCard result={result} />
          ) : null}
          <MethodologyNote note={result.methodology_note} />
          <TopCallout ranking={result.rankings[0]} />
          <RankingBoard rankings={result.rankings} onOpenBreakdown={openBreakdown} onOpenReport={openReport} />
          <InsightRail rankings={result.rankings} />
        </>
      ) : (
        <section className="rounded-md border border-line/90 bg-white/95 p-6 text-muted shadow-board ring-1 ring-white/60">
          Review results will appear here after you submit an idea.
        </section>
      )}

      {activeRanking ? (
        <PlatformModal
          view={modalView}
          ranking={activeRanking}
          report={report}
          loading={reportLoading}
          captionDrafts={result?.caption_drafts ?? []}
          onClose={() => {
            setActiveRanking(null);
            setReport(null);
            setReportLoading(false);
          }}
          onRetryReport={() => retryReport(activeRanking)}
        />
      ) : null}
    </AppShell>
  );
}

function MediaAnalysisCard({ result }: { result: ReviewResponse }) {
  return (
    <section className="rounded-md border border-line bg-white/95 p-5 shadow-board">
      <div className="flex items-center gap-2">
        <span className="rounded-md bg-ink/10 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-ink">
          Media analysed
        </span>
        <span className="text-xs text-muted">
          {result.media_assets.length} file{result.media_assets.length !== 1 ? "s" : ""}
        </span>
      </div>
      {result.media_summary ? (
        <p className="mt-3 text-sm leading-6 text-ink">{result.media_summary}</p>
      ) : null}
      {result.transcript_excerpt ? (
        <p className="mt-2 text-sm leading-6 text-muted">
          <span className="font-semibold text-ink">Transcript excerpt:</span> {result.transcript_excerpt}
        </p>
      ) : null}
      {result.caption_drafts.length > 0 ? (
        <div className="mt-4">
          <div className="text-xs font-bold uppercase tracking-wide text-muted">Caption drafts from Gemini</div>
          <ul className="mt-2 space-y-2">
            {result.caption_drafts.map((draft, i) => (
              <li key={i} className="rounded-md border border-line bg-paper px-3 py-2 text-sm leading-6 text-ink">
                {draft}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function MethodologyNote({ note }: { note: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-md border border-line bg-white/95 p-5 shadow-board">
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

function TopCallout({ ranking }: { ranking?: Ranking }) {
  if (!ranking) return null;
  return (
    <section className="rounded-md border border-accent/25 bg-[linear-gradient(135deg,rgba(241,90,33,0.08),rgba(255,255,255,0.98))] p-5 shadow-board">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-accent px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">
          Best current fit
        </span>
        <ConfidenceBadge confidence={ranking.confidence} />
      </div>
      <h2 className="mt-3 text-2xl font-black text-ink">{ranking.platform}</h2>
      <p className="mt-2 max-w-4xl text-sm leading-6 text-ink">{ranking.why}</p>
    </section>
  );
}

function RankingBoard({
  rankings,
  onOpenBreakdown,
  onOpenReport
}: {
  rankings: Ranking[];
  onOpenBreakdown: (ranking: Ranking) => void;
  onOpenReport: (ranking: Ranking) => void;
}) {
  return (
    <section className="space-y-3" aria-label="Platform ranking board">
      {rankings.map((ranking) => (
        <RankingCard
          key={`${ranking.rank}-${ranking.platform}`}
          ranking={ranking}
          onOpenBreakdown={onOpenBreakdown}
          onOpenReport={onOpenReport}
        />
      ))}
    </section>
  );
}

function RankingCard({
  ranking,
  onOpenBreakdown,
  onOpenReport
}: {
  ranking: Ranking;
  onOpenBreakdown: (ranking: Ranking) => void;
  onOpenReport: (ranking: Ranking) => void;
}) {
  const lowFit = ranking.fit_score < 55;
  const bestPattern = ranking.supporting_patterns?.[0];

  return (
    <article
      className={`rounded-md border bg-white/95 p-5 shadow-board transition duration-200 hover:-translate-y-0.5 hover:border-accent/35 ${
        lowFit ? "border-low/40 opacity-80" : "border-line"
      }`}
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_180px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-ink px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white">
              Rank {ranking.rank}
            </span>
            <h2 className="text-xl font-bold leading-tight text-ink">{ranking.platform}</h2>
            <ConfidenceBadge confidence={ranking.confidence} />
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-ink">{ranking.why}</p>
          {bestPattern ? (
            <p className="mt-3 text-sm leading-6 text-muted">
              <span className="font-semibold text-ink">Strongest pattern:</span> {bestPattern}
            </p>
          ) : null}
        </div>
        <div className="rounded-md border border-line bg-paper p-4 text-center shadow-sm">
          <div className={`text-5xl font-black leading-none ${lowFit ? "text-low" : "text-accent"}`}>
            {ranking.fit_score}
          </div>
          <div className="mt-1 text-xs font-semibold uppercase text-muted">fit score</div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-bold text-ink transition hover:border-accent hover:text-accent"
          onClick={() => onOpenBreakdown(ranking)}
        >
          Score breakdown
        </button>
        <button
          type="button"
          className="rounded-md bg-ink px-4 py-2 text-sm font-bold text-white transition hover:bg-ink/90"
          onClick={() => onOpenReport(ranking)}
        >
          Deep report
        </button>
      </div>
    </article>
  );
}

function InsightRail({ rankings }: { rankings: Ranking[] }) {
  return (
    <section className="rounded-md border border-line bg-white/95 p-5 shadow-board">
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-accent" aria-hidden="true" />
        <h2 className="text-lg font-bold text-ink">Platform signals</h2>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {rankings.slice(0, 3).map((ranking) => (
          <div key={ranking.platform} className="rounded-md border border-line bg-paper p-4">
            <div className="text-sm font-bold text-ink">{ranking.platform}</div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted">
              Rank {ranking.rank} • Score {ranking.fit_score}
            </div>
            <p className="mt-3 text-sm leading-6 text-muted">
              {ranking.supporting_patterns?.[1] ?? ranking.why}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function PlatformModal({
  view,
  ranking,
  report,
  loading,
  captionDrafts,
  onClose,
  onRetryReport,
}: {
  view: ModalView;
  ranking: Ranking;
  report: PlatformReportResponse | null;
  loading: boolean;
  captionDrafts: string[];
  onClose: () => void;
  onRetryReport: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 px-4 py-6" role="dialog" aria-modal="true">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-md border border-line bg-white shadow-board">
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-line bg-white/95 px-5 py-4 backdrop-blur">
          <div>
            <div className="text-xs font-black uppercase tracking-wide text-accent">
              {view === "breakdown" ? "Score breakdown" : "Deep report"}
            </div>
            <h2 className="mt-1 text-2xl font-black text-ink">{ranking.platform}</h2>
            <p className="mt-1 text-sm text-muted">{ranking.why}</p>
          </div>
          <button
            type="button"
            className="rounded-md border border-line p-2 text-muted transition hover:text-ink"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <XIcon size={18} />
          </button>
        </div>

        <div className="space-y-5 p-5">
          {view === "breakdown" ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                {(ranking.score_breakdown ?? []).map((item) => (
                  <div key={item.label} className="rounded-md border border-line bg-paper p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-bold text-ink">{item.label}</div>
                      <div className="text-lg font-black text-accent">{Math.round(item.score * 100)}</div>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted">{item.reason}</p>
                  </div>
                ))}
              </div>
              <div className="rounded-md border border-line bg-white p-4">
                <h3 className="text-sm font-bold uppercase tracking-wide text-ink">Supporting patterns</h3>
                <div className="mt-3 space-y-2">
                  {(ranking.supporting_patterns ?? []).map((pattern) => (
                    <p key={pattern} className="text-sm leading-6 text-muted">
                      {pattern}
                    </p>
                  ))}
                </div>
              </div>
              {captionDrafts.length > 0 ? (
                <div className="rounded-md border border-line bg-white p-4">
                  <h3 className="text-sm font-bold uppercase tracking-wide text-ink">
                    Caption drafts from media analysis
                  </h3>
                  <div className="mt-3 space-y-2">
                    {captionDrafts.map((draft, i) => (
                      <p key={i} className="rounded-md border border-line bg-paper px-3 py-2 text-sm leading-6 text-ink">
                        {draft}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
              <EvidenceDisclosure evidence={ranking.top_evidence} />
            </>
          ) : (
            <>
              {loading ? (
                <div className="flex items-center gap-3 rounded-md border border-line bg-paper p-4 text-sm text-muted">
                  <Loader2 size={18} className="animate-spin" />
                  Generating grounded platform report from matched Stars of Science records...
                </div>
              ) : report ? (
                <>
                  <div className="rounded-md border border-line bg-paper p-4">
                    <div className="text-xs font-bold uppercase tracking-wide text-muted">
                      Detailed analysis
                    </div>
                    <p className="mt-2 text-sm leading-7 text-ink">{report.analysis}</p>
                  </div>
                  {report.media_summary ? (
                    <div className="rounded-md border border-line bg-paper p-4">
                      <div className="text-xs font-bold uppercase tracking-wide text-muted">
                        From uploaded media
                      </div>
                      <p className="mt-2 text-sm leading-6 text-ink">{report.media_summary}</p>
                    </div>
                  ) : null}
                  <ReportList title="Strengths" items={report.strengths} />
                  <ReportList title="Risks" items={report.risks} />
                  <ReportList title="Recommendations" items={report.recommendations} />
                  <EvidenceDisclosure evidence={report.evidence} />
                </>
              ) : (
                <div className="space-y-3">
                  <ErrorBlock message="The deep report could not be generated right now." />
                  <button
                    type="button"
                    className="rounded-md border border-line bg-white px-4 py-2 text-sm font-bold text-ink transition hover:border-accent hover:text-accent"
                    onClick={onRetryReport}
                  >
                    Try again
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <h3 className="text-sm font-bold uppercase tracking-wide text-ink">{title}</h3>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <p key={item} className="text-sm leading-6 text-muted">
            {item}
          </p>
        ))}
      </div>
    </section>
  );
}
