from __future__ import annotations

from collections import Counter
from pathlib import Path
import statistics
from typing import Any, Dict, Optional

from .analysis_scope import AnalysisConfig, CommitScope, build_commit_scope
from .ai.ai_influence import collect_repository_ai_data, compute_ai_influence_details
from .ai.ai_metrics import compute_ai_aware_metrics
from .gitops import git_stdout
from .perf import PerformanceRecorder
from .sdlc import SDLCMode, resolve_effective_sdlc_mode

_FAST_WINDOW_FALLBACKS = (365, 730, 1095)
_CLASSIFICATION_THRESHOLDS = (0.30, 0.60)
_TRAFFIC_LIGHT_SCORES = {
    "green": 3,
    "yellow": 2,
    "orange": 1,
    "red": 0,
}


def _recent_signal_strength(analyzed_commits: int) -> str:
    if analyzed_commits >= 150:
        return "strong"
    if analyzed_commits >= 50:
        return "moderate"
    if analyzed_commits >= 1:
        return "weak"
    return "insufficient"


def _clone_analysis_config(base_config: AnalysisConfig, *, time_window_days: int) -> AnalysisConfig:
    return AnalysisConfig.resolve(
        mode=base_config.mode,
        time_window_days=time_window_days,
        sample_size=base_config.sample_size,
        cache_enabled=base_config.cache_enabled,
    )


def _fast_window_candidates(base_config: AnalysisConfig) -> list[int]:
    requested_window = base_config.time_window_days or 365
    candidates = [requested_window]
    for fallback_window in _FAST_WINDOW_FALLBACKS:
        if fallback_window > requested_window and fallback_window not in candidates:
            candidates.append(fallback_window)
    return candidates


def _resolve_fast_analysis_scope(
    repo_dir: Path,
    ref: str,
    analysis_config: AnalysisConfig,
    cache_dir: Path | None,
) -> tuple[AnalysisConfig, CommitScope, bool]:
    commit_scope = build_commit_scope(repo_dir, ref, analysis_config, cache_dir=cache_dir)
    if analysis_config.mode != "fast" or analysis_config.time_window_days is None:
        return analysis_config, commit_scope, False

    effective_config = analysis_config
    expanded = False
    for window_days in _fast_window_candidates(analysis_config)[1:]:
        if _recent_signal_strength(commit_scope.analyzed_commits) not in {"weak", "insufficient"}:
            break
        effective_config = _clone_analysis_config(analysis_config, time_window_days=window_days)
        commit_scope = build_commit_scope(repo_dir, ref, effective_config, cache_dir=cache_dir)
        expanded = True
        if _recent_signal_strength(commit_scope.analyzed_commits) != "insufficient":
            break

    return effective_config, commit_scope, expanded


def _sample_size_used(scope: CommitScope) -> int:
    if scope.sample_size is None:
        return scope.analyzed_commits
    return min(scope.sample_size, scope.total_commits)


def _classification_status_from_mode(effective_mode: str) -> str:
    mapping = {
        "human": "HUMAN",
        "hybrid": "HYBRID",
        "ai": "AI_DRIVEN",
        "insufficient_recent_data": "insufficient_recent_data",
    }
    return mapping.get(effective_mode, str(effective_mode))


def _nearest_threshold_distance(score: float | None) -> float | None:
    if score is None:
        return None
    return min(abs(float(score) - threshold) for threshold in _CLASSIFICATION_THRESHOLDS)


def _downgrade_confidence(level: str) -> str:
    order = ["very_low", "low", "moderate", "high"]
    try:
        index = order.index(level)
    except ValueError:
        return level
    return order[max(0, index - 1)]


def _metadata_anomaly_detected(
    scope: CommitScope,
    contributor_total: int,
    top_contributor_share: float | None,
    bus_factor_50p: int,
) -> bool:
    if scope.analyzed_commits <= 0:
        return False

    identities = [entry.author.strip() for entry in scope.selected_commits if entry.author.strip()]
    if not identities:
        return True
    if contributor_total == 0:
        return True
    if bus_factor_50p == 0:
        return True
    return False


def _metric_reliability_warning(
    analyzed_commits: int,
    window_expanded: bool,
) -> bool:
    """Returns True when the sample is analytically fragile but not structurally contradictory.

    Distinct from metadata_anomaly_detected, which is reserved for internally inconsistent
    outputs. This flag captures borderline cases: very small samples and expansions that
    did not materially improve signal.
    """
    # Extremely small sample — too few to support any distributional inference
    if 0 < analyzed_commits < 15:
        return True
    # Window expansion was applied but the resulting sample is still limited;
    # the expanded window trades recency for quantity with no strong guarantee of either
    if window_expanded and analyzed_commits < 50:
        return True
    return False


