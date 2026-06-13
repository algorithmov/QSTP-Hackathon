"use client";

import { FileImage, FileText, FileVideo, Loader2, X as XIcon } from "lucide-react";
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
  extracting: "Extracting media context...",
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
  const [goal, setGoal] = usePersistentState<Goal>("masar.review.goal", "applications", normalizeGoal);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = usePersistentState<ReviewResponse | null>("masar.review.result.v4", null);
  const [activeRanking, setActiveRanking] = useState<Ranking | null>(null);
  const [modalView, setModalView] = useState<ModalView>("breakdown");
  const [report, setReport] = useState<PlatformReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [mediaFiles, setMediaFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    const valid = Array.from(incoming).filter(
      (f) => ["image/", "video/", "audio/"].some((p) => f.type.startsWith(p)) && f.size <= 18 * 1024 * 1024
    );
    setMediaFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      return [...prev, ...valid.filter((f) => !existing.has(f.name))];
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
      // modal shows retry state
    } finally {
      setReportLoading(false);
    }
  }

  return (
    <AppShell>
      {/* Input */}
      <section className="rounded-lg border border-line bg-white p-6 shadow-board">
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <label className="block">
            <span className="text-sm font-semibold text-ink">Idea or post text</span>
            <textarea
              className="mt-2 min-h-36 w-full resize-y rounded-md border border-line bg-paper/40 px-4 py-3 text-base leading-7 text-ink outline-none transition focus:border-accent focus:bg-white focus:shadow-[0_0_0_3px_rgba(14,124,102,0.10)] disabled:opacity-60"
              value={ideaText}
              disabled={isLoading}
              onChange={(e) => setIdeaText(e.target.value)}
              placeholder="Paste a Stars of Science campaign idea, caption, or post concept."
            />
            <span className="mt-1.5 block text-xs text-muted">{ideaText.length} characters</span>
          </label>

          <div className="flex flex-col gap-4">
            <div>
              <span className="text-sm font-semibold text-ink">Goal</span>
              <div className="mt-2">
                <GoalSelector value={goal} disabled={isLoading} onChange={setGoal} />
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">
                Scores each of the five Stars of Science platforms using matched post evidence.
              </p>
            </div>
            <button
              type="button"
              disabled={!canSubmit}
              className="rounded-md bg-accent px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-px hover:bg-accent/90 disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
              onClick={handleSubmit}
            >
              {isLoading ? LOADING_STEPS[status] || "Reviewing…" : "Review for Stars of Science"}
            </button>
          </div>
        </div>

        {/* Media upload */}
        <div className="mt-5 border-t border-line pt-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ink">
              Media{" "}
              <span className="text-xs font-normal text-muted">— optional image, video, or audio</span>
            </span>
            <button
              type="button"
              disabled={isLoading}
              className="rounded-md border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
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
            <ul className="mt-3 space-y-1.5">
              {mediaFiles.map((file) => (
                <li key={file.name} className="flex items-center gap-2 rounded border border-line bg-paper/60 px-3 py-2 text-xs">
                  {mediaIcon(file.type)}
                  <span className="flex-1 truncate text-ink">{file.name}</span>
                  <span className="text-muted">{formatBytes(file.size)}</span>
                  <button type="button" disabled={isLoading} className="text-muted hover:text-ink" onClick={() => removeFile(file.name)} aria-label={`Remove ${file.name}`}>
                    <XIcon size={12} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-muted">
              Gemini extracts content type, language, and caption drafts from uploaded media.
            </p>
          )}
        </div>
      </section>

      {/* Status */}
      {isLoading && <LoadingBlock label={LOADING_STEPS[status] || "Reviewing…"} />}
      {status === "error" && error && <ErrorBlock message={error} />}

      {/* Results */}
      {result ? (
        <>
          {/* Idea summary — separated from input by AppShell gap-8 */}
          <IdeaSummaryCard summary={result.idea_summary} />

          {result.media_context_used && <MediaAnalysisCard result={result} />}

          {/* Extra visual separator before rankings */}
          <div className="border-t border-line/60" aria-hidden="true" />

          <RankingBoard
            rankings={result.rankings}
            onOpenBreakdown={openBreakdown}
            onOpenReport={openReport}
          />

          <MethodologyNote note={result.methodology_note} />
        </>
      ) : (
        !isLoading && (
          <section className="rounded-lg border border-line bg-white px-6 py-12 text-center text-sm text-muted shadow-board">
            Submit an idea above to see platform rankings.
          </section>
        )
      )}

      {/* Modal */}
      {activeRanking && (
        <PlatformModal
          view={modalView}
          ranking={activeRanking}
          report={report}
          loading={reportLoading}
          captionDrafts={result?.caption_drafts ?? []}
          onClose={() => { setActiveRanking(null); setReport(null); setReportLoading(false); }}
          onRetryReport={() => openReport(activeRanking)}
        />
      )}
    </AppShell>
  );
}

