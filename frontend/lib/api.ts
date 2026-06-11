import axios from 'axios';
import { RouteRequest, RouteResponse } from './types';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === 'true';

export async function routeContent(request: RouteRequest): Promise<RouteResponse> {
  if (USE_MOCKS) {
    await new Promise(resolve => setTimeout(resolve, 1200));
    const mock = await import('../mocks/route_response.json');
    return mock.default as unknown as RouteResponse;
  }
  const response = await axios.post<RouteResponse>(`${BACKEND_URL}/api/route`, request);
  return response.data;
}

export async function uploadMedia(file: File): Promise<string> {
  if (USE_MOCKS) {
    return `uploads/${file.name}`;
  }
  const formData = new FormData();
  formData.append('file', file);
  const response = await axios.post<{ media_url: string }>(
    `${BACKEND_URL}/api/upload`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data.media_url;
}
