import {
  Bot,
  CheckCircle2,
  Database,
  FileCog,
  Globe2,
  TriangleAlert,
  Wrench,
} from "lucide-react";

import type { ConnectionStatus, MonitorEvent } from "../types";
import { StatusPill } from "./StatusPill";

interface ActivityPanelProps {
  events: MonitorEvent[];
  connectionStatus: ConnectionStatus;
}

function EventIcon({ event }: { event: MonitorEvent }) {
  const name = String(event.data.assistant_name || event.data.tool_name || "");
  if (event.event === "error") return <TriangleAlert aria-hidden="true" size={16} />;
  if (event.event === "task_result") return <CheckCircle2 aria-hidden="true" size={16} />;
  if (event.event === "session_created") return <FileCog aria-hidden="true" size={16} />;
  if (name.includes("network") || name.includes("internet")) {
    return <Globe2 aria-hidden="true" size={16} />;
  }
  if (name.includes("database") || name.includes("sql")) {
    return <Database aria-hidden="true" size={16} />;
  }
  if (event.event === "assistant_call") return <Bot aria-hidden="true" size={16} />;
  return <Wrench aria-hidden="true" size={16} />;
}

function eventDetail(event: MonitorEvent): string {
  if (event.event === "assistant_call") return String(event.data.assistant_name || "Specialist");
  if (event.event === "tool_start") {
    const args = event.data.args;
    const query = args && typeof args === "object" ? String((args as Record<string, unknown>).query || "") : "";
    return query ? `${String(event.data.tool_name)} · ${query.slice(0, 90)}` : String(event.data.tool_name);
  }
  if (event.event === "session_created") return String(event.data.path || "Workspace ready");
  if (event.event === "error") return String(event.data.error || "Task failed");
  return "Final response delivered";
}

export function ActivityPanel({ events, connectionStatus }: ActivityPanelProps) {
  return (
    <section className="activity-section" aria-labelledby="activity-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Live trace</span>
          <h2 id="activity-title">Agent activity</h2>
        </div>
        <StatusPill status={connectionStatus} />
      </div>
      <div className="activity-list" aria-live="polite">
        {events.length === 0 ? (
          <div className="activity-empty">
            <Bot aria-hidden="true" size={22} />
            <p>Execution events will appear once research begins.</p>
            <small>Private model reasoning is never displayed.</small>
          </div>
        ) : (
          events.map((event, index) => (
            <article className={`activity-item event-${event.event}`} key={`${event.timestamp}-${index}`}>
              <span className="activity-icon">
                <EventIcon event={event} />
              </span>
              <div>
                <strong>{event.message}</strong>
                <p>{eventDetail(event)}</p>
                <time dateTime={event.timestamp}>
                  {new Date(event.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </time>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

