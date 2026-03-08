from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .gitops import git_stdout


def repo_age_days(repo_dir: Path, ref: str = "HEAD") -> int | None:
    """
    Age = days since first commit. Returns None if no commits.
    """
    out = git_stdout(repo_dir, ["rev-list", "--max-parents=0", ref]).strip()
    if not out:
        return None
    first = out.splitlines()[0].strip()
    ts = git_stdout(repo_dir, ["show", "-s", "--format=%ct", first]).strip()
    if not ts:
        return None
    first_ts = int(ts)

    now_ts = int(git_stdout(repo_dir, ["show", "-s", "--format=%ct", ref]).strip())
    days = max(0, (now_ts - first_ts) // 86400)
    return days


def commit_count(repo_dir: Path, ref: str = "HEAD") -> int:
    out = git_stdout(repo_dir, ["rev-list", "--count", ref]).strip()
    return int(out) if out else 0


def contributor_count(repo_dir: Path, ref: str = "HEAD") -> int:
    # Unique authors by email+name (fast enough for MVP)
    out = git_stdout(repo_dir, ["log", "--format=%aN <%aE>", ref]).strip()
    if not out:
        return 0
    uniq = set(line.strip() for line in out.splitlines() if line.strip())
    return len(uniq)


def _shortlog_entries(repo_dir: Path, ref: str = "HEAD") -> list[tuple[int, str]]:
    """
    Returns a list of (commit_count, author_field) from git shortlog -sne HEAD.
    Example author_field: 'Name <email@example.com>'
    """
    out = git_stdout(repo_dir, ["shortlog", "-sne", ref]).strip()
    if not out:
        return []

    entries: list[tuple[int, str]] = []

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) != 2:
            continue

        try:
            commits = int(parts[0].strip())
        except ValueError:
            continue

        author_field = parts[1].strip()
        entries.append((commits, author_field))

    return entries


def _extract_email(author_field: str) -> str | None:
    if "<" in author_field and ">" in author_field:
        return author_field.split("<")[-1].split(">")[0].strip()
    return None


def _bus_factor_author_set(repo_dir: Path, threshold: float, ref: str = "HEAD") -> list[str]:
    """
    Returns the minimal contributor set whose cumulative commit share
    reaches the given threshold.
    """
    if threshold <= 0 or threshold > 1:
        raise ValueError("threshold must be > 0 and <= 1")

    entries = _shortlog_entries(repo_dir, ref)
    if not entries:
        return []

    total = sum(commits for commits, _ in entries)
    if total <= 0:
        return []

    target = total * threshold
    cumulative = 0
    selected: list[str] = []

    for commits, author_field in entries:
        selected.append(author_field)
        cumulative += commits
        if cumulative >= target:
            break

    return selected


def top_contributor_share(repo_dir: Path, ref: str = "HEAD") -> float:
    """
    Share of commits by top contributor (0..1).
    Uses shortlog -sne (counts commits per author).
    """
    entries = _shortlog_entries(repo_dir, ref)
    if not entries:
        return 0.0

    counts = [commits for commits, _ in entries]
    total = sum(counts)
    if total <= 0:
        return 0.0

    return max(counts) / total


def bus_factor_estimate(repo_dir: Path, threshold: float = 0.5, ref: str = "HEAD") -> int:
    """
    Minimal number of top contributors needed to reach 'threshold' of commits.
    This is a rough bus-factor proxy for MVP.
    """
    entries = _shortlog_entries(repo_dir, ref)
    if not entries:
        return 0

    counts = sorted((commits for commits, _ in entries), reverse=True)
    total = sum(counts)
    if total <= 0:
        return 0

    running = 0
    k = 0
    for c in counts:
        running += c
        k += 1
        if (running / total) >= threshold:
            return k
    return k


