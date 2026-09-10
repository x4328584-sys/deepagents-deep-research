"""Pattern-based current-tree and Git-history secret scan for release gates."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
TOKEN_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-compatible key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Tavily key": re.compile(rb"\btvly-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
SECRET_ASSIGNMENT = re.compile(
    rb"(?m)^[ \t]*(?:OPENAI_API_KEY|TAVILY_API_KEY|RAGFLOW_API_KEY|"
    rb"MYSQL_PASSWORD|MYSQL_ROOT_PASSWORD)[ \t]*=[ \t]*([^\r\n]*)[ \t]*$"
)
PLACEHOLDER = re.compile(
    rb"^(?:<[^>]+>|\$\{[^}]+\}|\[?REDACTED\]?|test[-_].*|dummy|example)?$",
    re.IGNORECASE,
)


def _git(*args: str, check: bool = True) -> bytes:
    if GIT is None:
        raise RuntimeError("git executable is required for the secret scan")
    result = subprocess.run(  # noqa: S603 - internal executable and release-gate arguments
        [GIT, *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _find_secret_kinds(content: bytes) -> set[str]:
    findings = {name for name, pattern in TOKEN_PATTERNS.items() if pattern.search(content)}
    for match in SECRET_ASSIGNMENT.finditer(content):
        value = match.group(1).strip().strip(b'"\'')
        if not PLACEHOLDER.fullmatch(value):
            findings.add("non-placeholder credential assignment")
    return findings


def main() -> int:
    candidates = [
        item.decode("utf-8", errors="surrogateescape")
        for item in _git(
            "ls-files", "-z", "--cached", "--others", "--exclude-standard"
        ).split(b"\0")
        if item
    ]
    findings: list[tuple[str, str]] = []
    for relative in candidates:
        path = ROOT / relative
        if not path.is_file():
            continue
        content = path.read_bytes()
        if b"\0" in content:
            continue
        for kind in _find_secret_kinds(content):
            findings.append((relative, kind))

    history = _git(
        "log",
        "-p",
        "--all",
        "--full-history",
        "--no-ext-diff",
        "--no-textconv",
        check=False,
    )
    commit_count_raw = _git("rev-list", "--count", "--all", check=False).strip()
    commit_count = int(commit_count_raw) if commit_count_raw.isdigit() else 0
    for kind in _find_secret_kinds(history):
        findings.append(("Git history", kind))

    tracked = {
        item.decode("utf-8", errors="surrogateescape")
        for item in _git("ls-files", "-z").split(b"\0")
        if item
    }
    forbidden_env = sorted(
        path for path in tracked if Path(path).name == ".env"
    )
    findings.extend((path, "tracked local environment file") for path in forbidden_env)

    if GIT is None:
        raise RuntimeError("git executable is required for the secret scan")
    ignored_env = (
        subprocess.run(  # noqa: S603 - fixed executable and fixed arguments
            [GIT, "check-ignore", "-q", ".env"],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )
    if not ignored_env:
        findings.append((".gitignore", ".env is not ignored"))

    if findings:
        for path, kind in sorted(set(findings)):
            print(f"FAIL: {kind} in {path}")
        return 1
    print(
        f"PASS: scanned {len(candidates)} release files and {commit_count} Git commits; "
        "no secret patterns found; .env is ignored"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
