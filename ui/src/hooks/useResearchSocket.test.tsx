import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useResearchSocket } from "./useResearchSocket";

class MockWebSocket {
  static readonly OPEN = 1;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(url: string | URL) {
    this.url = String(url);
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  message(payload: unknown) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(payload) }),
    );
  }

  rawMessage(payload: string) {
    this.onmessage?.(new MessageEvent("message", { data: payload }));
  }

  disconnect() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
}

describe("useResearchSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("collects result events, sends heartbeats, and reconnects", () => {
    const { result, unmount } = renderHook(() => useResearchSocket("thread-hook"));
    const first = MockWebSocket.instances[0];

    expect(first?.url).toContain("/ws/thread-hook");
    expect(result.current.connectionStatus).toBe("connecting");

    act(() => first?.open());
    expect(result.current.connectionStatus).toBe("connected");

    act(() => {
      first?.message({
        type: "monitor_event",
        event: "session_created",
        message: "Session workspace created",
        data: { path: "session_thread-hook" },
        timestamp: "2026-09-09T08:00:00Z",
      });
      first?.message({
        type: "monitor_event",
        event: "task_result",
        message: "Research task completed",
        data: { result: "# Complete" },
        timestamp: "2026-09-09T08:00:01Z",
      });
    });
    expect(result.current.sessionPath).toBe("session_thread-hook");
    expect(result.current.result).toBe("# Complete");
    expect(result.current.events).toHaveLength(2);

    act(() => first?.message({ type: "pong", message: "received" }));
    expect(result.current.events).toHaveLength(2);

    act(() => first?.rawMessage("{invalid"));
    expect(result.current.error).toBe("Received an invalid server event.");

    act(() => vi.advanceTimersByTime(25_000));
    expect(first?.send).toHaveBeenCalledWith("ping");

    act(() => first?.disconnect());
    expect(result.current.connectionStatus).toBe("reconnecting");
    act(() => vi.advanceTimersByTime(1_000));
    expect(MockWebSocket.instances).toHaveLength(2);

    unmount();
  });

  it("caps exponential reconnect delay", () => {
    const { unmount } = renderHook(() => useResearchSocket("bounded-backoff"));
    MockWebSocket.instances[0]?.disconnect();

    for (const delay of [1_000, 2_000, 4_000, 8_000]) {
      act(() => vi.advanceTimersByTime(delay));
      const latest = MockWebSocket.instances.at(-1);
      latest?.disconnect();
    }

    const countBeforeCap = MockWebSocket.instances.length;
    act(() => vi.advanceTimersByTime(7_999));
    expect(MockWebSocket.instances).toHaveLength(countBeforeCap);
    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(countBeforeCap + 1);
    unmount();
  });
});
