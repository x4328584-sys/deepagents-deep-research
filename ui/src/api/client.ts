import type { GeneratedFile } from "../types";

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const productionHttpBase = window.location.origin;
const productionWebSocketBase = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.DEV ? "http://localhost:8000" : productionHttpBase),
);
export const WS_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_WS_BASE_URL ||
    (import.meta.env.DEV ? "ws://localhost:8000" : productionWebSocketBase),
);

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  let message = `Request failed (${response.status})`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) message = payload.detail;
  } catch {
    // Keep the status-based fallback when the server does not return JSON.
  }
  throw new Error(message);
}

export async function getHealth(): Promise<{ status: string; mode: "demo" | "real" }> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return parseResponse(response);
}

export async function uploadFiles(threadId: string, files: File[]): Promise<string[]> {
  if (!files.length) return [];
  const form = new FormData();
  form.append("thread_id", threadId);
  files.forEach((file) => form.append("files", file));
  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: form,
  });
  const payload = await parseResponse<{ status: string; files: string[] }>(response);
  return payload.files;
}

export async function startTask(
  query: string,
  threadId: string,
): Promise<{ status: string; thread_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/task`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id: threadId }),
  });
  return parseResponse(response);
}

export async function listFiles(path: string): Promise<GeneratedFile[]> {
  const query = new URLSearchParams({ path });
  const response = await fetch(`${API_BASE_URL}/api/files?${query.toString()}`);
  return parseResponse(response);
}

export function downloadUrl(path: string): string {
  const query = new URLSearchParams({ path });
  return `${API_BASE_URL}/api/download?${query.toString()}`;
}
