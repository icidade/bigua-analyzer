from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional


class GitError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        raise GitError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout or ""


def stable_repo_dir(cache_dir: Path, repo_url: str) -> Path:
    h = hashlib.sha256(repo_url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / h


def ensure_cloned(repo_url: str, cache_dir: Path) -> Path:
    """
    Clone repo to a stable cache path (based on URL hash).
    If already cloned, fetch updates.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = stable_repo_dir(cache_dir, repo_url)

    if not repo_dir.exists():
        _run(["git", "clone", "--no-tags", "--filter=blob:none", repo_url, str(repo_dir)])
    else:
        # Update existing clone
        _run(["git", "fetch", "--all", "--prune"], cwd=repo_dir)

    return repo_dir


def checkout_ref(repo_dir: Path, ref: Optional[str]) -> None:
    if not ref:
        return
    # Try to checkout ref (branch/tag/sha)
    _run(["git", "checkout", "--force", ref], cwd=repo_dir)


def git_stdout(repo_dir: Path, args: list[str]) -> str:
    return _run(["git", *args], cwd=repo_dir)