from __future__ import annotations

from pathlib import Path

from .gitops import GitError, checkout_ref, ensure_cloned
from .metrics import collect_all_metrics
from .types import RepoResult, RepoSpec


def analyze_repo(repo: RepoSpec, cache_dir: Path) -> RepoResult:
    """
    Core: analyze exactly ONE repo.
    CLI/app decides whether it's single-run or batch dataset.
    """
    try:
        repo_dir = ensure_cloned(repo.url, cache_dir=cache_dir)
        checkout_ref(repo_dir, repo.ref)
        metrics = collect_all_metrics(repo_dir)
        return RepoResult(repo=repo, ok=True, metrics=metrics)
    except (GitError, Exception) as e:
        return RepoResult(repo=repo, ok=False, error=str(e))