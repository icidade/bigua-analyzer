from __future__ import annotations

import os
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from .core import analyze_repo
from .io_utils import read_dataset, write_csv, write_jsonl
from .models import RepoResult, RepoSpec
from .sdlc import SDLCMode


_EXTERNAL_LLM_WARNING = (
    "[privacy-warning] Repository metadata and derived metrics may be sent to an "
    "external LLM API. "
    "Avoid using analyze-report with private or sensitive repositories unless "
    "your org policy explicitly allows it."
)


def _format_elapsed(start_time: float) -> str:
    elapsed_seconds = max(0, int(time.time() - start_time))
    return _format_duration(elapsed_seconds)


def _format_duration(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _estimate_eta(start_time: float, completed: int, total: int) -> str | None:
    if completed <= 0 or total <= completed:
        return None

    elapsed_seconds = max(1, int(time.time() - start_time))
    average_seconds_per_item = elapsed_seconds / completed
    remaining_seconds = int(round((total - completed) * average_seconds_per_item))
    return _format_duration(remaining_seconds)


def _print_progress(
    message: str,
    start_time: float | None = None,
    completed: int | None = None,
    total: int | None = None,
) -> None:
    suffix_parts: list[str] = []
    if start_time is not None:
        suffix_parts.append(f"elapsed: {_format_elapsed(start_time)}")
    if start_time is not None and completed is not None and total is not None:
        eta = _estimate_eta(start_time, completed, total)
        if eta is not None:
            suffix_parts.append(f"ETA: {eta}")

    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
    print(f"[progress] {message}{suffix}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Sub-command: analyze  (existing behaviour)
# ---------------------------------------------------------------------------

def _add_analyze_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "analyze",
        help="Analyze repositories and extract socio-technical metrics.",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("repo", nargs="?", help="Repository URL (single mode). Example: https://github.com/org/repo")
    g.add_argument("--dataset", type=str, help="Path to a dataset (.csv or .jsonl) containing repository URLs.")
    p.add_argument("--ref", type=str, default=None, help="Branch/tag/SHA to analyze (single mode only).")
    p.add_argument("--cache-dir", type=str, default=str(Path.home() / ".bigua" / "cache"), help="Local cache directory for git clones.")
    p.add_argument("--out", type=str, default="out/results", help="Output path prefix (without extension).")
    p.add_argument("--format", choices=["jsonl", "csv", "both"], default="both", help="Output format.")
    p.add_argument("--max-repos", type=int, default=None, help="Limit number of repos from dataset (useful for testing).")
    p.add_argument("--max-workers", type=int, default=4, help="Maximum number of parallel threads for dataset processing.")
    p.add_argument(
        "--sdlc-mode",
        choices=["auto", "human", "hybrid", "ai"],
        default="auto",
        help="Analysis mode: auto, human, hybrid, or ai (default: auto).",
    )
    p.set_defaults(func=_cmd_analyze)


def _run_single(args) -> List[RepoResult]:
    spec = RepoSpec(url=args.repo, ref=args.ref)
    r = analyze_repo(spec, cache_dir=Path(args.cache_dir), sdlc_mode=args.sdlc_mode)
    return [r]


def _run_dataset(args) -> List[RepoResult]:
    start_time = time.time()
    repos = read_dataset(Path(args.dataset))
    if args.max_repos is not None:
        repos = repos[: max(0, args.max_repos)]

    results: List[RepoResult] = []
    cache_dir = Path(args.cache_dir)
    sdlc_mode: SDLCMode = args.sdlc_mode
    total_repos = len(repos)

    _print_progress(
        f"Scheduling {total_repos} repositories with max_workers={args.max_workers}",
        start_time,
    )

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(analyze_repo, repo, cache_dir, sdlc_mode=sdlc_mode): repo
            for repo in repos
        }
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            repo_label = result.repo.repo_id or result.repo.url
            status = "ok" if result.ok else "failed"
            _print_progress(
                f"Repository {completed}/{total_repos} completed: {repo_label} [{status}]",
                start_time,
                completed,
                total_repos,
            )

    return results


def _cmd_analyze(args) -> None:
    if args.dataset:
        results = _run_dataset(args)
    else:
        results = _run_single(args)

    out_prefix = Path(args.out)

    # If the user supplies just a basename (no directory), default to the `out/` folder
    if out_prefix.parent in (Path("."), Path("")):
        out_prefix = Path("out") / out_prefix

    if args.format in ("jsonl", "both"):
        write_jsonl(results, out_prefix.with_suffix(".jsonl"))
    if args.format in ("csv", "both"):
        write_csv(results, out_prefix.with_suffix(".csv"))

    ok = sum(1 for r in results if r.ok)
    fail = len(results) - ok
    print(f"Analyzed {len(results)} repos: ok={ok}, failed={fail}")
    if fail:
        print("Failed repos:")
        for r in results:
            if not r.ok:
                rid = r.repo.repo_id or r.repo.url
                print(f"- {rid}: {r.error}")


# ---------------------------------------------------------------------------
# Sub-command: analyze-report  (new AI report pipeline)
# ---------------------------------------------------------------------------

def _add_analyze_report_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "analyze-report",
        help="Generate an AI-assisted Markdown (and optional HTML) report from a metrics CSV.",
    )
    p.add_argument(
        "--csv",
        required=True,
        type=str,
        help="Path to the metrics CSV produced by the 'analyze' command.",
    )
    p.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="Filter to a specific repository URL when the CSV contains multiple rows.",
    )
    p.add_argument(
        "--out-dir",
        type=str,
        default="analysis_reports",
        help="Output directory for batch mode when --repo-url is not provided (default: analysis_reports).",
    )
    p.add_argument(
        "--out-md",
        type=str,
        default="analysis_report.md",
        help="Output path for the Markdown report (default: analysis_report.md).",
    )
    p.add_argument(
        "--out-html",
        type=str,
        default="analysis_report.html",
        help="Output path for the HTML report. Pass empty string to skip HTML rendering.",
    )
    p.add_argument(
        "--llm",
        "--provider",
        dest="llm",
        choices=["openai-compatible", "openai", "xai", "gemini", "ollama"],
        default="openai-compatible",
        help="LLM adapter (default: openai-compatible). Supported: openai-compatible, openai, xai, gemini, ollama.",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (falls back to LLM_MODEL, then provider-specific vars).",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Provider API base URL override (falls back to LLM_BASE_URL, then provider-specific vars).",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key override (falls back to LLM_API_KEY, then provider-specific vars).",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature (default: 0.2).",
    )
    p.add_argument(
        "--top-p",
        type=float,
        default=0.9,
        help="Nucleus sampling probability mass (default: 0.9).",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens in the LLM response (default: 4096).",
    )
    p.add_argument(
        "--suppress-external-llm-warning",
        action="store_true",
        help="Suppress privacy warning about sending repository metadata/metrics to an external LLM API.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Bypass interactive confirmation prompt and continue immediately.",
    )
    p.set_defaults(func=_cmd_analyze_report)


