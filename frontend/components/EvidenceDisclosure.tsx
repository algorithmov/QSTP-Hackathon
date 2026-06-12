"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { EvidenceItem } from "@/types/route";

export function EvidenceDisclosure({ evidence }: { evidence: EvidenceItem[] }) {
  const [open, setOpen] = useState(false);
  const count = evidence.length;

  return (
    <div className="mt-4">
      <button
        type="button"
        className="flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:border-accent/60"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        Evidence
        <span className="text-muted">({count})</span>
        <ChevronDown
          size={16}
          className={open ? "rotate-180 transition" : "transition"}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div className="mt-3 rounded-md border border-line bg-paper p-4 shadow-sm">
          {count > 0 ? (
            <ul className="space-y-3">
              {evidence.map((item, index) => (
                <li key={`${item.source}-${index}`} className="text-sm leading-6 text-ink">
                  <p>{item.claim}</p>
                  <p className="mt-1 text-xs font-semibold text-muted">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-accent hover:underline"
                      >
                        {item.source}
                        <ExternalLink size={13} aria-hidden="true" />
                      </a>
                    ) : (
                      item.source
                    )}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No cited evidence returned for this route.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