def compute_traffic_light(row: Dict[str, Any]) -> str:
    """Return a stable signal-quality label from already computed fields.

    Priority order:
    1. red
    2. orange
    3. yellow
    4. green
    """
    insufficient_recent_data = bool(row.get("insufficient_recent_data"))
    metadata_anomaly_detected = bool(row.get("metadata_anomaly_detected"))
    low_recent_signal = bool(row.get("low_recent_signal"))
    metric_reliability_warning = bool(row.get("metric_reliability_warning"))
    window_expanded = bool(row.get("window_expanded"))
    recent_signal_strength = row.get("recent_signal_strength")
    classification_confidence = row.get("classification_confidence")

    if insufficient_recent_data or metadata_anomaly_detected:
        return "red"

    if (
        low_recent_signal
        or classification_confidence in {"low", "very_low"}
        or metric_reliability_warning
    ):
        return "orange"

    if (
        recent_signal_strength == "moderate"
        or classification_confidence == "moderate"
        or window_expanded
    ):
        return "yellow"

    return "green"


def _signal_quality_fields(
    *,
    selected_mode: SDLCMode,
    effective_mode: str,
    ai_score: float,
    analysis_config: AnalysisConfig,
    commit_scope: CommitScope,
    window_expanded: bool,
    contributor_total: int,
    top_contributor_share: float | None,
    bus_factor_50p: int,
) -> Dict[str, Any]:
    analyzed_commits = commit_scope.analyzed_commits
    candidate_recent_commits = commit_scope.total_commits
    recent_signal_strength = _recent_signal_strength(analyzed_commits)
    low_recent_signal = analyzed_commits < 50
    insufficient_recent_data = analyzed_commits == 0
    metadata_anomaly_detected = _metadata_anomaly_detected(
        commit_scope,
        contributor_total=contributor_total,
        top_contributor_share=top_contributor_share,
        bus_factor_50p=bus_factor_50p,
    )
    metric_reliability_warning = _metric_reliability_warning(analyzed_commits, window_expanded)
    threshold_distance = _nearest_threshold_distance(ai_score)
    classification_guardrail_applied = bool(
        threshold_distance is not None
        and threshold_distance < 0.05
        and recent_signal_strength != "strong"
        and not insufficient_recent_data
    )

    if insufficient_recent_data:
        classification_confidence = "insufficient"
    elif analyzed_commits < 20:
        classification_confidence = "very_low"
    elif recent_signal_strength == "weak":
        classification_confidence = "low"
    elif recent_signal_strength == "moderate":
        classification_confidence = "moderate"
    else:
        classification_confidence = "high"

    if metadata_anomaly_detected and classification_confidence not in {"insufficient", "very_low"}:
        classification_confidence = _downgrade_confidence(classification_confidence)
    if classification_guardrail_applied and classification_confidence not in {"insufficient", "very_low"}:
        classification_confidence = _downgrade_confidence(classification_confidence)
    if metric_reliability_warning and classification_confidence not in {"insufficient", "very_low"}:
        classification_confidence = _downgrade_confidence(classification_confidence)

    rerun_full_needed = (
        low_recent_signal
        or insufficient_recent_data
        or classification_guardrail_applied
        or metric_reliability_warning
    )
    if rerun_full_needed and metadata_anomaly_detected:
        recommended_validation_mode = "rerun_full_and_metadata_review"
    elif rerun_full_needed:
        recommended_validation_mode = "rerun_full"
    elif metadata_anomaly_detected:
        recommended_validation_mode = "metadata_review"
    else:
        recommended_validation_mode = "none"

    if insufficient_recent_data:
        data_quality_status = "insufficient_recent_data"
        effective_classification_mode = "insufficient_recent_data"
    elif metadata_anomaly_detected:
        data_quality_status = "metadata_review_recommended"
        effective_classification_mode = effective_mode
    elif metric_reliability_warning:
        data_quality_status = "screening_grade_review_recommended"
        effective_classification_mode = effective_mode
    elif recent_signal_strength == "weak":
        data_quality_status = "screening_grade_low_signal"
        effective_classification_mode = effective_mode
    elif recent_signal_strength == "moderate" or classification_guardrail_applied:
        data_quality_status = "screening_grade"
        effective_classification_mode = effective_mode
    else:
        data_quality_status = "research_grade_screening"
        effective_classification_mode = effective_mode

    traffic_light_row = {
        "recent_signal_strength": recent_signal_strength,
        "classification_confidence": classification_confidence,
        "window_expanded": window_expanded,
        "low_recent_signal": low_recent_signal,
        "insufficient_recent_data": insufficient_recent_data,
        "metadata_anomaly_detected": metadata_anomaly_detected,
        "metric_reliability_warning": metric_reliability_warning,
    }
    traffic_light = compute_traffic_light(traffic_light_row)
    traffic_light_score = _TRAFFIC_LIGHT_SCORES[traffic_light]
    is_research_grade = traffic_light == "green"

    return {
        "analysis_mode": analysis_config.mode,
        "analysis_window_days": analysis_config.time_window_days,
        "window_expanded": window_expanded,
        "candidate_recent_commits": candidate_recent_commits,
        "analyzed_commits": analyzed_commits,
        "sample_size_used": _sample_size_used(commit_scope),
        "recent_signal_strength": recent_signal_strength,
        "classification_status": _classification_status_from_mode(effective_classification_mode),
        "classification_confidence": classification_confidence,
        "data_quality_status": data_quality_status,
        "recommended_validation_mode": recommended_validation_mode,
        "low_recent_signal": low_recent_signal,
        "insufficient_recent_data": insufficient_recent_data,
        "metadata_anomaly_detected": metadata_anomaly_detected,
        "classification_guardrail_applied": classification_guardrail_applied,
            "metric_reliability_warning": metric_reliability_warning,
        "traffic_light": traffic_light,
        "traffic_light_score": traffic_light_score,
        "is_research_grade": is_research_grade,
        "effective_sdlc_mode": effective_classification_mode,
        "selected_sdlc_mode": selected_mode,
    }


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


