import { BookOpenText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownResultProps {
  result: string;
  running: boolean;
}

export function MarkdownResult({ result, running }: MarkdownResultProps) {
  if (!result && running) {
    return (
      <div className="research-pending" aria-live="polite">
        <span className="research-orbit" aria-hidden="true" />
        <span className="eyebrow">Research in progress</span>
        <h2>Specialists are gathering evidence.</h2>
        <p>Source calls and generated artifacts are visible in the activity rail.</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="welcome-state">
        <span className="welcome-icon">
          <BookOpenText aria-hidden="true" size={25} />
        </span>
        <span className="eyebrow">Research workspace</span>
        <h1>Ask a question that deserves more than one source.</h1>
        <p>
          The main agent plans the task, delegates to focused specialists, reflects on gaps,
          and returns a grounded answer or report.
        </p>
        <div className="route-grid" aria-label="Available research routes">
          <div><strong>Public web</strong><span>Network Search Agent</span></div>
          <div><strong>Structured data</strong><span>Database Query Agent</span></div>
          <div><strong>Private knowledge</strong><span>RAGFlow Agent</span></div>
          <div><strong>Your files</strong><span>Session-safe reader</span></div>
        </div>
      </div>
    );
  }
  return (
    <article className="markdown-result">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href, title }) => (
            <a href={href} title={title} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {result}
      </ReactMarkdown>
    </article>
  );
}
