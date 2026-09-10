import { Download, File, FileText, LoaderCircle } from "lucide-react";

import { downloadUrl } from "../api/client";
import type { GeneratedFile } from "../types";

interface FilePanelProps {
  files: GeneratedFile[];
  loading: boolean;
}

function formatBytes(value: number): string {
  if (value < 1_024) return `${value} B`;
  if (value < 1_048_576) return `${(value / 1_024).toFixed(1)} KB`;
  return `${(value / 1_048_576).toFixed(1)} MB`;
}

export function FilePanel({ files, loading }: FilePanelProps) {
  return (
    <section className="files-section" aria-labelledby="files-title">
      <div className="panel-heading compact-heading">
        <div>
          <span className="eyebrow">Artifacts</span>
          <h2 id="files-title">Generated files</h2>
        </div>
        {loading && <LoaderCircle className="spin" aria-label="Loading files" size={17} />}
      </div>
      <div className="file-list">
        {files.length === 0 ? (
          <div className="file-empty">
            <File aria-hidden="true" size={20} />
            <span>No generated reports yet.</span>
          </div>
        ) : (
          files.map((file) => (
            <article className="file-row" key={file.path}>
              <span className="file-icon">
                <FileText aria-hidden="true" size={17} />
              </span>
              <div className="file-copy">
                <strong title={file.name}>{file.name}</strong>
                <small>{formatBytes(file.size)}</small>
              </div>
              <a
                className="download-button"
                href={downloadUrl(file.path)}
                aria-label={`Download ${file.name}`}
              >
                <Download aria-hidden="true" size={16} />
              </a>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

