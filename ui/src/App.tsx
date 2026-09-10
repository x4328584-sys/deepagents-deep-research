import { AlertTriangle, PanelRight, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getHealth, listFiles, startTask, uploadFiles } from "./api/client";
import { ActivityPanel } from "./components/ActivityPanel";
import { Composer } from "./components/Composer";
import { FilePanel } from "./components/FilePanel";
import { MarkdownResult } from "./components/MarkdownResult";
import { StatusPill } from "./components/StatusPill";
import { TaskHistory } from "./components/TaskHistory";
import { useResearchSocket } from "./hooks/useResearchSocket";
import type { GeneratedFile, TaskRecord, TaskStatus } from "./types";

const STORAGE_KEY = "deep-research-tasks-v1";

function loadTasks(): TaskRecord[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]") as unknown;
    return Array.isArray(parsed) ? (parsed as TaskRecord[]).slice(0, 30) : [];
  } catch {
    return [];
  }
}

function App() {
  const [tasks, setTasks] = useState<TaskRecord[]>(loadTasks);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [runtimeMode, setRuntimeMode] = useState<"demo" | "real" | "unknown">("unknown");
  const socket = useResearchSocket(activeId);

  const activeTask = useMemo(
    () => tasks.find((task) => task.id === activeId),
    [activeId, tasks],
  );

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  }, [tasks]);

  useEffect(() => {
    let active = true;
    void getHealth()
      .then((health) => {
        if (active) setRuntimeMode(health.mode);
      })
      .catch(() => {
        if (active) setRuntimeMode("unknown");
      });
    return () => {
      active = false;
    };
  }, []);

  const patchTask = useCallback((id: string, patch: Partial<TaskRecord>) => {
    setTasks((current) =>
      current.map((task) => {
        if (task.id !== id) return task;
        const changed = Object.entries(patch).some(
          ([key, value]) => task[key as keyof TaskRecord] !== value,
        );
        return changed ? { ...task, ...patch } : task;
      }),
    );
  }, []);

  const refreshFiles = useCallback(async (sessionPath: string) => {
    if (!sessionPath) return;
    setFilesLoading(true);
    try {
      setFiles(await listFiles(sessionPath));
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Could not load generated files.");
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!activeId) return;
    const latest = socket.events.at(-1);
    if (latest && !["task_result", "error"].includes(latest.event)) {
      patchTask(activeId, { status: "running" });
    }
    if (socket.sessionPath) {
      patchTask(activeId, { sessionPath: socket.sessionPath });
    }
    if (socket.result) {
      patchTask(activeId, {
        status: "complete",
        result: socket.result,
        sessionPath: socket.sessionPath || activeTask?.sessionPath,
      });
      setBusy(false);
      void refreshFiles(socket.sessionPath || activeTask?.sessionPath || "");
    }
    if (socket.error) {
      patchTask(activeId, { status: "error", error: socket.error });
      setBusy(false);
    }
  }, [
    activeId,
    activeTask?.sessionPath,
    patchTask,
    refreshFiles,
    socket.error,
    socket.events,
    socket.result,
    socket.sessionPath,
  ]);

  useEffect(() => {
    setFiles([]);
    setRequestError("");
    if (activeTask?.sessionPath) void refreshFiles(activeTask.sessionPath);
  }, [activeId, activeTask?.sessionPath, refreshFiles]);

  const handleSubmit = async () => {
    const normalized = query.trim();
    if (!normalized || busy) return;
    const id = crypto.randomUUID();
    const task: TaskRecord = {
      id,
      query: normalized,
      createdAt: new Date().toISOString(),
      status: "starting",
    };
    setTasks((current) => [task, ...current].slice(0, 30));
    setActiveId(id);
    setBusy(true);
    setRequestError("");
    setFiles([]);
    const attachments = selectedFiles;
    setSelectedFiles([]);
    setQuery("");
    try {
      if (attachments.length) await uploadFiles(id, attachments);
      await startTask(normalized, id);
      patchTask(id, { status: "running" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Research could not be started.";
      setRequestError(message);
      patchTask(id, { status: "error", error: message });
      setBusy(false);
    }
  };

  const displayedResult = socket.result || activeTask?.result || "";
  const displayedError = requestError || socket.error || activeTask?.error || "";
  const displayedStatus: TaskStatus = activeTask?.status || "starting";

  return (
    <div className="app-shell">
      <TaskHistory
        tasks={tasks}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id);
          setBusy(tasks.find((task) => task.id === id)?.status === "running");
        }}
        onNew={() => {
          setActiveId(null);
          setQuery("");
          setSelectedFiles([]);
          setBusy(false);
          setRequestError("");
          setFiles([]);
        }}
      />

      <main className="research-main">
        <header className="workspace-header">
          <div>
            <span className="eyebrow">Orchestrator workspace</span>
            <h2>{activeTask ? activeTask.query : "New research"}</h2>
          </div>
          <div className="header-actions">
            {activeTask && <StatusPill status={displayedStatus} />}
            <span className="mode-badge">
              <Sparkles aria-hidden="true" size={14} />
              {runtimeMode === "unknown" ? "API mode unavailable" : `${runtimeMode === "demo" ? "Demo" : "Real"} Mode`}
            </span>
          </div>
        </header>

        {displayedError && (
          <div className="error-banner" role="alert">
            <AlertTriangle aria-hidden="true" size={18} />
            <span>{displayedError}</span>
          </div>
        )}

        <section className="answer-scroll" aria-label="Research answer">
          <MarkdownResult
            result={displayedResult}
            running={busy || displayedStatus === "running"}
          />
        </section>

        <Composer
          query={query}
          onQueryChange={setQuery}
          files={selectedFiles}
          onFilesChange={setSelectedFiles}
          onSubmit={() => void handleSubmit()}
          busy={busy}
        />
      </main>

      <aside className="inspector-panel" aria-label="Research inspector">
        <div className="inspector-label">
          <PanelRight aria-hidden="true" size={16} /> Execution inspector
        </div>
        <ActivityPanel events={socket.events} connectionStatus={socket.connectionStatus} />
        <FilePanel files={files} loading={filesLoading} />
      </aside>
    </div>
  );
}

export default App;
