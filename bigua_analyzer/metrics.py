from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .gitops import git_stdout


def repo_age_days(repo_dir: Path) -> int | None:
    """
    Age = days since first commit. Returns None if no commits.
    """
    out = git_stdout(repo_dir, ["rev-list", "--max-parents=0", "HEAD"]).strip()
    if not out:
        return None
    first = out.splitlines()[0].strip()
    ts = git_stdout(repo_dir, ["show", "-s", "--format=%ct", first]).strip()
    if not ts:
        return None
    first_ts = int(ts)

    now_ts = int(git_stdout(repo_dir, ["show", "-s", "--format=%ct", "HEAD"]).strip())
    days = max(0, (now_ts - first_ts) // 86400)
    return days


def commit_count(repo_dir: Path) -> int:
    out = git_stdout(repo_dir, ["rev-list", "--count", "HEAD"]).strip()
    return int(out) if out else 0


def contributor_count(repo_dir: Path) -> int:
    # Unique authors by email+name (fast enough for MVP)
    out = git_stdout(repo_dir, ["log", "--format=%aN <%aE>"]).strip()
    if not out:
        return 0
    uniq = set(line.strip() for line in out.splitlines() if line.strip())
    return len(uniq)


def top_contributor_share(repo_dir: Path) -> float:
    """
    Share of commits by top contributor (0..1).
    Uses shortlog -sne (counts commits per author).
    """
    out = git_stdout(repo_dir, ["shortlog", "-sne", "HEAD"]).strip()
    if not out:
        return 0.0
    counts = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # format: "  123\tName <email>"
        num = line.split("\t")[0].strip()
        try:
            counts.append(int(num))
        except ValueError:
            continue
    total = sum(counts)
    if total <= 0:
        return 0.0
    return max(counts) / total


def bus_factor_estimate(repo_dir: Path, threshold: float = 0.5) -> int:
    """
    Minimal number of top contributors needed to reach 'threshold' of commits.
    This is a rough bus-factor proxy for MVP.
    """
    out = git_stdout(repo_dir, ["shortlog", "-sne", "HEAD"]).strip()
    if not out:
        return 0
    counts = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        num = line.split("\t")[0].strip()
        try:
            counts.append(int(num))
        except ValueError:
            continue
    total = sum(counts)
    if total <= 0:
        return 0
    counts.sort(reverse=True)
    running = 0
    k = 0
    for c in counts:
        running += c
        k += 1
        if (running / total) >= threshold:
            return k
    return k


def security_files_presence(repo_dir: Path) -> Dict[str, bool]:
    """
    Simple presence checks. Keep this conservative (no content parsing yet).
    """
    files = {
        "SECURITY.md": False,
        "CODEOWNERS": False,
        ".github/dependabot.yml": False,
        ".github/workflows": False,
    }

    if (repo_dir / "SECURITY.md").exists():
        files["SECURITY.md"] = True
    if (repo_dir / "CODEOWNERS").exists() or (repo_dir / ".github" / "CODEOWNERS").exists():
        files["CODEOWNERS"] = True
    if (repo_dir / ".github" / "dependabot.yml").exists():
        files[".github/dependabot.yml"] = True
    if (repo_dir / ".github" / "workflows").exists() and (repo_dir / ".github" / "workflows").is_dir():
        files[".github/workflows"] = True

    return files


def collect_all_metrics(repo_dir: Path) -> Dict[str, Any]:
    age = repo_age_days(repo_dir)
    commits = commit_count(repo_dir)
    contributors = contributor_count(repo_dir)

    metrics: Dict[str, Any] = {
        "repo_age_days": age,
        "commit_count": commits,
        "contributor_count": contributors,
        "top_contributor_share": round(top_contributor_share(repo_dir), 6),
        "bus_factor_50p": bus_factor_estimate(repo_dir, threshold=0.5),
        "bus_factor_75p": bus_factor_estimate(repo_dir, threshold=0.75),
    }
    metrics.update({f"has_{k.replace('.', '_').replace('/', '_')}": v for k, v in security_files_presence(repo_dir).items()})
    return metrics