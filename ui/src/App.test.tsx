import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import App from "./App";

class AppWebSocket {
  static readonly OPEN = 1;
  static instances: AppWebSocket[] = [];

  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(readonly url: string | URL) {
    AppWebSocket.instances.push(this);
  }

  open() {
    this.readyState = AppWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  message(payload: unknown) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(payload) }),
    );
  }
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  localStorage.clear();
  AppWebSocket.instances = [];
  vi.stubGlobal("WebSocket", AppWebSocket as unknown as typeof WebSocket);
  vi.stubGlobal(
    "crypto",
    {
      randomUUID: () => "11111111-1111-4111-8111-111111111111",
    } as unknown as Crypto,
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/health")) return jsonResponse({ status: "ok", mode: "real" });
      if (url.includes("/api/task") && init?.method === "POST") {
        return jsonResponse({
          status: "started",
          thread_id: "11111111-1111-4111-8111-111111111111",
        });
      }
      if (url.includes("/api/files?")) {
        return jsonResponse([
          {
            name: "report.md",
            type: "file",
            path: "session_11111111-1111-4111-8111-111111111111/report.md",
            size: 1024,
            mtime: 1_788_940_800,
          },
        ]);
      }
      throw new Error(`unexpected request: ${url}`);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("wires task events into the final answer and generated-file panel", async () => {
  render(<App />);
  expect(await screen.findByText("Real Mode")).toBeInTheDocument();

  fireEvent.change(screen.getByRole("textbox", { name: "Research task" }), {
    target: { value: "Create a Markdown report" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Start research" }));

  await waitFor(() => expect(AppWebSocket.instances).toHaveLength(1));
  const socket = AppWebSocket.instances[0];
  act(() => {
    socket?.open();
    socket?.message({
      type: "monitor_event",
      event: "session_created",
      message: "Session workspace created",
      data: { path: "session_11111111-1111-4111-8111-111111111111" },
      timestamp: "2026-09-09T08:00:00Z",
    });
    socket?.message({
      type: "monitor_event",
      event: "task_result",
      message: "Research task completed",
      data: { result: "# Complete report" },
      timestamp: "2026-09-09T08:00:01Z",
    });
  });

  expect(await screen.findByRole("heading", { name: "Complete report" })).toBeInTheDocument();
  expect(await screen.findByText("report.md")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download report.md" })).toHaveAttribute(
    "href",
    expect.stringContaining("/api/download?path=session_11111111"),
  );
});
