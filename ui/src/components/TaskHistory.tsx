import { Plus, Search } from "lucide-react";

import type { TaskRecord } from "../types";
import { StatusPill } from "./StatusPill";

interface TaskHistoryProps {
  tasks: TaskRecord[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function TaskHistory({ tasks, activeId, onSelect, onNew }: TaskHistoryProps) {
  return (
    <aside className="history-panel" aria-label="Research tasks">
      <div className="brand-block">
        <div className="brand-mark" aria-hidden="true">
          DR
        </div>
        <div>
          <span className="eyebrow">DeepAgents</span>
          <strong>Deep Research</strong>
        </div>
      </div>

      <button className="new-task-button" type="button" onClick={onNew}>
        <Plus aria-hidden="true" size={17} />
        New research
      </button>

      <div className="history-heading">
        <span>Recent tasks</span>
        <span className="task-count">{tasks.length}</span>
      </div>

      <div className="task-list">
        {tasks.length === 0 ? (
          <div className="history-empty">
            <Search aria-hidden="true" size={20} />
            <p>Your research tasks will appear here.</p>
          </div>
        ) : (
          tasks.map((task) => (
            <button
              className={`task-card ${task.id === activeId ? "is-active" : ""}`}
              type="button"
              key={task.id}
              onClick={() => onSelect(task.id)}
              aria-current={task.id === activeId ? "page" : undefined}
            >
              <span className="task-title">{task.query}</span>
              <span className="task-meta">
                <span>{formatTime(task.createdAt)}</span>
                <StatusPill status={task.status} />
              </span>
            </button>
          ))
        )}
      </div>

      <div className="mode-note">
        <span className="mode-dot" />
        Demo-ready · provider optional
      </div>
    </aside>
  );
}

