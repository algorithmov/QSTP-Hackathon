"use client";

import axios from "axios";
import type {
  PersonalizeRequest,
  PersonalizeResponse,
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

  const { data } = await axios.post<ReviewResponse>(`${backendUrl()}/api/review`, payload);
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

// Legacy no-op helpers retained until old v1 components are removed.
export async function uploadMedia(): Promise<string | null> {
  return null;
}

export async function routeContent(): Promise<never> {
  throw new Error("The v1 route endpoint was replaced by /api/review and /api/personalize.");
}
