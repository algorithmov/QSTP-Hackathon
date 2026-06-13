"use client";

import { Check, Clock, Copy, Layers3, MapPin, X as XIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EvidenceDisclosure } from "@/components/EvidenceDisclosure";
import { GoalSelector } from "@/components/GoalSelector";
import { IdeaSummaryCard } from "@/components/IdeaSummaryCard";
import { ErrorBlock, LoadingBlock } from "@/components/StatusBlock";
import { personalizeIdea } from "@/lib/api";
import { usePersistentState } from "@/lib/usePersistentState";
import {
  supportedCountries,
  supportedPlatforms,
  type CountryCode,
  type Goal,
  type PersonalizeResponse,
  type PersonalizedReport,
  type Platform
} from "@/types/route";

const starterText =
  "A 30-second clip idea: a Sudanese student demos a low-cost water purification filter she built from local materials.";

type Status = "idle" | "loading" | "success" | "error";

const loadingSteps = [
  "Understanding idea...",
  "Searching live evidence...",
  "Localizing formats...",
  "Writing captions...",
  "Finalizing delivery plan..."
];

function normalizeGoal(value: Goal | string): Goal {
  return value === "viewers" || value === "sponsors" ? value : "applications";
}

export default function PersonalizePage() {
  const [ideaText, setIdeaText] = usePersistentState("masar.personalize.ideaText", starterText);
  const [goal, setGoal] = usePersistentState<Goal>(
    "masar.personalize.goal",
    "applications",
    normalizeGoal,
  );
  const [countries, setCountries] = usePersistentState<CountryCode[]>(
    "masar.personalize.countries",
    ["EG", "SA"]
  );
  const [platforms, setPlatforms] = usePersistentState<Platform[]>(
    "masar.personalize.platforms",
    ["TikTok", "Instagram"]
  );
  const [status, setStatus] = useState<Status>("idle");
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = usePersistentState<PersonalizeResponse | null>(
    "masar.personalize.result",
    null
  );

  const canSubmit =
    ideaText.trim().length > 0 &&
    countries.length > 0 &&
    platforms.length > 0 &&
    status !== "loading";

  async function handleSubmit() {
    if (!canSubmit) return;
    setStatus("loading");
    setLoadingStep(0);
    setError(null);
    const timer = window.setInterval(() => {
      setLoadingStep((step) => Math.min(step + 1, loadingSteps.length - 1));
    }, 2200);
    try {
      const response = await personalizeIdea({
        idea_text: ideaText.trim(),
        goal,
        countries,
        platforms
      });
      setResult(response);
      setStatus("success");
    } catch {
      setError("Delivery plan generation failed. Check the backend connection or mock file and try again.");
      setStatus("error");
    } finally {
      window.clearInterval(timer);
    }
  }

  return (
    <AppShell>
      <section className="rounded-xl border-2 border-accent/30 bg-[linear-gradient(180deg,rgba(255,255,255,0.99),rgba(246,242,238,0.98))] p-6 shadow-board ring-1 ring-white/70">
        <SectionBanner
          step="01"
          title="Build The Audience Brief"
          description="Define the input idea, target goal, countries, and platforms before generating localized plans."
        />
        <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
          <label className="block">
            <span className="text-sm font-semibold text-ink">Idea or post text</span>
            <textarea
              className="mt-2 min-h-44 w-full resize-y rounded-md border border-line/90 bg-[linear-gradient(180deg,#ffffff,rgba(245,243,243,0.65))] px-4 py-3 text-base leading-7 text-ink outline-none transition duration-200 focus:border-accent focus:shadow-[0_0_0_4px_rgba(14,124,102,0.12)] disabled:bg-slate-50"
              value={ideaText}
              disabled={status === "loading"}
              onChange={(event) => setIdeaText(event.target.value)}
              placeholder="Paste a campaign idea, caption, or post concept."
            />
            <span className="mt-2 block text-xs font-semibold text-muted">
              {ideaText.length} characters
            </span>
          </label>
          <div className="space-y-4">
            <div className="rounded-xl border border-line/90 bg-white/88 p-4 shadow-sm">
              <span className="text-sm font-semibold text-ink">Goal</span>
              <div className="mt-2">
                <GoalSelector value={goal} disabled={status === "loading"} onChange={setGoal} />
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">
                Target an audience with delivery plans grounded in matched Stars of Science content plus local country timing and platform context.
              </p>
            </div>
            <div className="rounded-xl border border-line/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(247,243,239,0.92))] p-4 shadow-sm">
              <SelectionGroup
                label="Countries"
                helper="Choose up to 3 countries."
                options={supportedCountries.map((country) => ({
                  label: country.name,
                  value: country.code
                }))}
                values={countries}
                limit={3}
                disabled={status === "loading"}
                onChange={setCountries}
              />
            </div>
            <div className="rounded-xl border border-line/90 bg-[linear-gradient(180deg,rgba(245,248,249,0.95),rgba(255,255,255,0.96))] p-4 shadow-sm">
              <SelectionGroup
                label="Platforms"
                helper="Choose up to 2 platforms."
                options={supportedPlatforms.map((platform) => ({ label: platform, value: platform }))}
                values={platforms}
                limit={2}
                disabled={status === "loading"}
                onChange={setPlatforms}
              />
            </div>
            <button
              type="button"
              disabled={!canSubmit}
              className="w-full rounded-md border border-accent bg-accent px-6 py-3 text-sm font-bold text-white shadow-[0_16px_30px_rgba(241,90,33,0.2)] transition duration-200 hover:-translate-y-0.5 hover:bg-accent/90 disabled:translate-y-0 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300 disabled:text-slate-600 disabled:shadow-none"
              onClick={handleSubmit}
            >
              {status === "loading" ? "Generating..." : "Generate audience plan"}
            </button>
          </div>
        </div>
      </section>

      <div className="h-3" aria-hidden="true" />
      {status === "loading" ? <LoadingBlock label={loadingSteps[loadingStep]} /> : null}
      {status === "error" && error ? <ErrorBlock message={error} /> : null}

      {result ? (
        <>
          <section className="mt-5 rounded-xl border-2 border-ink/12 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,247,244,0.97))] p-6 shadow-board">
            <SectionBanner
              step="02"
              title="Review The Extracted Summary"
              description="Inspect the normalized topic, audience, content type, and key themes before using the generated delivery routes."
            />
            <IdeaSummaryCard summary={result.idea_summary} />
          </section>
          <section className="mt-7 rounded-xl border-2 border-ink/12 bg-[linear-gradient(180deg,rgba(244,240,235,0.96),rgba(255,255,255,0.98))] p-6 shadow-board">
            <SectionBanner
              step="03"
              title="Compare Country Delivery Routes"
              description="Each country is isolated into its own planning block so the generated routes are easy to distinguish and review."
            />
            <ReportGrid reports={result.reports} />
          </section>
        </>
      ) : (
        <section className="mt-5 rounded-xl border-2 border-dashed border-line/90 bg-white/95 p-8 text-muted shadow-board ring-1 ring-white/70">
          Audience delivery reports will appear here after you choose countries and platforms.
        </section>
      )}
    </AppShell>
  );
}

