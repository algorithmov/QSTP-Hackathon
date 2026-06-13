"use client";

import axios from "axios";
import type {
  PersonalizeRequest,
  PersonalizeResponse,
  PlatformReportRequest,
  PlatformReportResponse,
  ReviewRequest,
  ReviewResponse
} from "@/types/route";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const backendUrl = () => process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const mockMode = () => process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

async function loadMock<T>(path: string): Promise<T> {
  await delay(750);
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Mock response could not be loaded.");
  }
  return response.json() as Promise<T>;
}

export async function reviewIdea(payload: ReviewRequest): Promise<ReviewResponse> {
  if (mockMode()) {
    return loadMock<ReviewResponse>("/mocks/review_response.json");
  }

  // Always send multipart/form-data — backend accepts Form fields + optional file uploads
  const form = new FormData();
  form.append("idea_text", payload.idea_text);
  form.append("goal", payload.goal);
  for (const file of payload.files ?? []) {
    form.append("files", file);
  }

  // Do NOT set Content-Type manually — axios must set it so it includes the multipart boundary.
  const { data } = await axios.post<ReviewResponse>(`${backendUrl()}/api/review`, form);
  return data;
}

export async function personalizeIdea(payload: PersonalizeRequest): Promise<PersonalizeResponse> {
  if (mockMode()) {
    return loadMock<PersonalizeResponse>("/mocks/personalize_response.json");
  }

  const { data } = await axios.post<PersonalizeResponse>(
    `${backendUrl()}/api/personalize`,
    payload
  );
  return data;
}

export async function fetchPlatformReport(
  payload: PlatformReportRequest
): Promise<PlatformReportResponse> {
  const { data } = await axios.post<PlatformReportResponse>(
    `${backendUrl()}/api/review/report`,
    payload
  );
  return data;
}

