from __future__ import annotations

import threading
from pathlib import Path

from .analysis_scope import AnalysisConfig
from .gitops import GitError, checkout_ref, ensure_cloned
from .metrics import collect_all_metrics
from .models import RepoResult, RepoSpec
from .perf import PerformanceRecorder
from .sdlc import SDLCMode


# Global lock for shared cache operations (cloning)
cache_lock = threading.Lock()


def analyze_repo(
    repo: RepoSpec,
    cache_dir: Path,
    sdlc_mode: SDLCMode = "auto",
    emit_performance: bool = False,
    analysis_config: AnalysisConfig | None = None,
) -> RepoResult:
    """
    Core: analyze exactly ONE repo.
    CLI/app decides whether it's single-run or batch dataset.
    """
    analysis_config = analysis_config or AnalysisConfig.resolve()
    profiler = PerformanceRecorder() if emit_performance else None
    try:
        if profiler is not None:
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
                        analysis_config=analysis_config,
                        analysis_cache_dir=cache_dir / "analysis",
                    )
            metrics["performance"] = profiler.snapshot_ms()
        else:
            with cache_lock:
                repo_dir = ensure_cloned(repo.url, cache_dir=cache_dir)

            checkout_ref(repo_dir, repo.ref)
            metrics = collect_all_metrics(
                repo_dir,
                repo.ref,
                sdlc_mode=sdlc_mode,
                profiler=None,
                analysis_config=analysis_config,
                analysis_cache_dir=cache_dir / "analysis",
            )
        return RepoResult(repo=repo, ok=True, metrics=metrics)
    except (GitError, Exception) as e:
        return RepoResult(repo=repo, ok=False, error=str(e))