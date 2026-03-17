"""
Orchestrate the full pipeline:

    CSV → prompt builder (+ derived signals) → LLM → analysis_report.md → analysis_report.html
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .prompt_builder import build_prompt, SYSTEM_PROMPT
from .llm_client import call_llm
from .html_renderer import render_html


def _row_to_metrics(row: "pd.Series[Any]") -> Dict[str, Any]:  # type: ignore[type-arg]
    """Extract metric columns from a CSV row, skipping bookkeeping columns."""
    skip = {"url", "ref", "repo_id", "ok", "error"}
    return {
        k: v
        for k, v in row.items()
        if k not in skip and pd.notna(v)
    }


def _repo_name_from_url(repo_url: str) -> str:
    return repo_url.rstrip("/").split("/")[-1] if repo_url else "unknown"


def _repo_slug(row: "pd.Series[Any]") -> str:  # type: ignore[type-arg]
    repo_id = row.get("repo_id")
    if pd.notna(repo_id) and str(repo_id).strip():
        raw = str(repo_id).strip()
    else:
        repo_url = str(row.get("url", "")).strip().rstrip("/")
        parts = [part for part in repo_url.split("/") if part]
        raw = "__".join(parts[-2:]) if len(parts) >= 2 else _repo_name_from_url(repo_url)

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return slug or "repository"


def _generate_markdown_for_row(
    row: "pd.Series[Any]",  # type: ignore[type-arg]
    *,
    provider: str,
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> str:
    resolved_url = str(row.get("url", ""))
    repo_name = _repo_name_from_url(resolved_url)
    metrics = _row_to_metrics(row)

    prompt = build_prompt(
        repo_name=repo_name,
        repo_url=resolved_url,
        metrics_dict=metrics,
    )

    return call_llm(
        prompt,
        provider=provider,
        system_prompt=SYSTEM_PROMPT,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )


def _write_report_outputs(
    markdown_report: str,
    *,
    out_md: Path,
    out_html: Optional[Path],
) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(markdown_report, encoding="utf-8")

    if out_html is not None:
        render_html(markdown_report, out_html)


def generate_report(
    csv_path: Path,
    *,
    repo_url: Optional[str] = None,
    out_md: Path = Path("analysis_report.md"),
    out_html: Optional[Path] = Path("analysis_report.html"),
    provider: str = "openai-compatible",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    top_p: float = 0.9,
    max_tokens: int = 4096,
) -> str:
    """
    Run the full CSV → Markdown (→ HTML) pipeline for one repository.

    Parameters
    ----------
    csv_path:
        Path to the CSV produced by ``bigua-analyzer``.
    repo_url:
        Filter to a specific repository URL.  If the CSV contains only one
        row the filter is applied automatically.
    out_md:
        Destination path for the Markdown report.
    out_html:
        Destination path for the HTML report.  Pass ``None`` to skip HTML
        rendering.
    provider / model / base_url / api_key / temperature / top_p / max_tokens:
        Forwarded verbatim to :func:`~bigua_analyzer.ai.llm_client.call_llm`.

    Returns
    -------
    str
        The raw Markdown text returned by the LLM.
    """
    df = pd.read_csv(csv_path)

    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    # Select the target row
    if repo_url:
        mask = df["url"] == repo_url
        if not mask.any():
            raise ValueError(f"Repository URL not found in CSV: {repo_url}")
        row = df[mask].iloc[0]
    elif len(df) == 1:
        row = df.iloc[0]
    else:
        raise ValueError(
            "CSV contains multiple rows. "
            "Specify --repo-url to select one repository."
        )

    markdown_report = _generate_markdown_for_row(
        row,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )

    _write_report_outputs(
        markdown_report,
        out_md=out_md,
        out_html=out_html,
    )

    return markdown_report


def generate_reports(
    csv_path: Path,
    *,
    out_dir: Path = Path("analysis_reports"),
    render_html_output: bool = True,
    provider: str = "openai-compatible",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    top_p: float = 0.9,
    max_tokens: int = 4096,
) -> list[Path]:
    """Generate one Markdown report per CSV row and optional paired HTML files."""
    df = pd.read_csv(csv_path)

    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    written_reports: list[Path] = []
    for _, row in df.iterrows():
        markdown_report = _generate_markdown_for_row(
            row,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        slug = _repo_slug(row)
        out_md = out_dir / f"{slug}_analysis_report.md"
        out_html = out_dir / f"{slug}_analysis_report.html" if render_html_output else None

        _write_report_outputs(
            markdown_report,
            out_md=out_md,
            out_html=out_html,
        )
        written_reports.append(out_md)

    return written_reports
