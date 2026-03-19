from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from .gitops import GitError, checkout_ref, ensure_cloned
from .metrics import collect_all_metrics
from .models import RepoResult, RepoSpec
from .sdlc import SDLCMode


# Global lock for shared cache operations (cloning)
cache_lock = threading.Lock()


def _format_elapsed(start_time: float) -> str:
    elapsed_seconds = max(0, int(time.time() - start_time))
    minutes, seconds = divmod(elapsed_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _print_step(step: int, total: int, message: str, start_time: float) -> None:
    elapsed = _format_elapsed(start_time)
    print(f"[progress] Step {step}/{total}: {message} (elapsed: {elapsed})", file=sys.stderr, flush=True)


def analyze_repo(repo: RepoSpec, cache_dir: Path, sdlc_mode: SDLCMode = "auto") -> RepoResult:
    """
    Core: analyze exactly ONE repo.
    CLI/app decides whether it's single-run or batch dataset.
    """
    start_time = time.time()
    try:
        _print_step(1, 3, f"Preparing repository cache for {repo.url}", start_time)
        with cache_lock:
            repo_dir = ensure_cloned(repo.url, cache_dir=cache_dir)

        _print_step(2, 3, "Resolving repository reference", start_time)
        checkout_ref(repo_dir, repo.ref)

        _print_step(3, 3, "Collecting repository metrics", start_time)
        metrics = collect_all_metrics(repo_dir, repo.ref, sdlc_mode=sdlc_mode)
        return RepoResult(repo=repo, ok=True, metrics=metrics)
    except (GitError, Exception) as e:
        return RepoResult(repo=repo, ok=False, error=str(e))