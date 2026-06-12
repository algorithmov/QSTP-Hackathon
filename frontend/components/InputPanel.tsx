"use client";

import { Upload } from "lucide-react";
import type { Goal, RouteRequest } from "@/types/route";

const goals: Array<{ label: string; value: Goal }> = [
  { label: "Applications", value: "applications" },
  { label: "Viewers", value: "viewers" },
  { label: "Sponsors", value: "sponsors" },
  { label: "Buzz", value: "buzz" }
];

type InputPanelProps = {
  contentText: string;
  goal: Goal | null;
  topicHint: string;
  mediaFileName: string | null;
  isLoading: boolean;
  onContentTextChange: (value: string) => void;
  onGoalChange: (value: Goal) => void;
  onTopicHintChange: (value: string) => void;
  onMediaChange: (fileName: string | null) => void;
  onSubmit: (payload: RouteRequest) => void;
};

export function InputPanel({
  contentText,
  goal,
  topicHint,
  mediaFileName,
  isLoading,
  onContentTextChange,
  onGoalChange,
  onTopicHintChange,
  onMediaChange,
  onSubmit
}: InputPanelProps) {
  const canSubmit = contentText.trim().length > 0 && goal !== null && !isLoading;

  return (
    <form
      className="rounded-md border border-line bg-white p-5 shadow-board"
      onSubmit={(event) => {
        event.preventDefault();
        if (!canSubmit || goal === null) return;
        onSubmit({
          content_text: contentText.trim(),
          media_url: mediaFileName ? `uploads/${mediaFileName}` : null,
          goal,
          topic_hint: topicHint.trim() || null
        });
      }}
    >
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <label className="block">
          <span className="text-sm font-semibold text-ink">Content text</span>
          <textarea
            className="mt-2 min-h-36 w-full resize-y rounded-md border border-line bg-white px-4 py-3 text-base leading-7 text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:bg-slate-50"
            value={contentText}
            disabled={isLoading}
            onChange={(event) => onContentTextChange(event.target.value)}
            placeholder="A 30-second clip of a Jordanian student showing her water-purification prototype."
          />
        </label>

        <div className="grid gap-4">
          <label className="block">
            <span className="text-sm font-semibold text-ink">Topic hint</span>
            <input
              className="mt-2 w-full rounded-md border border-line bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:bg-slate-50"
              value={topicHint}
              disabled={isLoading}
              onChange={(event) => onTopicHintChange(event.target.value)}
              placeholder="young inventors water tech"
            />
          </label>

          <label className="flex min-h-24 cursor-pointer flex-col justify-center rounded-md border border-dashed border-line bg-paper px-4 py-3 text-sm text-muted transition hover:border-accent/60">
            <span className="flex items-center gap-2 font-semibold text-ink">
              <Upload size={17} aria-hidden="true" />
              Optional image or video
            </span>
            <span className="mt-1 truncate">{mediaFileName ?? "No file selected"}</span>
            <input
              className="sr-only"
              type="file"
              accept="image/*,video/*"
              disabled={isLoading}
              onChange={(event) => onMediaChange(event.target.files?.[0]?.name ?? null)}
            />
          </label>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-4 border-t border-line pt-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Campaign goal">
          {goals.map((item) => {
            const active = goal === item.value;
            return (
              <button
                key={item.value}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={isLoading}
                className={`rounded-md border px-4 py-2 text-sm font-semibold transition ${
                  active ? "border-accent bg-accent text-white" : "border-line bg-white text-ink hover:border-accent/60"
                } disabled:cursor-not-allowed disabled:opacity-60`}
                onClick={() => onGoalChange(item.value)}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md bg-accent px-6 py-3 text-sm font-bold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
        >
          {isLoading ? "Routing..." : "Route it."}
        </button>
      </div>
    </form>
  );
}
