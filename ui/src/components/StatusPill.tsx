import { CircleCheck, CircleDashed, CircleX, Radio } from "lucide-react";

import type { ConnectionStatus, TaskStatus } from "../types";

interface StatusPillProps {
  status: TaskStatus | ConnectionStatus;
}

const labels: Record<TaskStatus | ConnectionStatus, string> = {
  idle: "Offline",
  connecting: "Connecting",
  connected: "Live",
  reconnecting: "Reconnecting",
  starting: "Starting",
  running: "Researching",
  complete: "Complete",
  error: "Needs attention",
};

export function StatusPill({ status }: StatusPillProps) {
  const Icon =
    status === "complete" || status === "connected"
      ? CircleCheck
      : status === "error"
        ? CircleX
        : status === "running"
          ? Radio
          : CircleDashed;
  return (
    <span className={`status-pill status-${status}`}>
      <Icon aria-hidden="true" size={13} strokeWidth={2.2} />
      {labels[status]}
    </span>
  );
}

