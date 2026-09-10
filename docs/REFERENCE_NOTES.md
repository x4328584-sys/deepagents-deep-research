# Reference notes

## Source condition

The requested source files were initially found at `docs/深度搜索项目文档.md`
and `docs/api文档.md`, not beneath `docs/reference/`. Both files were read in
full on 2026-09-09 and were exactly zero bytes. They have been moved, without
content changes, to the requested `docs/reference/` paths. Consequently there
is no reference implementation, historical API text, frontend source, sample
pharma schema, version list, or secret to recover from those two files.

The attached project task is therefore the only substantive specification.
This implementation does not claim pixel-level or line-for-line fidelity to an
unavailable original project.

## Decisions and conflict resolution

| Topic | Observed issue | Decision |
|---|---|---|
| Reference location | Files existed one directory above the specified path | Move the unchanged empty files into `docs/reference/` |
| Reference content | Both primary references are empty | Treat the detailed attached task as authoritative; document every assumption |
| API compatibility | No reference API document exists | Implement the explicit REST/WebSocket JSON contracts verbatim and use correct HTTP 4xx errors |
| DeepAgents version | The task names an API but pins no release | Verify the current stable PyPI package and official API, then pin the tested compatible set |
| DeepSeek model alias | The legacy `deepseek-chat` alias is no longer current as of implementation | Default to current `deepseek-v4-flash`; keep `LLM_MODEL` environment-configurable for `deepseek-v4-pro` or later IDs |
| Word output | Narrative warns of possible Word references but tool chain defines only Markdown/PDF | Support Markdown/PDF output only |
| Offline requirement | Real DeepAgents needs an LLM, while Demo Mode must need no credentials | Keep the genuine DeepAgents graph for Real Mode and a clearly labelled offline coordinator for Demo Mode using identical boundaries/events |
| MySQL in Compose | Compose must include MySQL but Demo Mode must not require it | Keep MySQL in the opt-in `real` profile; default Compose starts only the credential-free frontend/backend |
| Upload move/copy | The task says “move/copy” | Copy uploads into a run session so failed/retried runs retain the original upload; overwrite is never silent |
| One connection mapping | Text says `thread_id -> connection`, but reconnect/multiple tabs are required | Store a set of live connections per thread; broadcasts remain thread-scoped |
| RAGFlow SDK | SDK/API revisions may differ | Isolate RAGFlow behind a tested SDK service adapter with timeout-aware transport and injected mocks |
| PDF engine | WeasyPrint can require native Windows libraries | Use ReportLab with its cross-platform `STSong-Light` CID font for conservative CJK report rendering |
| Supplied provider credential | A credential was supplied outside repository files | Never place it in repository/tool output; use Demo tests and document env-only Real Mode configuration; rotate before publishing |

## Behavioral precedence

For any later discovered discrepancy the project follows: executable API
contract and observed package behavior, then complete implementation guidance,
then architecture text, examples, and finally introductory prose. New findings
must be appended here rather than silently changing behavior.
