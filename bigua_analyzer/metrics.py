from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .ai.ai_influence import collect_repository_ai_data, compute_ai_influence_details
from .ai.ai_metrics import compute_ai_aware_metrics
from .gitops import git_stdout
from .sdlc import SDLCMode, resolve_effective_sdlc_mode


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

    # Get all commits with author and timestamp
    out = git_stdout(repo_dir, ["log", "--format=%aN <%aE> %ct", ref]).strip()
    if not out:
        return None

    # Build dict of author_field -> max ts
    author_last_commit: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: "Name <email> ts"
        parts = line.rsplit(' ', 1)
        if len(parts) != 2:
            continue
        author_field = parts[0]
        try:
            ts = int(parts[1])
            if author_field not in author_last_commit or ts > author_last_commit[author_field]:
                author_last_commit[author_field] = ts
        except ValueError:
            continue

    inactivity_days: list[int] = []
    for author_field in selected_authors:
        if author_field in author_last_commit:
            last_ts = author_last_commit[author_field]
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

    # Get all commits with author and timestamp (no since filter for last commit)
    out = git_stdout(repo_dir, ["log", "--format=%aN <%aE> %ct", ref]).strip()
    if not out:
        return None

    # Build dict of author_field -> max ts
    author_last_commit: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(' ', 1)
        if len(parts) != 2:
            continue
        author_field = parts[0]
        try:
            ts = int(parts[1])
            if author_field not in author_last_commit or ts > author_last_commit[author_field]:
                author_last_commit[author_field] = ts
        except ValueError:
            continue

    inactivity_days = []
    for author_field in selected_authors:
        if author_field in author_last_commit:
            last_ts = author_last_commit[author_field]
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

def gini_coefficient(repo_dir: Path, ref: str = "HEAD") -> float | None:
    """
    Gini coefficient for commit distribution among contributors.
    Measures inequality: 0 = perfect equality, 1 = perfect inequality.
    """
    entries = _shortlog_entries(repo_dir, ref)
    if not entries:
        return None

    commits = [count for count, _ in entries]
    if len(commits) < 2:
        return 0.0

    commits.sort()
    n = len(commits)
    total = sum(commits)
    if total == 0:
        return 0.0

    cumulative = 0
    for i, x in enumerate(commits):
        cumulative += x * (i + 1)

    mean = total / n
    gini = (2 * cumulative) / (n * total) - (n + 1) / n
    return max(0.0, min(1.0, gini))


def developer_turnover(repo_dir: Path, inactive_days: int = 365, ref: str = "HEAD") -> float | None:
    """
    Proportion of contributors inactive for more than `inactive_days`.
    Turnover proxy: inactive_contributors / total_contributors
    """
    total_contributors = contributor_count(repo_dir, ref)
    if total_contributors == 0:
        return None

    head_ts_raw = git_stdout(repo_dir, ["show", "-s", "--format=%ct", ref]).strip()
    if not head_ts_raw:
        return None

    now_ts = int(head_ts_raw)
    threshold_ts = now_ts - (inactive_days * 86400)

    # Get all commits with author email and timestamp in one go
    out = git_stdout(repo_dir, ["log", "--format=%aE %ct", ref]).strip()
    if not out:
        return 0.0

    # Build a dict of email -> max timestamp
    author_last_commit: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            email = parts[0]
            ts = int(parts[1])
            if email not in author_last_commit or ts > author_last_commit[email]:
                author_last_commit[email] = ts
        except ValueError:
            continue

    # Count inactive contributors
    inactive_count = sum(1 for last_ts in author_last_commit.values() if last_ts < threshold_ts)

    return inactive_count / total_contributors

def collect_all_metrics(repo_dir: Path, ref: Optional[str] = None, sdlc_mode: SDLCMode = "auto") -> Dict[str, Any]:
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
        "gini_coefficient": gini_coefficient(repo_dir, ref_str),
        "developer_turnover": developer_turnover(repo_dir, 365, ref_str),
    }
    metrics.update({f"has_{k.replace('.', '_').replace('/', '_')}": v for k, v in security_files_presence(repo_dir, ref_str).items()})

    repo_data = collect_repository_ai_data(repo_dir, ref_str)
    repo_data["repo_age_days"] = age
    repo_data["commit_count"] = commits
    repo_data["contributor_count"] = contributors
    ai_details = compute_ai_influence_details(repo_data)
    effective_sdlc_mode = resolve_effective_sdlc_mode(sdlc_mode, ai_details.ai_influence_score)

    metrics.update(
        {
            "sdlc_mode": sdlc_mode,
            "effective_sdlc_mode": effective_sdlc_mode,
            "ai_influence_score": round(ai_details.ai_influence_score, 6),
            "ai_influence_confidence": round(ai_details.ai_influence_confidence, 6),
            "ai_weighted_base_score": round(ai_details.weighted_base_score, 6),
            "ai_temporal_adoption_prior": round(ai_details.temporal_adoption_prior, 6),
            "ai_temporal_anomaly_weight": round(ai_details.temporal_anomaly_weight, 6),
            "ai_dominant_activity_period": ai_details.dominant_activity_period,
            "ai_historical_constraint_applied": ai_details.historical_constraint_applied,
            "ai_legacy_variance_protection_applied": ai_details.legacy_variance_protection_applied,
            "ai_influence_rationale": ai_details.ai_influence_rationale,
            "ai_h1_textual_markers": None if ai_details.ai_h1_textual_markers is None else round(ai_details.ai_h1_textual_markers, 6),
            "ai_h2_explicit_attribution": None if ai_details.ai_h2_explicit_attribution is None else round(ai_details.ai_h2_explicit_attribution, 6),
            "ai_h3_temporal_prior": round(ai_details.ai_h3_temporal_prior, 6),
            "ai_h4_burstiness": None if ai_details.ai_h4_burstiness is None else round(ai_details.ai_h4_burstiness, 6),
            "ai_h5_style_shift": None if ai_details.ai_h5_style_shift is None else round(ai_details.ai_h5_style_shift, 6),
            "ai_h6_large_low_discussion": None if ai_details.ai_h6_large_low_discussion is None else round(ai_details.ai_h6_large_low_discussion, 6),
            "ai_h7_output_asymmetry": None if ai_details.ai_h7_output_asymmetry is None else round(ai_details.ai_h7_output_asymmetry, 6),
            "ai_h8_tooling_footprint": None if ai_details.ai_h8_tooling_footprint is None else round(ai_details.ai_h8_tooling_footprint, 6),
            "ai_h9_generated_text_pattern": None if ai_details.ai_h9_generated_text_pattern is None else round(ai_details.ai_h9_generated_text_pattern, 6),
            "ai_commit_pattern_score": None if ai_details.commit_pattern_score is None else round(ai_details.commit_pattern_score, 6),
            "ai_temporal_anomaly_score": None if ai_details.temporal_anomaly_score is None else round(ai_details.temporal_anomaly_score, 6),
            "ai_temporal_anomaly_score_raw": None if ai_details.temporal_anomaly_score_raw is None else round(ai_details.temporal_anomaly_score_raw, 6),
            "ai_style_uniformity_score": None if ai_details.style_uniformity_score is None else round(ai_details.style_uniformity_score, 6),
            "ai_metadata_signal_score": None if ai_details.metadata_signal_score is None else round(ai_details.metadata_signal_score, 6),
        }
    )

    if effective_sdlc_mode in {"hybrid", "ai"}:
        metrics["ai_metrics"] = compute_ai_aware_metrics(metrics, ai_details, effective_sdlc_mode)

    return metrics