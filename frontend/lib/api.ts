"use client";

import axios from "axios";
import type { RouteRequest, RouteResponse } from "@/types/route";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function routeContent(payload: RouteRequest): Promise<RouteResponse> {
  const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

  if (useMocks) {
    await delay(650);
    const response = await fetch("/mocks/route_response.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Mock route response could not be loaded.");
    }
    return response.json() as Promise<RouteResponse>;
  }

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  const { data } = await axios.post<RouteResponse>(`${backendUrl}/api/route`, payload);
  return data;
}
