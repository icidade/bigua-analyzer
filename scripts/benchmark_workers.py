from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path
from types import SimpleNamespace

from bigua_analyzer.cli import _run_dataset


def _parse_workers(raw: str) -> list[int]:
    workers = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not workers:
        raise ValueError("At least one worker count must be provided")
    return workers


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dataset throughput across multiple worker counts.")
    parser.add_argument("--dataset", required=True, help="CSV or JSONL dataset path.")
    parser.add_argument("--workers", default="2,4,6,8", help="Comma-separated worker counts (default: 2,4,6,8).")
    parser.add_argument("--max-repos", type=int, default=None, help="Limit repos for faster benchmark runs.")
    parser.add_argument("--repeats", type=int, default=1, help="How many times to run each worker count.")
    parser.add_argument("--cache-dir", default=str(Path.home() / ".bigua" / "cache"), help="Local cache directory for git clones.")
    parser.add_argument("--sdlc-mode", choices=["auto", "human", "hybrid", "ai"], default="auto")
    args = parser.parse_args()

    worker_counts = _parse_workers(args.workers)
    print("workers\trepeat\telapsed_s\tok\tfailed\tavg_repo_s")

    for worker_count in worker_counts:
        elapsed_samples: list[float] = []
        for repeat_index in range(1, args.repeats + 1):
            cli_args = SimpleNamespace(
                dataset=args.dataset,
                max_repos=args.max_repos,
                cache_dir=args.cache_dir,
                max_workers=worker_count,
                sdlc_mode=args.sdlc_mode,
                profile=False,
            )
            started = time.perf_counter()
            results = _run_dataset(cli_args)
            elapsed = time.perf_counter() - started
            elapsed_samples.append(elapsed)
            ok = sum(1 for result in results if result.ok)
            failed = len(results) - ok
            avg_repo = elapsed / len(results) if results else 0.0
            print(f"{worker_count}\t{repeat_index}\t{elapsed:.3f}\t{ok}\t{failed}\t{avg_repo:.3f}")

        if len(elapsed_samples) > 1:
            mean_elapsed = statistics.mean(elapsed_samples)
            stdev_elapsed = statistics.stdev(elapsed_samples)
            print(f"summary\t{worker_count}\tmean={mean_elapsed:.3f}s\tstdev={stdev_elapsed:.3f}s")


if __name__ == "__main__":
    main()