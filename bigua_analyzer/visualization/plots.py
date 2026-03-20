from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

# Force non-interactive backend for CI/headless environments.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_RADAR_CONTEXT: dict[str, float] = {
    "max_bus_factor": 1.0,
    "max_log_contributors": 1.0,
}


def _safe_repo_id(row: pd.Series[Any]) -> str:
    repo_id = str(row.get("repo_id", "")).strip()
    if repo_id and repo_id.lower() != "nan":
        source = repo_id
    else:
        source = str(row.get("url", "unknown_repo")).strip() or "unknown_repo"

    cleaned = "".join(c if c.isalnum() or c in "._-" else "_" for c in source)
    cleaned = cleaned.strip("._-")
    return cleaned or "unknown_repo"


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _normalize_unit(value: float, invert: bool = False) -> float:
    bounded = max(0.0, min(1.0, value))
    return 1.0 - bounded if invert else bounded


def _normalize_log_count(value: float, max_log_value: float) -> float:
    if value <= 0:
        return 0.0
    denominator = max(max_log_value, 1e-9)
    return max(0.0, min(1.0, math.log1p(value) / denominator))


def _save_current_figure(output_path: Path) -> None:
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def generate_radar_chart(row: pd.Series[Any], output_dir: str) -> Path | None:
    """Generate one radar chart per repository and save it to disk."""
    gini = _to_float(row.get("gini_coefficient"))
    bus_factor = _to_float(row.get("bus_factor_50p"))
    contributor_count = _to_float(row.get("contributor_count"))
    turnover = _to_float(row.get("developer_turnover"))
    ai_score = _to_float(row.get("ai_influence_score"))

    if None in {gini, bus_factor, contributor_count, turnover, ai_score}:
        return None

    max_bus_factor = max(_RADAR_CONTEXT.get("max_bus_factor", 1.0), 1e-9)
    max_log_contrib = max(_RADAR_CONTEXT.get("max_log_contributors", 1.0), 1e-9)

    normalized_values = [
        _normalize_unit(gini, invert=True),
        _normalize_unit(bus_factor / max_bus_factor),
        _normalize_log_count(contributor_count, max_log_contrib),
        _normalize_unit(turnover, invert=True),
        _normalize_unit(ai_score),
    ]

    labels = [
        "1 - Gini",
        "Bus Factor (50p)",
        "Contributors (log)",
        "1 - Turnover",
        "AI Influence",
    ]

    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)

    values = normalized_values + [normalized_values[0]]
    angles_closed = np.concatenate([angles, [angles[0]]])

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, values, linewidth=2)
    ax.fill(angles_closed, values, alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)

    repo_name = _safe_repo_id(row)
    ax.set_title(repo_name)

    out_path = Path(output_dir) / f"radar_{repo_name}.png"
    _save_current_figure(out_path)
    return out_path


def generate_traffic_light_badge(row: pd.Series[Any], output_dir: str) -> Path:
    """Generate a simple traffic-light textual badge for one repository."""
    traffic_raw = str(row.get("traffic_light", "")).strip().lower()
    if traffic_raw == "green":
        label = "GREEN"
    elif traffic_raw == "yellow":
        label = "YELLOW"
    elif traffic_raw in {"orange", "red"}:
        label = "RED"
    else:
        label = "UNKNOWN"

    fig = plt.figure(figsize=(6, 1.8))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(
        0.5,
        0.5,
        f"STRUCTURAL SIGNAL: {label}",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
    )

    repo_name = _safe_repo_id(row)
    out_path = Path(output_dir) / f"traffic_light_{repo_name}.png"
    _save_current_figure(out_path)
    return out_path


def generate_all_plots(csv_path: str, output_dir: str) -> None:
    """Generate all aggregate and per-repo visual outputs from analyzer CSV."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # A) Gini vs Bus Factor
    if {"gini_coefficient", "bus_factor_50p"}.issubset(df.columns):
        plot_df = df[["gini_coefficient", "bus_factor_50p"]].dropna()
        if not plot_df.empty:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.scatter(plot_df["gini_coefficient"], plot_df["bus_factor_50p"])
            ax.set_title("Gini vs Bus Factor")
            ax.set_xlabel("Gini Coefficient")
            ax.set_ylabel("Bus Factor (50p)")
            _save_current_figure(output_root / "gini_vs_bus_factor.png")

    # B) AI Influence Distribution
    if "ai_influence_score" in df.columns:
        values = pd.to_numeric(df["ai_influence_score"], errors="coerce").dropna()
        if not values.empty:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.hist(values, bins=10)
            ax.set_title("AI Influence Distribution")
            ax.set_xlabel("AI Influence Score")
            ax.set_ylabel("Count")
            _save_current_figure(output_root / "ai_influence_distribution.png")

    # C) Repo Classification (Traffic Light)
    if "traffic_light" in df.columns:
        counts = (
            df["traffic_light"]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("nan", np.nan)
            .dropna()
            .value_counts()
            .sort_index()
        )
        if not counts.empty:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.bar(counts.index, counts.values)
            ax.set_title("Repo Classification (Traffic Light)")
            ax.set_xlabel("Traffic Light")
            ax.set_ylabel("Count")
            _save_current_figure(output_root / "repo_classification.png")

    # D) Turnover vs Contributors
    if {"contributor_count", "developer_turnover"}.issubset(df.columns):
        plot_df = df[["contributor_count", "developer_turnover"]].apply(
            pd.to_numeric,
            errors="coerce",
        ).dropna()
        if not plot_df.empty:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.scatter(plot_df["contributor_count"], plot_df["developer_turnover"])
            ax.set_title("Turnover vs Contributors")
            ax.set_xlabel("Contributor Count")
            ax.set_ylabel("Developer Turnover")
            _save_current_figure(output_root / "turnover_vs_contributors.png")

    # E) Release Cadence vs AI Influence
    if {"release_cadence_days", "ai_influence_score"}.issubset(df.columns):
        plot_df = df[["release_cadence_days", "ai_influence_score"]].apply(
            pd.to_numeric,
            errors="coerce",
        ).dropna()
        if not plot_df.empty:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.scatter(plot_df["release_cadence_days"], plot_df["ai_influence_score"])
            ax.set_title("Release Cadence vs AI Influence")
            ax.set_xlabel("Release Cadence Days")
            ax.set_ylabel("AI Influence Score")
            _save_current_figure(output_root / "release_vs_ai.png")

    if "bus_factor_50p" in df.columns:
        bus_series = pd.to_numeric(df["bus_factor_50p"], errors="coerce").dropna()
        bus_max = float(bus_series.max()) if not bus_series.empty else 1.0
    else:
        bus_max = 1.0

    if "contributor_count" in df.columns:
        contributor_series = pd.to_numeric(df["contributor_count"], errors="coerce").dropna()
    else:
        contributor_series = pd.Series(dtype=float)
    if contributor_series.empty:
        max_log_contributors = 1.0
    else:
        max_log_contributors = math.log1p(float(contributor_series.max()))

    _RADAR_CONTEXT["max_bus_factor"] = float(max(bus_max, 1.0))
    _RADAR_CONTEXT["max_log_contributors"] = float(max(max_log_contributors, 1.0))

    for _, row in df.iterrows():
        generate_radar_chart(row, str(output_root))
        generate_traffic_light_badge(row, str(output_root))