def _top_contributor_share_from_scope(scope: CommitScope) -> float:
    counts = Counter(entry.author for entry in scope.selected_commits if entry.author)
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    return max(counts.values()) / total


def _bus_factor_from_scope(scope: CommitScope, threshold: float) -> int:
    counts = Counter(entry.author for entry in scope.selected_commits if entry.author)
    if not counts:
        return 0

    total = sum(counts.values())
    if total <= 0:
        return 0

    running = 0
    contributors = 0
    for commit_total in sorted(counts.values(), reverse=True):
        running += commit_total
        contributors += 1
        if (running / total) >= threshold:
            return contributors
    return contributors


def _commit_volatility_from_scope(scope: CommitScope) -> float | None:
    if not scope.selected_commits:
        return None

    month_counts = Counter()
    for entry in scope.selected_commits:
        month_counts[entry.timestamp // (30 * 86400)] += 1

    values = list(month_counts.values())
    if len(values) < 2:
        return 0.0

    mean = statistics.mean(values)
    if mean == 0:
        return 0.0

    return statistics.stdev(values) / mean


def _author_last_commit_timestamps(scope: CommitScope) -> dict[str, int]:
    author_last_commit: dict[str, int] = {}
    for entry in scope.selected_commits:
        if not entry.author:
            continue
        current = author_last_commit.get(entry.author)
        if current is None or entry.timestamp > current:
            author_last_commit[entry.author] = entry.timestamp
    return author_last_commit


def _email_last_commit_timestamps(scope: CommitScope) -> dict[str, int]:
    email_last_commit: dict[str, int] = {}
    for entry in scope.selected_commits:
        if not entry.email:
            continue
        current = email_last_commit.get(entry.email)
        if current is None or entry.timestamp > current:
            email_last_commit[entry.email] = entry.timestamp
    return email_last_commit


def _head_timestamp(repo_dir: Path, ref: str) -> int | None:
    raw = git_stdout(repo_dir, ["show", "-s", "--format=%ct", ref]).strip()
    if not raw:
        return None
    return int(raw)


def _median_inactivity_days(scope: CommitScope, threshold: float, head_ts: int | None) -> int | None:
    if head_ts is None:
        return None

    counts = Counter(entry.author for entry in scope.selected_commits if entry.author)
    if not counts:
        return None

    total = sum(counts.values())
    target = total * threshold
    running = 0
    selected_authors: list[str] = []
    for author, commit_total in counts.most_common():
        selected_authors.append(author)
        running += commit_total
        if running >= target:
            break

    author_last_commit = _author_last_commit_timestamps(scope)
    inactivity_days = [
        max(0, (head_ts - author_last_commit[author]) // 86400)
        for author in selected_authors
        if author in author_last_commit
    ]
    if not inactivity_days:
        return None
    return int(statistics.median(inactivity_days))


def _gini_from_scope(scope: CommitScope) -> float | None:
    counts = sorted(Counter(entry.author for entry in scope.selected_commits if entry.author).values())
    if not counts:
        return None
    if len(counts) < 2:
        return 0.0

    total = sum(counts)
    if total == 0:
        return 0.0

    cumulative = 0
    for index, value in enumerate(counts, start=1):
        cumulative += value * index
    gini = (2 * cumulative) / (len(counts) * total) - (len(counts) + 1) / len(counts)
    return max(0.0, min(1.0, gini))


def _developer_turnover_from_scope(scope: CommitScope, total_contributors: int, inactive_days: int, head_ts: int | None) -> float | None:
    if total_contributors == 0 or head_ts is None:
        return None

    threshold_ts = head_ts - (inactive_days * 86400)
    email_last_commit = _email_last_commit_timestamps(scope)
    if not email_last_commit:
        return 0.0

    inactive_count = sum(1 for timestamp in email_last_commit.values() if timestamp < threshold_ts)
    return inactive_count / total_contributors


def _recent_scope_config(base_config: AnalysisConfig) -> AnalysisConfig:
    recent_cutoff = AnalysisConfig.resolve(mode="full", time_window_days=365).since
    if base_config.since is not None and recent_cutoff is not None:
        recent_cutoff = max(base_config.since, recent_cutoff)
    return AnalysisConfig.resolve(
        mode=base_config.mode,
        since=recent_cutoff,
        sample_size=base_config.sample_size,
        cache_enabled=base_config.cache_enabled,
    )

def collect_all_metrics(
    repo_dir: Path,
    ref: Optional[str] = None,
    sdlc_mode: SDLCMode = "auto",
    profiler: Optional[PerformanceRecorder] = None,
    analysis_config: Optional[AnalysisConfig] = None,
    analysis_cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    from .gitops import get_ref_for_commands
    analysis_config = analysis_config or AnalysisConfig.resolve()
    if profiler is not None:
        with profiler.track("resolve_ref_ms"):
            ref_str = get_ref_for_commands(repo_dir, ref)
    else:
        ref_str = get_ref_for_commands(repo_dir, ref)
    
    if profiler is not None:
        with profiler.track("repository_basics_ms"):
            age = repo_age_days(repo_dir, ref_str)
            commits = commit_count(repo_dir, ref_str)
            contributors = contributor_count(repo_dir, ref_str)
            head_ts = _head_timestamp(repo_dir, ref_str)
    else:
        age = repo_age_days(repo_dir, ref_str)
        commits = commit_count(repo_dir, ref_str)
        contributors = contributor_count(repo_dir, ref_str)
        head_ts = _head_timestamp(repo_dir, ref_str)

    effective_analysis_config, commit_scope, window_expanded = _resolve_fast_analysis_scope(
        repo_dir,
        ref_str,
        analysis_config,
        analysis_cache_dir,
    )
    recent_scope = build_commit_scope(
        repo_dir,
        ref_str,
        _recent_scope_config(effective_analysis_config),
        cache_dir=analysis_cache_dir,
    )

    top_contributor_share = round(_top_contributor_share_from_scope(commit_scope), 6)
    bus_factor_50p = _bus_factor_from_scope(commit_scope, threshold=0.5)
    bus_factor_75p = _bus_factor_from_scope(commit_scope, threshold=0.75)
    commit_volatility = _commit_volatility_from_scope(commit_scope)
    bus_factor_50p_median_inactivity_days = _median_inactivity_days(commit_scope, threshold=0.5, head_ts=head_ts)
    bus_factor_75p_median_inactivity_days = _median_inactivity_days(commit_scope, threshold=0.75, head_ts=head_ts)
    recent_bus_factor_50p_median_inactivity_days = _median_inactivity_days(recent_scope, 0.5, head_ts=head_ts)
    recent_bus_factor_75p_median_inactivity_days = _median_inactivity_days(recent_scope, 0.75, head_ts=head_ts)
    gini_coefficient = _gini_from_scope(commit_scope)
    developer_turnover = _developer_turnover_from_scope(commit_scope, contributors, 365, head_ts)

    if profiler is not None:
        with profiler.track("standard_metric_calculation_ms"):
            metrics: Dict[str, Any] = {
                "repo_age_days": age,
                "commit_count": commits,
                "contributor_count": contributors,
                "top_contributor_share": top_contributor_share,
                "bus_factor_50p": bus_factor_50p,
                "bus_factor_75p": bus_factor_75p,
                "commit_volatility": commit_volatility,
                "bus_factor_50p_median_inactivity_days": bus_factor_50p_median_inactivity_days,
                "bus_factor_75p_median_inactivity_days": bus_factor_75p_median_inactivity_days,
                "release_cadence_days": release_cadence_days(repo_dir),
                "recent_release_cadence_days": recent_release_cadence_days(repo_dir, 365),
                "recent_bus_factor_50p_median_inactivity_days": recent_bus_factor_50p_median_inactivity_days,
                "recent_bus_factor_75p_median_inactivity_days": recent_bus_factor_75p_median_inactivity_days,
                "gini_coefficient": gini_coefficient,
                "developer_turnover": developer_turnover,
            }
            metrics.update({f"has_{k.replace('.', '_').replace('/', '_')}": v for k, v in security_files_presence(repo_dir, ref_str).items()})
    else:
        metrics = {
            "repo_age_days": age,
            "commit_count": commits,
            "contributor_count": contributors,
            "top_contributor_share": top_contributor_share,
            "bus_factor_50p": bus_factor_50p,
            "bus_factor_75p": bus_factor_75p,
            "commit_volatility": commit_volatility,
            "bus_factor_50p_median_inactivity_days": bus_factor_50p_median_inactivity_days,
            "bus_factor_75p_median_inactivity_days": bus_factor_75p_median_inactivity_days,
            "release_cadence_days": release_cadence_days(repo_dir),
            "recent_release_cadence_days": recent_release_cadence_days(repo_dir, 365),
            "recent_bus_factor_50p_median_inactivity_days": recent_bus_factor_50p_median_inactivity_days,
            "recent_bus_factor_75p_median_inactivity_days": recent_bus_factor_75p_median_inactivity_days,
            "gini_coefficient": gini_coefficient,
            "developer_turnover": developer_turnover,
        }
        metrics.update({f"has_{k.replace('.', '_').replace('/', '_')}": v for k, v in security_files_presence(repo_dir, ref_str).items()})

    metrics.update(
        {
            "analysis_mode": effective_analysis_config.mode,
            "analysis_since": effective_analysis_config.since,
            "analysis_time_window_days": effective_analysis_config.time_window_days,
            "analysis_sample_size": effective_analysis_config.sample_size,
            "analysis_sampling_strategy": commit_scope.sampling_strategy,
            "analysis_cache_enabled": effective_analysis_config.cache_enabled,
            "analysis_cache_hit": commit_scope.cache_hit,
            "commit_scope_total_commits": commit_scope.total_commits,
            "commit_scope_analyzed_commits": commit_scope.analyzed_commits,
            "commit_scope_is_approximate": commit_scope.analyzed_commits < commit_scope.total_commits,
        }
    )

    if sdlc_mode == "human":
        # Skip expensive full-history AI data collection when mode is explicitly human.
        repo_data = {
            "commits": [],
            "file_paths": [],
        }
    else:
        repo_data = collect_repository_ai_data(
            repo_dir,
            ref_str,
            profiler=profiler,
            analysis_config=effective_analysis_config,
            cache_dir=analysis_cache_dir,
        )

    repo_data["repo_age_days"] = age
    repo_data["commit_count"] = commits
    repo_data["contributor_count"] = contributors
    repo_data["commit_scope_total_commits"] = commit_scope.total_commits
    repo_data["commit_scope_analyzed_commits"] = commit_scope.analyzed_commits
    repo_data["analysis_mode"] = effective_analysis_config.mode
    ai_details = compute_ai_influence_details(repo_data, profiler=profiler)
    effective_sdlc_mode = resolve_effective_sdlc_mode(sdlc_mode, ai_details.ai_influence_score)
    signal_quality = _signal_quality_fields(
        selected_mode=sdlc_mode,
        effective_mode=effective_sdlc_mode,
        ai_score=ai_details.ai_influence_score,
        analysis_config=effective_analysis_config,
        commit_scope=commit_scope,
        window_expanded=window_expanded,
        contributor_total=contributors,
        top_contributor_share=top_contributor_share,
        bus_factor_50p=bus_factor_50p,
    )
    effective_sdlc_mode = str(signal_quality["effective_sdlc_mode"])

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
    metrics.update(signal_quality)

    if effective_sdlc_mode in {"hybrid", "ai"}:
        if profiler is not None:
            with profiler.track("ai_metrics_aggregation_ms"):
                metrics["ai_metrics"] = compute_ai_aware_metrics(metrics, ai_details, effective_sdlc_mode)
        else:
            metrics["ai_metrics"] = compute_ai_aware_metrics(metrics, ai_details, effective_sdlc_mode)

    return metrics