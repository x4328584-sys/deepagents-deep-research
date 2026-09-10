import { ArrowUp, FilePlus2, LoaderCircle, Paperclip, X } from "lucide-react";
import { useRef } from "react";

interface ComposerProps {
  query: string;
  onQueryChange: (value: string) => void;
  files: File[];
  onFilesChange: (files: File[]) => void;
  onSubmit: () => void;
  busy: boolean;
}

export function Composer({
  query,
  onQueryChange,
  files,
  onFilesChange,
  onSubmit,
  busy,
}: ComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const canSubmit = query.trim().length > 0 && !busy;
  return (
    <div className="composer-shell">
      {files.length > 0 && (
        <div className="attachment-list" aria-label="Selected attachments">
          {files.map((file, index) => (
            <span className="attachment-chip" key={`${file.name}-${file.lastModified}`}>
              <Paperclip aria-hidden="true" size={13} />
              {file.name}
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() => onFilesChange(files.filter((_, itemIndex) => itemIndex !== index))}
              >
                <X aria-hidden="true" size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="composer">
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          multiple
          accept=".txt,.md,.json,.jsonl,.csv,.docx,.pdf,.xlsx,.xls"
          onChange={(event) => {
            onFilesChange(Array.from(event.target.files || []));
            event.target.value = "";
          }}
        />
        <button
          className="attach-button"
          type="button"
          onClick={() => inputRef.current?.click()}
          aria-label="Attach research files"
          disabled={busy}
        >
          <FilePlus2 aria-hidden="true" size={19} />
        </button>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && canSubmit) {
              event.preventDefault();
              onSubmit();
            }
          }}
          placeholder="Describe the research task, sources, and desired report format…"
          aria-label="Research task"
          rows={2}
          maxLength={20_000}
          disabled={busy}
        />
        <button
          className="submit-button"
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          aria-label={busy ? "Research is running" : "Start research"}
        >
          {busy ? <LoaderCircle className="spin" aria-hidden="true" size={18} /> : <ArrowUp aria-hidden="true" size={19} />}
        </button>
      </div>
      <p className="composer-hint">Ctrl/⌘ + Enter to run · Markdown and PDF reports supported</p>
    </div>
  );
}

