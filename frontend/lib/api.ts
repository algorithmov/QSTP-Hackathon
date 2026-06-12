"use client";

import axios from "axios";
import type { RouteRequest, RouteResponse } from "@/types/route";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const backendUrl = () => process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const mockMode = () => process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

export async function uploadMedia(file: File): Promise<string | null> {
  if (mockMode()) return null;
  const form = new FormData();
  form.append("file", file);
  try {
    const resp = await fetch(`${backendUrl()}/api/upload`, { method: "POST", body: form });
    if (!resp.ok) return null;
    const data = (await resp.json()) as { media_url: string };
    return data.media_url;
  } catch {
    return null;
  }
}

export async function routeContent(payload: RouteRequest): Promise<RouteResponse> {
  if (mockMode()) {
    await delay(650);
    const response = await fetch("/mocks/route_response.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Mock route response could not be loaded.");
    return response.json() as Promise<RouteResponse>;
  }

  const { data } = await axios.post<RouteResponse>(`${backendUrl()}/api/route`, payload);
  return data;
}