def _cmd_analyze_report(args) -> None:
    from .ai.report_generator import generate_report, generate_reports

    out_html = Path(args.out_html) if args.out_html else None

    if not args.suppress_external_llm_warning:
        print(_EXTERNAL_LLM_WARNING, file=sys.stderr)

    if not args.yes:
        if not sys.stdin.isatty():
            raise SystemExit(
                "Interactive confirmation required but stdin is not a TTY. "
                "Re-run with --yes to bypass the prompt."
            )

        answer = input(
            "Continue and send repository metadata/metrics to an external LLM API? [y/N]: "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted by user.")
            return

    if args.repo_url:
        generate_report(
            csv_path=Path(args.csv),
            repo_url=args.repo_url,
            out_md=Path(args.out_md),
            out_html=out_html,
            provider=args.llm,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )

        print(f"Report written to: {args.out_md}")
        if out_html:
            print(f"HTML report written to: {args.out_html}")
        return

    written_reports = generate_reports(
        csv_path=Path(args.csv),
        out_dir=Path(args.out_dir),
        render_html_output=bool(args.out_html),
        provider=args.llm,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
    )

    print(f"Generated {len(written_reports)} Markdown reports in: {args.out_dir}")
    if args.out_html:
        print(f"Generated matching HTML reports in: {args.out_dir}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bigua-analyzer",
        description="Analyze public GitHub repositories and extract socio-technical development metrics.",
    )
    subparsers = p.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True
    _add_analyze_parser(subparsers)
    _add_analyze_report_parser(subparsers)
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)