function MediaAnalysisCard({ result }: { result: ReviewResponse }) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-board">
      <div className="flex items-center gap-2">
        <span className="rounded bg-ink/8 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-ink">
          Media analysed
        </span>
        <span className="text-xs text-muted">{result.media_assets.length} file{result.media_assets.length !== 1 ? "s" : ""}</span>
      </div>
      {result.media_summary && <p className="mt-3 text-sm leading-6 text-ink">{result.media_summary}</p>}
      {result.transcript_excerpt && (
        <p className="mt-2 text-sm leading-6 text-muted">
          <span className="font-semibold text-ink">Transcript: </span>{result.transcript_excerpt}
        </p>
      )}
      {result.caption_drafts.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Caption drafts</div>
          <ul className="mt-2 space-y-2">
            {result.caption_drafts.map((draft, i) => (
              <li key={i} className="rounded border border-line bg-paper/60 px-3 py-2 text-sm leading-6 text-ink">{draft}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}


function RankingBoard({
  rankings,
  onOpenBreakdown,
  onOpenReport,
}: {
  rankings: Ranking[];
  onOpenBreakdown: (r: Ranking) => void;
  onOpenReport: (r: Ranking) => void;
}) {
  return (
    <section aria-label="Platform rankings">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted">Platform rankings</h2>
        <span className="text-xs text-muted">{rankings.length} platforms</span>
      </div>
      <div className="space-y-4">
        {rankings.map((ranking) => (
          <RankingCard
            key={ranking.platform}
            ranking={ranking}
            onOpenBreakdown={onOpenBreakdown}
            onOpenReport={onOpenReport}
          />
        ))}
      </div>
    </section>
  );
}

function RankingCard({
  ranking,
  onOpenBreakdown,
  onOpenReport,
}: {
  ranking: Ranking;
  onOpenBreakdown: (r: Ranking) => void;
  onOpenReport: (r: Ranking) => void;
}) {
  const isBest = ranking.rank === 1;
  const lowFit = ranking.fit_score < 55;

  return (
    <article className={`rounded-lg border bg-white shadow-board transition hover:-translate-y-px ${
      isBest ? "border-accent/30 bg-accent/[0.03]" : lowFit ? "border-line opacity-70" : "border-line hover:border-line/60"
    }`}>
      <div className="p-6">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded px-2 py-0.5 text-xs font-bold text-white ${isBest ? "bg-accent" : "bg-ink"}`}>
                #{ranking.rank}
              </span>
              {isBest && (
                <span className="rounded border border-accent/30 bg-accent/10 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-accent">
                  Best fit
                </span>
              )}
              <h3 className="text-lg font-bold text-ink">{ranking.platform}</h3>
              <ConfidenceBadge confidence={ranking.confidence} />
            </div>
            <p className="mt-3 text-sm leading-6 text-muted">{ranking.why}</p>
          </div>
          <div className="shrink-0 text-right">
            <div className={`text-5xl font-black leading-none ${isBest ? "text-accent" : lowFit ? "text-muted" : "text-ink/70"}`}>
              {ranking.fit_score}
            </div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted">score</div>
          </div>
        </div>
      </div>

      <div className="flex gap-2 border-t border-line px-6 py-3">
        <button
          type="button"
          className="rounded border border-line bg-white px-4 py-2 text-xs font-semibold text-ink transition hover:border-accent hover:text-accent"
          onClick={() => onOpenBreakdown(ranking)}
        >
          Score breakdown
        </button>
        <button
          type="button"
          className="rounded bg-ink px-4 py-2 text-xs font-semibold text-white transition hover:bg-ink/85"
          onClick={() => onOpenReport(ranking)}
        >
          Deep report
        </button>
      </div>
    </article>
  );
}

function MethodologyNote({ note }: { note: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-board">
      <button
        type="button"
        className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted transition hover:text-ink"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>Methodology</span>
        <span className="text-base leading-none">{open ? "−" : "+"}</span>
      </button>
      {open && <p className="mt-3 text-sm leading-6 text-muted">{note}</p>}
    </section>
  );
}

function PlatformModal({
  view, ranking, report, loading, captionDrafts, onClose, onRetryReport,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4 py-6" role="dialog" aria-modal="true">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-line bg-white shadow-board">
        {/* Header */}
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-line bg-white px-5 py-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">
              {view === "breakdown" ? "Score breakdown" : "Deep report"}
            </div>
            <h2 className="mt-0.5 text-xl font-black text-ink">{ranking.platform}</h2>
          </div>
          <button
            type="button"
            className="rounded border border-line p-1.5 text-muted transition hover:text-ink"
            onClick={onClose}
            aria-label="Close"
          >
            <XIcon size={16} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {view === "breakdown" ? (
            <>
              {/* Score items */}
              <div className="grid gap-3 sm:grid-cols-2">
                {(ranking.score_breakdown ?? []).map((item) => (
                  <div key={item.label} className="rounded-md border border-line bg-paper/60 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-ink">{item.label}</span>
                      <span className="text-lg font-black text-accent">{Math.round(item.score * 100)}</span>
                    </div>
                    <p className="mt-1.5 text-xs leading-5 text-muted">{item.reason}</p>
                  </div>
                ))}
              </div>

              {/* Patterns */}
              {(ranking.supporting_patterns ?? []).length > 0 && (
                <div className="rounded-md border border-line bg-white p-4">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-muted">Supporting patterns</h3>
                  <ul className="mt-3 space-y-2">
                    {(ranking.supporting_patterns ?? []).map((p) => (
                      <li key={p} className="text-sm leading-6 text-ink">— {p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Caption drafts if media was used */}
              {captionDrafts.length > 0 && (
                <div className="rounded-md border border-line bg-white p-4">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-muted">Caption drafts from media</h3>
                  <ul className="mt-3 space-y-2">
                    {captionDrafts.map((draft, i) => (
                      <li key={i} className="rounded border border-line bg-paper/60 px-3 py-2 text-sm leading-6 text-ink">{draft}</li>
                    ))}
                  </ul>
                </div>
              )}

              <EvidenceDisclosure evidence={ranking.top_evidence} />
            </>
          ) : (
            <>
              {loading ? (
                <div className="flex items-center gap-3 rounded-md border border-line bg-paper/60 p-4 text-sm text-muted">
                  <Loader2 size={16} className="animate-spin" />
                  Generating report from Stars of Science records…
                </div>
              ) : report ? (
                <>
                  <div className="rounded-md border border-line bg-paper/60 p-4">
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted">Analysis</div>
                    <p className="mt-2 text-sm leading-7 text-ink">{report.analysis}</p>
                  </div>
                  {report.media_summary && (
                    <div className="rounded-md border border-line bg-paper/60 p-4">
                      <div className="text-xs font-semibold uppercase tracking-wide text-muted">From uploaded media</div>
                      <p className="mt-2 text-sm leading-6 text-ink">{report.media_summary}</p>
                    </div>
                  )}
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
                    className="rounded border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:border-accent hover:text-accent"
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
  if (!items?.length) return null;
  return (
    <div className="rounded-md border border-line bg-white p-4">
      <h3 className="text-xs font-bold uppercase tracking-wide text-muted">{title}</h3>
      <ul className="mt-3 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="text-sm leading-6 text-ink">— {item}</li>
        ))}
      </ul>
    </div>
  );
}