type SelectionGroupProps<T extends string> = {
  label: string;
  helper: string;
  options: Array<{ label: string; value: T }>;
  values: T[];
  limit: number;
  disabled: boolean;
  onChange: (values: T[]) => void;
};

function SelectionGroup<T extends string>({
  label,
  helper,
  options,
  values,
  limit,
  disabled,
  onChange
}: SelectionGroupProps<T>) {
  function toggle(value: T) {
    if (values.includes(value)) {
      onChange(values.filter((item) => item !== value));
      return;
    }
    if (values.length >= limit) return;
    onChange([...values, value]);
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-ink">{label}</span>
        <span className="text-xs font-semibold text-muted">
          {values.length}/{limit}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">{helper}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {options.map((option) => {
          const active = values.includes(option.value);
          const limitReached = values.length >= limit && !active;
          return (
            <button
              key={option.value}
              type="button"
              disabled={disabled || limitReached}
              className={`min-h-12 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                active
                  ? "border-accent bg-accent text-white shadow-sm"
                  : "border-line/90 bg-white text-ink hover:-translate-y-0.5 hover:border-accent/60"
              } disabled:cursor-not-allowed disabled:opacity-50`}
              onClick={() => toggle(option.value)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SectionBanner({
  step,
  title,
  description
}: {
  step: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-6 flex items-start gap-4 border-b border-line/80 pb-5">
      <div className="rounded-lg border border-accent/35 bg-accent px-3 py-2 text-sm font-black tracking-[0.18em] text-white">
        {step}
      </div>
      <div>
        <div className="text-xs font-black uppercase tracking-[0.18em] text-accent">Section</div>
        <h2 className="mt-1 text-2xl font-black text-ink">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">{description}</p>
      </div>
    </div>
  );
}

function ReportGrid({ reports }: { reports: PersonalizedReport[] }) {
  const grouped = useMemo(() => {
    const map = new Map<string, PersonalizedReport[]>();
    for (const report of reports) {
      const key = report.country_name;
      map.set(key, [...(map.get(key) ?? []), report]);
    }
    return Array.from(map.entries());
  }, [reports]);

  return (
    <section className="space-y-8" aria-label="Delivery reports">
      {grouped.map(([countryName, countryReports]) => (
        <section
          key={countryName}
          className="rounded-xl border-2 border-line/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,243,239,0.95))] p-5 shadow-board ring-1 ring-white/70"
        >
          <div className="mb-5 flex items-center justify-between gap-3 border-b-2 border-line/80 pb-5">
            <div className="flex items-center gap-3">
              <span className="rounded-xl border border-accent/25 bg-accent/10 p-2.5 text-accent">
                <Layers3 size={16} aria-hidden="true" />
              </span>
              <div>
                <div className="text-xs font-black uppercase tracking-[0.16em] text-accent">Country plan</div>
                <h2 className="mt-1 text-2xl font-black text-ink">{countryName}</h2>
              </div>
            </div>
            <div className="rounded-md border border-line/80 bg-white/85 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted">
              {countryReports.length} route{countryReports.length === 1 ? "" : "s"}
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {countryReports.map((report) => (
              <ReportCard
                key={`${report.country}-${report.platform}-${report.language}`}
                report={report}
              />
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}

function ReportCard({ report }: { report: PersonalizedReport }) {
  const [copied, setCopied] = useState(false);
  const rtl = report.language_direction === "rtl";

  async function copyCaption() {
    try {
      await navigator.clipboard.writeText(report.caption);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="rounded-xl border border-line/90 bg-white/98 p-5 shadow-[0_16px_38px_rgba(15,23,42,0.08)] transition duration-200 hover:-translate-y-0.5 hover:border-accent/35">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.16em] text-accent">{report.platform}</div>
          <h3 className="mt-1 text-xl font-bold text-ink">{report.language}</h3>
        </div>
        <ConfidenceBadge confidence={report.confidence} />
      </div>

      <p className="mt-4 rounded-md border border-line/90 bg-paper/75 p-3 text-sm leading-6 text-ink">
        <span className="font-semibold">Format:</span> {report.recommended_format}
      </p>

      <div className="mt-4 rounded-md border border-accent/20 bg-accent/5 p-4">
        <div className="text-xs font-bold uppercase tracking-wide text-accent">Hook</div>
        <p className="mt-2 text-sm font-semibold leading-6 text-ink">{report.hook}</p>
      </div>

      <div className="mt-4 rounded-md border border-line/90 bg-paper/75 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs font-bold uppercase tracking-wide text-muted">Caption</div>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-bold text-ink hover:border-accent/60"
            onClick={copyCaption}
          >
            {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p
          dir={report.language_direction}
          className={`mt-3 whitespace-pre-wrap text-base leading-8 text-ink ${rtl ? "text-right" : "text-left"}`}
        >
          {report.caption}
        </p>
        <div
          dir={report.language_direction}
          className={`mt-3 flex flex-wrap gap-2 ${rtl ? "justify-end text-right" : ""}`}
        >
          {report.hashtags.map((tag) => (
            <span
              key={tag}
              className="rounded-md border border-line/90 bg-white px-2.5 py-1 text-xs font-semibold text-ink"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-sm text-muted">
        <span className="flex items-center gap-1.5">
          <Clock size={15} aria-hidden="true" />
          {report.post_time_local}
        </span>
        <span className="flex items-center gap-1.5">
          <MapPin size={15} aria-hidden="true" />
          {report.timezone}
        </span>
      </div>

      <div className="mt-4 rounded-md border border-line/90 bg-paper/75 p-4">
        <div className="text-xs font-bold uppercase tracking-wide text-muted">Timing</div>
        <p className="mt-2 text-sm font-semibold leading-6 text-ink">{report.recommended_day_window}</p>
        <p className="mt-2 text-sm leading-6 text-muted">{report.timing_rationale}</p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <GuidanceList title="Do" items={report.dos} icon="check" />
        <GuidanceList title="Do not" items={report.donts} icon="x" />
      </div>

      <p className="mt-4 text-sm leading-6 text-ink">{report.why}</p>
      <EvidenceDisclosure evidence={report.evidence} />
    </article>
  );
}

function GuidanceList({ title, items, icon }: { title: string; items: string[]; icon: "check" | "x" }) {
  return (
    <div className="rounded-md border border-line/90 bg-white p-3">
      <div className="text-xs font-bold uppercase tracking-wide text-muted">{title}</div>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm leading-6 text-ink">
            <span className="mt-1 shrink-0 text-accent">
              {icon === "check" ? <Check size={15} aria-hidden="true" /> : <XIcon size={15} aria-hidden="true" />}
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
