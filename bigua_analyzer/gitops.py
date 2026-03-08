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
    Uses bare repository to avoid working tree issues.
    If already cloned, fetch updates.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = stable_repo_dir(cache_dir, repo_url)

    if not repo_dir.exists():
        _run(["git", "-c", "core.longpaths=true", "clone", "--bare", "--filter=blob:none", repo_url, str(repo_dir)])
        _run(["git", "fetch", "--tags"], cwd=repo_dir)
    else:
        # Update existing clone
        _run(["git", "fetch", "--all", "--prune"], cwd=repo_dir)
        _run(["git", "fetch", "--tags"], cwd=repo_dir)

    return repo_dir


def get_ref_for_commands(repo_dir: Path, ref: Optional[str]) -> str:
    """
    Returns the ref to use in git commands.
    If ref is None, tries to find a default branch.
    """
    if ref:
        return ref
    
    # Try common default branch names
    for branch in ["main", "master", "develop"]:
        try:
            git_stdout(repo_dir, ["rev-parse", "--verify", f"refs/heads/{branch}"])
            return branch
        except GitError:
            continue
    
    # Fallback to HEAD
    return "HEAD"


def checkout_ref(repo_dir: Path, ref: Optional[str]) -> None:
    """
    For bare repositories, we don't checkout.
    This function is kept for compatibility but does nothing.
    """
    pass


def git_stdout(repo_dir: Path, args: list[str]) -> str:
    return _run(["git", *args], cwd=repo_dir)