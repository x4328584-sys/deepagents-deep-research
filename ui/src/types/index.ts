export type TaskStatus = "starting" | "running" | "complete" | "error";

export interface TaskRecord {
  id: string;
  query: string;
  createdAt: string;
  status: TaskStatus;
  result?: string;
  sessionPath?: string;
  error?: string;
}

export interface MonitorEvent {
  type: "monitor_event";
  event: "session_created" | "tool_start" | "assistant_call" | "task_result" | "error";
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface GeneratedFile {
  name: string;
  type: "file";
  path: string;
  size: number;
  mtime: number;
}

export type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting";