def security_files_presence(repo_dir: Path, ref: str = "HEAD") -> Dict[str, bool]:
    """
    Simple presence checks. Uses git ls-tree to check file presence without working tree.
    """
    files = {
        "SECURITY.md": False,
        "CODEOWNERS": False,
        ".github/dependabot.yml": False,
        ".github/workflows": False,
    }

    # Get all files in the tree
    out = git_stdout(repo_dir, ["ls-tree", "-r", "--name-only", ref]).strip()
    if not out:
        return files

    file_set = set(out.splitlines())

    if "SECURITY.md" in file_set:
        files["SECURITY.md"] = True
    if "CODEOWNERS" in file_set or ".github/CODEOWNERS" in file_set:
        files["CODEOWNERS"] = True
    if ".github/dependabot.yml" in file_set:
        files[".github/dependabot.yml"] = True
    if any(f.startswith(".github/workflows/") for f in file_set):
        files[".github/workflows"] = True

    return files


def commit_volatility(repo_dir: Path, ref: str = "HEAD") -> float | None:
    """
    Coefficient of variation of commits per month.
    Higher = more unstable activity.
    """
    import statistics
    from collections import Counter

    out = git_stdout(repo_dir, ["log", "--date=short", "--pretty=%ad", ref]).strip()
    if not out:
        return None

    months = [line[:7] for line in out.splitlines()]  # YYYY-MM
    counts = Counter(months)

    values = list(counts.values())
    if len(values) < 2:
        return 0.0

    mean = statistics.mean(values)
    if mean == 0:
        return 0.0

    stdev = statistics.stdev(values)
    return stdev / mean


