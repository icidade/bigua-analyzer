from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from .gitops import git_stdout


AnalysisMode = Literal["full", "fast"]

_CACHE_VERSION = "v1"
T = TypeVar("T")


@dataclass(frozen=True)
class AnalysisConfig:
    mode: AnalysisMode = "full"
    since: str | None = None
    time_window_days: int | None = None
    sample_size: int | None = None
    cache_enabled: bool = True

    @classmethod
    def resolve(
        cls,
        mode: AnalysisMode = "full",
        since: str | None = None,
        time_window_days: int | None = None,
        sample_size: int | None = None,
        cache_enabled: bool = True,
    ) -> "AnalysisConfig":
        if since and time_window_days is not None:
            raise ValueError("Use either 'since' or 'time_window_days', not both.")
        if since is not None:
            datetime.strptime(since, "%Y-%m-%d")
        if time_window_days is not None and time_window_days <= 0:
            raise ValueError("time_window_days must be > 0.")
        if sample_size is not None and sample_size <= 0:
            raise ValueError("sample_size must be > 0.")

        resolved_window = time_window_days
        resolved_sample_size = sample_size
        resolved_since = since

        if mode == "fast":
            if resolved_since is None and resolved_window is None:
                resolved_window = 365
            if resolved_sample_size is None:
                resolved_sample_size = 240

        if resolved_since is None and resolved_window is not None:
            resolved_since = (datetime.now(timezone.utc).date() - timedelta(days=resolved_window)).isoformat()

        return cls(
            mode=mode,
            since=resolved_since,
            time_window_days=resolved_window,
            sample_size=resolved_sample_size,
            cache_enabled=cache_enabled,
        )

    @property
    def sampling_strategy(self) -> str:
        if self.sample_size is not None:
            return "time-bucket-sample"
        if self.since is not None:
            return "time-window"
        return "full-history"

    def git_since_args(self) -> list[str]:
        if self.since is None:
            return []
        return [f"--since={self.since}"]

    def cache_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommitMeta:
    commit: str
    timestamp: int
    author: str
    email: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommitScope:
    total_commits: int
    selected_commits: tuple[CommitMeta, ...]
    since: str | None
    sample_size: int | None
    sampling_strategy: str
    cache_hit: bool = False

    @property
    def analyzed_commits(self) -> int:
        return len(self.selected_commits)


def _cache_path(cache_dir: Path, namespace: str, key_payload: dict[str, Any]) -> Path:
    raw = json.dumps(
        {
            "namespace": namespace,
            "version": _CACHE_VERSION,
            "payload": key_payload,
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}.json"


def load_analysis_cache(cache_dir: Path | None, namespace: str, key_payload: dict[str, Any]) -> dict[str, Any] | None:
    if cache_dir is None:
        return None
    cache_file = _cache_path(cache_dir, namespace, key_payload)
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def store_analysis_cache(cache_dir: Path | None, namespace: str, key_payload: dict[str, Any], data: dict[str, Any]) -> None:
    if cache_dir is None:
        return
    cache_file = _cache_path(cache_dir, namespace, key_payload)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def resolve_ref_oid(repo_dir: Path, ref: str) -> str:
    return git_stdout(repo_dir, ["rev-parse", ref]).strip()


def _parse_commit_listing(output: str) -> list[CommitMeta]:
    entries: list[CommitMeta] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        commit, timestamp_raw, author, email = parts
        try:
            timestamp = int(timestamp_raw)
        except ValueError:
            continue
        entries.append(
            CommitMeta(
                commit=commit,
                timestamp=timestamp,
                author=author,
                email=email,
            )
        )
    return entries


def _list_scope_entries(
    repo_dir: Path,
    ref: str,
    config: AnalysisConfig,
    cache_dir: Path | None,
) -> tuple[list[CommitMeta], bool]:
    ref_oid = resolve_ref_oid(repo_dir, ref)
    key_payload = {
        "ref_oid": ref_oid,
        "config": config.cache_payload(),
    }
    cached = load_analysis_cache(cache_dir if config.cache_enabled else None, "commit-scope-list", key_payload)
    if cached is not None:
        return [CommitMeta(**entry) for entry in cached.get("entries", [])], True

    out = git_stdout(
        repo_dir,
        [
            "log",
            "--reverse",
            "--format=%H%x09%ct%x09%aN <%aE>%x09%aE",
            *config.git_since_args(),
            ref,
        ],
    ).strip()
    entries = _parse_commit_listing(out)
    store_analysis_cache(
        cache_dir if config.cache_enabled else None,
        "commit-scope-list",
        key_payload,
        {"entries": [entry.as_dict() for entry in entries]},
    )
    return entries, False


def _month_bucket(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m")


def _pick_evenly(items: list[T], count: int) -> list[T]:
    if count <= 0 or not items:
        return []
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[len(items) // 2]]

    indices: list[int] = []
    seen: set[int] = set()
    last_index = len(items) - 1
    for idx in range(count):
        candidate = round(idx * last_index / (count - 1))
        if candidate in seen:
            while candidate < len(items) and candidate in seen:
                candidate += 1
            if candidate >= len(items):
                candidate = max(index for index in range(len(items)) if index not in seen)
        seen.add(candidate)
        indices.append(candidate)
    indices.sort()
    return [items[index] for index in indices]


def _apply_time_bucket_sampling(entries: list[CommitMeta], sample_size: int | None) -> list[CommitMeta]:
    if sample_size is None or sample_size >= len(entries):
        return list(entries)

    bucket_order: list[str] = []
    buckets: dict[str, list[CommitMeta]] = {}
    for entry in entries:
        bucket = _month_bucket(entry.timestamp)
        if bucket not in buckets:
            buckets[bucket] = []
            bucket_order.append(bucket)
        buckets[bucket].append(entry)

    if sample_size < len(bucket_order):
        selected_buckets = set(_pick_evenly(bucket_order, sample_size))
        sampled: list[CommitMeta] = []
        for bucket in bucket_order:
            if bucket in selected_buckets:
                sampled.extend(_pick_evenly(buckets[bucket], 1))
        return sampled[:sample_size]

    allocations = {bucket: 1 for bucket in bucket_order}
    remaining = sample_size - len(bucket_order)
    expandable = sorted(bucket_order, key=lambda bucket: len(buckets[bucket]), reverse=True)
    while remaining > 0:
        progressed = False
        for bucket in expandable:
            if allocations[bucket] < len(buckets[bucket]):
                allocations[bucket] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            break

    sampled = []
    for bucket in bucket_order:
        sampled.extend(_pick_evenly(buckets[bucket], allocations[bucket]))
    return sampled[:sample_size]


def build_commit_scope(
    repo_dir: Path,
    ref: str,
    config: AnalysisConfig,
    cache_dir: Path | None = None,
) -> CommitScope:
    entries, cache_hit = _list_scope_entries(repo_dir, ref, config, cache_dir)
    selected = _apply_time_bucket_sampling(entries, config.sample_size)
    return CommitScope(
        total_commits=len(entries),
        selected_commits=tuple(selected),
        since=config.since,
        sample_size=config.sample_size,
        sampling_strategy=config.sampling_strategy,
        cache_hit=cache_hit,
    )