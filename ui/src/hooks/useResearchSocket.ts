import { useEffect, useRef, useState } from "react";

import { WS_BASE_URL } from "../api/client";
import type { ConnectionStatus, MonitorEvent } from "../types";

interface SocketState {
  connectionStatus: ConnectionStatus;
  events: MonitorEvent[];
  result: string;
  sessionPath: string;
  error: string;
}

interface ScopedSocketState extends SocketState {
  threadId: string | null;
}

const initialState: ScopedSocketState = {
  threadId: null,
  connectionStatus: "idle",
  events: [],
  result: "",
  sessionPath: "",
  error: "",
};

export function useResearchSocket(threadId: string | null): SocketState {
  const [state, setState] = useState<ScopedSocketState>(initialState);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!threadId) {
      setState(initialState);
      return;
    }

    let disposed = false;
    let retries = 0;
    let reconnectTimer: number | undefined;
    let heartbeatTimer: number | undefined;
    setState({ ...initialState, threadId, connectionStatus: "connecting" });

    const connect = () => {
      if (disposed) return;
      setState((current) =>
        current.threadId === threadId
          ? {
              ...current,
              connectionStatus: retries ? "reconnecting" : "connecting",
            }
          : current,
      );
      const socket = new WebSocket(`${WS_BASE_URL}/ws/${encodeURIComponent(threadId)}`);
      socketRef.current = socket;

      socket.onopen = () => {
        if (disposed) return;
        retries = 0;
        setState((current) =>
          current.threadId === threadId
            ? { ...current, connectionStatus: "connected", error: "" }
            : current,
        );
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send("ping");
        }, 25_000);
      };

      socket.onmessage = (message) => {
        if (disposed) return;
        try {
          const payload = JSON.parse(String(message.data)) as
            | MonitorEvent
            | { type: "pong"; message: string };
          if (payload.type === "pong") return;
          setState((current) => {
            if (current.threadId !== threadId) return current;
            const next: ScopedSocketState = {
              ...current,
              events: [...current.events, payload].slice(-100),
            };
            if (payload.event === "session_created") {
              next.sessionPath = String(payload.data.path || "");
            } else if (payload.event === "task_result") {
              next.result = String(payload.data.result || "");
            } else if (payload.event === "error") {
              next.error = String(payload.data.error || payload.message);
            }
            return next;
          });
        } catch {
          setState((current) =>
            current.threadId === threadId
              ? { ...current, error: "Received an invalid server event." }
              : current,
          );
        }
      };

      socket.onerror = () => socket.close();
      socket.onclose = () => {
        window.clearInterval(heartbeatTimer);
        if (disposed) return;
        retries += 1;
        const delay = Math.min(1_000 * 2 ** Math.min(retries - 1, 3), 10_000);
        setState((current) =>
          current.threadId === threadId
            ? { ...current, connectionStatus: "reconnecting" }
            : current,
        );
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(reconnectTimer);
      window.clearInterval(heartbeatTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [threadId]);

  if (state.threadId !== threadId) {
    return {
      ...initialState,
      connectionStatus: threadId ? "connecting" : "idle",
    };
  }
  return state;
}
