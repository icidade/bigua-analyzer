from __future__ import annotations

import os
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from .core import analyze_repo
from .io_utils import read_dataset, write_csv, write_jsonl
from .models import RepoResult, RepoSpec


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bigua-analyzer", description="Analyze public GitHub repositories and extract socio-technical development metrics.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("repo", nargs="?", help="Repository URL to analyze (single mode). Example: https://github.com/org/repo")
    g.add_argument("--dataset", type=str, help="Path to a dataset (.csv or .jsonl) containing repository URLs.")
    p.add_argument("--ref", type=str, default=None, help="Branch/tag/SHA to analyze (single mode only).")
    p.add_argument("--cache-dir", type=str, default=str(Path.home() / ".bigua" / "cache"), help="Local cache directory for git clones.")
    p.add_argument("--out", type=str, default="out/results", help="Output path prefix (without extension).")
    p.add_argument("--format", choices=["jsonl", "csv", "both"], default="both", help="Output format.")
    p.add_argument("--max-repos", type=int, default=None, help="Limit number of repos from dataset (useful for testing).")
    p.add_argument("--max-workers", type=int, default=4, help="Maximum number of parallel threads for dataset processing.")
    return p


def _run_single(args) -> List[RepoResult]:
    spec = RepoSpec(url=args.repo, ref=args.ref)
    r = analyze_repo(spec, cache_dir=Path(args.cache_dir))
    return [r]


def _run_dataset(args) -> List[RepoResult]:
    repos = read_dataset(Path(args.dataset))
    if args.max_repos is not None:
        repos = repos[: max(0, args.max_repos)]

    results: List[RepoResult] = []
    cache_dir = Path(args.cache_dir)

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {executor.submit(analyze_repo, repo, cache_dir): repo for repo in repos}
        for future in as_completed(futures):
            results.append(future.result())

    return results


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.dataset:
        results = _run_dataset(args)
    else:
        results = _run_single(args)

    out_prefix = Path(args.out)
    if args.format in ("jsonl", "both"):
        write_jsonl(results, out_prefix.with_suffix(".jsonl"))
    if args.format in ("csv", "both"):
        write_csv(results, out_prefix.with_suffix(".csv"))

    # Basic summary to stdout
    ok = sum(1 for r in results if r.ok)
    fail = len(results) - ok
    print(f"Analyzed {len(results)} repos: ok={ok}, failed={fail}")
    if fail:
        print("Failed repos:")
        for r in results:
            if not r.ok:
                rid = r.repo.repo_id or r.repo.url
                print(f"- {rid}: {r.error}")