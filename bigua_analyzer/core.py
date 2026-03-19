from __future__ import annotations

import threading
from pathlib import Path

from .gitops import GitError, checkout_ref, ensure_cloned
from .metrics import collect_all_metrics
from .models import RepoResult, RepoSpec
from .perf import PerformanceRecorder
from .sdlc import SDLCMode


# Global lock for shared cache operations (cloning)
cache_lock = threading.Lock()


def analyze_repo(repo: RepoSpec, cache_dir: Path, sdlc_mode: SDLCMode = "auto") -> RepoResult:
    """
    Core: analyze exactly ONE repo.
    CLI/app decides whether it's single-run or batch dataset.
    """
    profiler = PerformanceRecorder()
    try:
        with profiler.track("total_analysis_ms"):
            with cache_lock:
                with profiler.track("clone_fetch_ms"):
                    repo_dir = ensure_cloned(repo.url, cache_dir=cache_dir)

            with profiler.track("checkout_ref_ms"):
                checkout_ref(repo_dir, repo.ref)

            with profiler.track("metrics_collection_ms"):
                metrics = collect_all_metrics(
                    repo_dir,
                    repo.ref,
                    sdlc_mode=sdlc_mode,
                    profiler=profiler,
                )
        metrics["performance"] = profiler.snapshot_ms()
        return RepoResult(repo=repo, ok=True, metrics=metrics)
    except (GitError, Exception) as e:
        return RepoResult(repo=repo, ok=False, error=str(e))