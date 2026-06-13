"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { EvidenceItem } from "@/types/route";

function formatMetric(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const hasMetrics = item.metrics && Object.values(item.metrics).some((v) => v > 0);
  const isStarsPost = item.evidence_type === "stars_post";

  return (
    <li className="rounded-md border border-line bg-white p-3 text-sm">
      <p className="leading-6 text-ink">{item.claim}</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <span className="font-semibold text-muted">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              {item.source}
              <ExternalLink size={12} aria-hidden="true" />
            </a>
          ) : (
            item.source
          )}
        </span>
        {item.published_at ? (
          <span className="text-xs text-muted">{item.published_at}</span>
        ) : null}
        {item.platform && isStarsPost ? (
          <span className="rounded bg-accent/10 px-1.5 py-0.5 text-xs font-bold text-accent">
            {item.platform}
          </span>
        ) : null}
        {item.relevance_score != null ? (
          <span className="text-xs text-muted">
            match {Math.round(item.relevance_score * 100)}%
          </span>
        ) : null}
      </div>
      {hasMetrics ? (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
          {item.metrics!.views > 0 && (
            <span>{formatMetric(item.metrics!.views)} views</span>
          )}
          {item.metrics!.likes > 0 && (
            <span>{formatMetric(item.metrics!.likes)} likes</span>
          )}
          {item.metrics!.shares > 0 && (
            <span>{formatMetric(item.metrics!.shares)} shares</span>
          )}
          {item.metrics!.comments > 0 && (
            <span>{formatMetric(item.metrics!.comments)} comments</span>
          )}
        </div>
      ) : null}
    </li>
  );
}

export function EvidenceDisclosure({ evidence }: { evidence: EvidenceItem[] | undefined }) {
  const [open, setOpen] = useState(false);
  const items = evidence ?? [];
  const count = items.length;

  return (
    <div className="mt-4">
      <button
        type="button"
        className="flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:border-accent/60"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        Stars of Science evidence
        <span className="text-muted">({count})</span>
        <ChevronDown
          size={16}
          className={open ? "rotate-180 transition" : "transition"}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div className="mt-3">
          {count > 0 ? (
            <ul className="space-y-2">
              {items.map((item, index) => (
                <EvidenceRow key={`${item.source}-${index}`} item={item} />
              ))}
            </ul>
          ) : (
            <p className="rounded-md border border-line bg-paper px-4 py-3 text-sm text-muted">
              No cited evidence returned for this route.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
