"""Pre-release security audit for tracked repository content and commit history."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


HIGH_CONFIDENCE_PATTERNS = {
    "provider_token_patterns": re.compile(
        r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z\-_]{35}|sk-[A-Za-z0-9]{20,})"
    ),
    "private_key_block": re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


GENERIC_KEYWORD_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|password|passwd|private[_-]?key|client[_-]?secret|access[_-]?key|auth[_-]?token)"
)


DEFAULT_EXCLUDE_FILE_PATTERNS = (
    re.compile(r"^tests/"),
    re.compile(r"^README\.md$"),
    re.compile(r"^docs/.*\.svg$"),
)


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def is_excluded(path: str) -> bool:
    return any(rx.search(path) for rx in DEFAULT_EXCLUDE_FILE_PATTERNS)


def tracked_files(repo_root: Path) -> list[str]:
    cp = run_git(["ls-files"], repo_root)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "git ls-files failed")
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def file_content(repo_root: Path, rel_path: str) -> str:
    file_path = repo_root / rel_path
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan_tracked_content(repo_root: Path, include_generic: bool) -> list[str]:
    findings: list[str] = []
    for rel_path in tracked_files(repo_root):
        if is_excluded(rel_path):
            continue
        content = file_content(repo_root, rel_path)
        if not content:
            continue
        patterns = dict(HIGH_CONFIDENCE_PATTERNS)
        if include_generic:
            patterns["generic_secret_keywords"] = GENERIC_KEYWORD_PATTERN

        for name, pattern in patterns.items():
            for match in pattern.finditer(content):
                if name == "email" and match.group(0).endswith("@example.com"):
                    continue
                line_no = content.count("\n", 0, match.start()) + 1
                snippet = match.group(0)
                findings.append(f"{rel_path}:{line_no} [{name}] {snippet}")
    return findings


def scan_git_history(repo_root: Path, max_count: int, include_generic: bool) -> list[str]:
    findings: list[str] = []
    cp_log = run_git(["rev-list", f"--max-count={max_count}", "HEAD"], repo_root)
    if cp_log.returncode != 0:
        raise RuntimeError(cp_log.stderr.strip() or "git rev-list failed")

    commits = [c.strip() for c in cp_log.stdout.splitlines() if c.strip()]
    for commit in commits:
        cp_show = run_git(["show", "--no-color", "--format=", commit], repo_root)
        if cp_show.returncode != 0:
            continue
        text = cp_show.stdout
        patterns = dict(HIGH_CONFIDENCE_PATTERNS)
        if include_generic:
            patterns["generic_secret_keywords"] = GENERIC_KEYWORD_PATTERN

        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                if name == "email" and match.group(0).endswith("@example.com"):
                    continue
                findings.append(f"{commit} [{name}] {match.group(0)}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-release security audit.")
    parser.add_argument(
        "--history-commits",
        type=int,
        default=200,
        help="Number of recent commits to scan in history (default: 200).",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip history scanning and only scan tracked file content.",
    )
    parser.add_argument(
        "--include-generic-keyword-scan",
        action="store_true",
        help="Also scan generic secret keywords (high false-positive rate).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    try:
        tracked_findings = scan_tracked_content(
            repo_root, include_generic=args.include_generic_keyword_scan
        )
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2

    history_findings: list[str] = []
    if not args.no_history:
        try:
            history_findings = scan_git_history(
                repo_root,
                max_count=args.history_commits,
                include_generic=args.include_generic_keyword_scan,
            )
        except RuntimeError as exc:
            print(f"[ERROR] {exc}")
            return 2

    print("[INFO] Tracked content findings:", len(tracked_findings))
    print("[INFO] History findings:", len(history_findings))

    if tracked_findings:
        print("\n[TRACKED CONTENT]")
        for finding in tracked_findings[:200]:
            print("-", finding)

    if history_findings:
        print("\n[HISTORY]")
        for finding in history_findings[:200]:
            print("-", finding)

    if tracked_findings or history_findings:
        print("\n[FAIL] Potentially sensitive data found. Review findings before release.")
        return 1

    print("\n[PASS] No potentially sensitive data found by current audit rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())