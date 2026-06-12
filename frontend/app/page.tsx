"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";
import { InputPanel } from "@/components/InputPanel";
import { MenaMap } from "@/components/MenaMap";
import { RouteBoard } from "@/components/RouteBoard";
import { TrendTicker } from "@/components/TrendTicker";
import { VisualProfilePanel } from "@/components/VisualProfilePanel";
import { routeContent } from "@/lib/api";
import type { Goal, RouteRequest, RouteResponse } from "@/types/route";

const starterText = "A 30-second clip of a Jordanian student showing her water-purification prototype.";

export default function Page() {
  const [contentText, setContentText] = useState(starterText);
  const [goal, setGoal] = useState<Goal | null>("applications");
  const [topicHint, setTopicHint] = useState("young inventors water tech");
  const [mediaFileName, setMediaFileName] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RouteResponse | null>(null);

  async function handleSubmit(payload: RouteRequest) {
    setStatus("loading");
    setError(null);
    try {
      const response = await routeContent(payload);
      setResult(response);
      setStatus("success");
    } catch {
      setError("Routing failed. Check the backend URL or mock response and try again.");
      setStatus("error");
    }
  }

  const routes = result?.routes ?? [];
  const mapData = result?.map_data ?? [];
  const trends = result?.trend_ticker ?? [];

  return (
    <main className="min-h-screen bg-paper">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3 border-b border-line pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-black tracking-normal text-ink sm:text-4xl">Masar</h1>
            <p className="mt-2 max-w-2xl text-base leading-7 text-muted">
              Route content to the right platform, country, language, and publishing time.
            </p>
          </div>
          <div className="rounded-md border border-line bg-white px-4 py-3 text-sm font-semibold text-muted">
            {process.env.NEXT_PUBLIC_USE_MOCKS === "false" ? "Live backend" : "Mock mode"}
          </div>
        </header>

        <InputPanel
          contentText={contentText}
          goal={goal}
          topicHint={topicHint}
          mediaFileName={mediaFileName}
          isLoading={status === "loading"}
          onContentTextChange={setContentText}
          onGoalChange={setGoal}
          onTopicHintChange={setTopicHint}
          onMediaChange={setMediaFileName}
          onSubmit={handleSubmit}
        />

        {status === "loading" ? (
          <div className="flex items-center gap-3 rounded-md border border-line bg-white px-5 py-4 text-sm font-semibold text-muted shadow-board">
            <Loader2 className="animate-spin text-accent" size={18} aria-hidden="true" />
            Calculating route fit from the frozen contract.
          </div>
        ) : null}

        {status === "error" && error ? (
          <div className="flex items-center gap-3 rounded-md border border-red-200 bg-red-50 px-5 py-4 text-sm font-semibold text-red-800">
            <AlertCircle size={18} aria-hidden="true" />
            {error}
          </div>
        ) : null}

        {result ? (
          <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
            <div className="space-y-5">
              <RouteBoard routes={routes} />
            </div>
            <aside className="space-y-5">
              <VisualProfilePanel summary={result.content_summary} profile={result.visual_profile} />
              <MenaMap data={mapData} />
            </aside>
          </div>
        ) : (
          <RouteBoard routes={[]} />
        )}

        <TrendTicker trends={trends} />
      </div>
    </main>
  );
}
