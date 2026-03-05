from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RepoSpec:
    """Normalized input describing what repository to analyze."""
    url: str
    ref: Optional[str] = None  # branch/tag/sha
    repo_id: Optional[str] = None  # stable id for outputs (optional)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepoResult:
    repo: RepoSpec
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None