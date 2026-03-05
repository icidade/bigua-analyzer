from __future__ import annotations

import json
from pathlib import Path
import typing

import pandas as pd

from .types import RepoResult, RepoSpec


def sstrip(v: typing.Any) -> typing.Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None

def read_dataset(path: Path) -> typing.List[RepoSpec]:
    """
    Accepts CSV or JSONL for MVP.

    CSV columns supported:
      - url (required)
      - ref (optional)
      - repo_id (optional)

    JSONL: one object per line with keys url/ref/repo_id/extra
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if "url" not in df.columns:
            raise ValueError("CSV must contain a 'url' column.")
        repos: typing.List[RepoSpec] = []
        for _, row in df.iterrows():
            url = sstrip(row.get("url"))
            if not url:
                raise ValueError(f"Row {row.name}: 'url' must be a non-empty string.")
            ref = sstrip(row.get("ref")) if not pd.isna(row.get("ref")) else None
            repo_id = sstrip(row.get("repo_id")) if not pd.isna(row.get("repo_id")) else None
            repos.append(
                RepoSpec(
                    url=url,
                    ref=ref,
                    repo_id=repo_id,
                )
            )
        return repos

    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        repos = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                url = sstrip(obj.get("url") if isinstance(obj, dict) else None)
                if not url:
                    raise ValueError("Missing required field 'url'")
                ref = sstrip(obj.get("ref"))
                repo_id = sstrip(obj.get("repo_id"))
                extra = obj.get("extra", {})
                repos.append(
                    RepoSpec(
                        url=url,
                        ref=ref,
                        repo_id=repo_id,
                        extra=extra,
                    )
                )
        return repos

    raise ValueError("Unsupported dataset format. Use .csv or .jsonl/.ndjson")


def write_jsonl(results: typing.Iterable[RepoResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            obj = {
                "repo": {
                    "url": r.repo.url,
                    "ref": r.repo.ref,
                    "repo_id": r.repo.repo_id,
                    "extra": r.repo.extra,
                },
                "ok": r.ok,
                "metrics": r.metrics,
                "error": r.error,
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_csv(results: typing.Iterable[RepoResult], out_path: Path) -> None:
    rows = []
    for r in results:
        row = {
            "url": r.repo.url,
            "ref": r.repo.ref,
            "repo_id": r.repo.repo_id,
            "ok": r.ok,
            "error": r.error,
            **r.metrics,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)