def bus_factor_set_median_inactivity_days(repo_dir: Path, threshold: float = 0.5, ref: str = "HEAD") -> int | None:
    """
    Median inactivity (in days) among the minimal contributor set whose cumulative
    commit share reaches the given threshold.

    Example:
        threshold=0.5  -> contributors covering 50% of commits
        threshold=0.75 -> contributors covering 75% of commits
    """
    import statistics

    selected_authors = _bus_factor_author_set(repo_dir, threshold=threshold, ref=ref)
    if not selected_authors:
        return None

    head_ts_raw = git_stdout(repo_dir, ["show", "-s", "--format=%ct", ref]).strip()
    if not head_ts_raw:
        return None

    now_ts = int(head_ts_raw)
    inactivity_days: list[int] = []

    for author_field in selected_authors:
        email = _extract_email(author_field)

        if email:
            ts = git_stdout(
                repo_dir,
                ["log", "-1", "--format=%ct", f"--author={email}"]
            ).strip()
        else:
            ts = git_stdout(
                repo_dir,
                ["log", "-1", "--format=%ct", f"--author={author_field}"]
            ).strip()

        if not ts:
            continue

        last_ts = int(ts)
        inactivity_days.append(max(0, (now_ts - last_ts) // 86400))

    if not inactivity_days:
        return None

    return int(statistics.median(inactivity_days))


def release_cadence_days(repo_dir: Path) -> float | None:
    """
    Average days between tag creation dates.
    Returns None if fewer than 2 tags exist.
    """
    import statistics

    out = git_stdout(
        repo_dir,
        [
            "for-each-ref",
            "--sort=creatordate",
            "--format=%(creatordate:unix)",
            "refs/tags",
        ],
    ).strip()

    if not out:
        return None

    timestamps = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            timestamps.append(int(line))
        except ValueError:
            continue

    if len(timestamps) < 2:
        return None

    timestamps.sort()

    gaps = [
        (timestamps[i] - timestamps[i - 1]) / 86400
        for i in range(1, len(timestamps))
    ]

    return statistics.mean(gaps) if gaps else None

def recent_bus_factor_set_median_inactivity_days(
    repo_dir: Path,
    threshold: float = 0.5,
    window_days: int = 365,
    ref: str = "HEAD"
) -> int | None:
    """
    Median inactivity (in days) among the contributor set covering the given
    threshold of commits within the last `window_days`.

    Example:
        threshold=0.5 -> contributors responsible for 50% of recent commits
        threshold=0.75 -> contributors responsible for 75% of recent commits
    """
    import statistics
    from collections import Counter

    if threshold <= 0 or threshold > 1:
        raise ValueError("threshold must be > 0 and <= 1")

    since_arg = f"--since={window_days}.days"

    out = git_stdout(
        repo_dir,
        ["log", since_arg, "--format=%aN <%aE>", ref]
    ).strip()

    if not out:
        return None

    authors = [line.strip() for line in out.splitlines() if line.strip()]
    counts = Counter(authors)

    if not counts:
        return None

    total = sum(counts.values())
    target = total * threshold

    sorted_authors = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    cumulative = 0
    selected_authors = []

    for author, commits in sorted_authors:
        selected_authors.append(author)
        cumulative += commits
        if cumulative >= target:
            break

    head_ts_raw = git_stdout(repo_dir, ["show", "-s", "--format=%ct", "HEAD"]).strip()
    if not head_ts_raw:
        return None

    now_ts = int(head_ts_raw)
    inactivity_days = []

    for author_field in selected_authors:
        email = None
        if "<" in author_field and ">" in author_field:
            email = author_field.split("<")[-1].split(">")[0].strip()

        if email:
            ts = git_stdout(
                repo_dir,
                ["log", "-1", "--format=%ct", f"--author={email}"]
            ).strip()
        else:
            ts = git_stdout(
                repo_dir,
                ["log", "-1", "--format=%ct", f"--author={author_field}"]
            ).strip()

        if not ts:
            continue

        last_ts = int(ts)
        inactivity_days.append(max(0, (now_ts - last_ts) // 86400))

    if not inactivity_days:
        return None

    return int(statistics.median(inactivity_days))

def recent_release_cadence_days(repo_dir: Path, window_days: int = 365) -> float | None:
    """
    Average days between tags created within the last `window_days`.

    Returns None if fewer than 2 tags exist in the window.
    """
    import statistics
    import time

    now_ts = int(time.time())
    window_start = now_ts - (window_days * 86400)

    out = git_stdout(
        repo_dir,
        [
            "for-each-ref",
            "--sort=creatordate",
            "--format=%(creatordate:unix)",
            "refs/tags",
        ],
    ).strip()

    if not out:
        return None

    timestamps = []

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ts = int(line)
        except ValueError:
            continue

        if ts >= window_start:
            timestamps.append(ts)

    if len(timestamps) < 2:
        return None

    timestamps.sort()

    gaps = [
        (timestamps[i] - timestamps[i - 1]) / 86400
        for i in range(1, len(timestamps))
    ]

    return statistics.mean(gaps) if gaps else None

def collect_all_metrics(repo_dir: Path, ref: Optional[str] = None) -> Dict[str, Any]:
    from .gitops import get_ref_for_commands
    ref_str = get_ref_for_commands(repo_dir, ref)
    
    age = repo_age_days(repo_dir, ref_str)
    commits = commit_count(repo_dir, ref_str)
    contributors = contributor_count(repo_dir, ref_str)

    metrics: Dict[str, Any] = {
        "repo_age_days": age,
        "commit_count": commits,
        "contributor_count": contributors,
        "top_contributor_share": round(top_contributor_share(repo_dir, ref_str), 6),
        "bus_factor_50p": bus_factor_estimate(repo_dir, threshold=0.5, ref=ref_str),
        "bus_factor_75p": bus_factor_estimate(repo_dir, threshold=0.75, ref=ref_str),
        "commit_volatility": commit_volatility(repo_dir, ref_str),
        "bus_factor_50p_median_inactivity_days": bus_factor_set_median_inactivity_days(repo_dir, threshold=0.5, ref=ref_str),
        "bus_factor_75p_median_inactivity_days": bus_factor_set_median_inactivity_days(repo_dir, threshold=0.75, ref=ref_str),
        "release_cadence_days": release_cadence_days(repo_dir),
        "recent_release_cadence_days": recent_release_cadence_days(repo_dir, 365),
        "recent_bus_factor_50p_median_inactivity_days": recent_bus_factor_set_median_inactivity_days(repo_dir, 0.5, 365, ref_str),
        "recent_bus_factor_75p_median_inactivity_days": recent_bus_factor_set_median_inactivity_days(repo_dir, 0.75, 365, ref_str),
    }
    metrics.update({f"has_{k.replace('.', '_').replace('/', '_')}": v for k, v in security_files_presence(repo_dir, ref_str).items()})
    return metrics