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

_RADAR_LABELS = [
    "Distribution",
    "Bus Factor",
    "Contributors (log)",
    "Stability",
    "AI Influence",
]


def _safe_repo_id(row: pd.Series[Any]) -> str:
    repo_id = str(row.get("repo_id", "")).strip()
    if repo_id and repo_id.lower() != "nan":
        source = repo_id
    else:
        source = str(row.get("url", "unknown_repo")).strip() or "unknown_repo"

    cleaned = "".join(c if c.isalnum() or c in "._-" else "_" for c in source)
    cleaned = cleaned.strip("._-")
    return cleaned or "unknown_repo"


def _display_repo_name(row: pd.Series[Any]) -> str:
    repo_id = str(row.get("repo_id", "")).strip()
    if repo_id and repo_id.lower() != "nan":
        return repo_id

    url = str(row.get("url", "")).strip().rstrip("/")
    if url and url.lower() != "nan":
        parts = [part for part in url.split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[-2:])
    return "unknown_repo"


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


def _normalized_radar_values(row: pd.Series[Any]) -> list[float] | None:
    gini = _to_float(row.get("gini_coefficient"))
    bus_factor = _to_float(row.get("bus_factor_50p"))
    contributor_count = _to_float(row.get("contributor_count"))
    turnover = _to_float(row.get("developer_turnover"))
    ai_score = _to_float(row.get("ai_influence_score"))

    if None in {gini, bus_factor, contributor_count, turnover, ai_score}:
        return None

    max_bus_factor = max(_RADAR_CONTEXT.get("max_bus_factor", 1.0), 1e-9)
    max_log_contrib = max(_RADAR_CONTEXT.get("max_log_contributors", 1.0), 1e-9)

    return [
        _normalize_unit(gini, invert=True),
        _normalize_unit(bus_factor / max_bus_factor),
        _normalize_log_count(contributor_count, max_log_contrib),
        _normalize_unit(turnover, invert=True),
        _normalize_unit(ai_score),
    ]


def _radar_angles() -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0, 2 * np.pi, len(_RADAR_LABELS), endpoint=False)
    angles_closed = np.concatenate([angles, [angles[0]]])
    return angles, angles_closed


def _setup_radar_axis(ax: Any) -> tuple[np.ndarray, np.ndarray]:
    angles, angles_closed = _radar_angles()
    ax.set_xticks(angles)
    ax.set_xticklabels(_RADAR_LABELS)
    ax.set_ylim(0, 1)
    return angles, angles_closed


def _plot_radar_series(
    ax: Any,
    values: list[float] | np.ndarray,
    angles_closed: np.ndarray,
    label: str,
    color: str,
    *,
    fill_alpha: float = 0.08,
    linewidth: float = 2,
    linestyle: str = "-",
) -> None:
    closed_values = list(values) + [values[0]]
    ax.plot(
        angles_closed,
        closed_values,
        linewidth=linewidth,
        linestyle=linestyle,
        color=color,
        label=label,
    )
    if fill_alpha > 0:
        ax.fill(angles_closed, closed_values, color=color, alpha=fill_alpha)


def _build_radar_frame(df: pd.DataFrame) -> pd.DataFrame:
    metric_columns = [
        "gini_coefficient",
        "bus_factor_50p",
        "contributor_count",
        "developer_turnover",
        "ai_influence_score",
    ]
    missing_columns = [column for column in metric_columns if column not in df.columns]
    if missing_columns:
        return pd.DataFrame()

    radar_df = df.copy()
    radar_df[metric_columns] = radar_df[metric_columns].apply(pd.to_numeric, errors="coerce")

    records: list[dict[str, Any]] = []
    for _, row in radar_df.iterrows():
        normalized = _normalized_radar_values(row)
        if normalized is None:
            continue
        record = {
            "display_name": _display_repo_name(row),
            "traffic_light": str(row.get("traffic_light", "")).strip().lower(),
            "ai_influence_score": _to_float(row.get("ai_influence_score")) or 0.0,
            "radar_distribution": normalized[0],
            "radar_bus_factor": normalized[1],
            "radar_contributors_log": normalized[2],
            "radar_stability": normalized[3],
            "radar_ai_influence": normalized[4],
        }
        records.append(record)

    return pd.DataFrame.from_records(records)


def _radar_metric_values(row: pd.Series[Any]) -> list[float]:
    return [
        float(row["radar_distribution"]),
        float(row["radar_bus_factor"]),
        float(row["radar_contributors_log"]),
        float(row["radar_stability"]),
        float(row["radar_ai_influence"]),
    ]


def _generate_aggregate_radar_by_traffic_light(radar_df: pd.DataFrame, output_dir: Path) -> Path | None:
    if radar_df.empty or "traffic_light" not in radar_df.columns:
        return None

    ordered_labels = ["green", "yellow", "orange", "red"]
    color_by_label = {
        "green": "#2e7d32",
        "yellow": "#f9a825",
        "orange": "#ef6c00",
        "red": "#c62828",
    }
    metric_columns = [
        "radar_distribution",
        "radar_bus_factor",
        "radar_contributors_log",
        "radar_stability",
        "radar_ai_influence",
    ]
    grouped = (
        radar_df[radar_df["traffic_light"].isin(ordered_labels)]
        .groupby("traffic_light")[metric_columns]
        .mean()
        .reindex(ordered_labels)
        .dropna(how="all")
    )
    if grouped.empty:
        return None

    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111, polar=True)
    _, angles_closed = _setup_radar_axis(ax)
    for label, values in grouped.iterrows():
        _plot_radar_series(
            ax,
            [float(value) for value in values.tolist()],
            angles_closed,
            label=label,
            color=color_by_label[label],
            fill_alpha=0.12,
        )
    ax.set_title("Aggregate Radar by Traffic Light")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.05))

    out_path = output_dir / "radar_aggregate_by_traffic_light.png"
    _save_current_figure(out_path)
    return out_path


def _generate_top_ai_radar(radar_df: pd.DataFrame, output_dir: Path, limit: int = 8) -> Path | None:
    if radar_df.empty:
        return None

    top_df = radar_df.sort_values("ai_influence_score", ascending=False).head(limit)
    if top_df.empty:
        return None

    colors = plt.cm.tab10(np.linspace(0, 1, len(top_df)))
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    _, angles_closed = _setup_radar_axis(ax)

    for color, (_, row) in zip(colors, top_df.iterrows()):
        _plot_radar_series(
            ax,
            _radar_metric_values(row),
            angles_closed,
            label=str(row["display_name"]),
            color=color,
            fill_alpha=0.05,
            linewidth=1.8,
        )

    ax.set_title(f"Radar Top {len(top_df)} by AI Influence")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.05), fontsize=8)

    out_path = output_dir / "radar_top8_ai_influence.png"
    _save_current_figure(out_path)
    return out_path


def _generate_median_plus_outliers_radar(radar_df: pd.DataFrame, output_dir: Path) -> Path | None:
    if radar_df.empty:
        return None

    metric_columns = [
        "radar_distribution",
        "radar_bus_factor",
        "radar_contributors_log",
        "radar_stability",
        "radar_ai_influence",
    ]
    median_values = radar_df[metric_columns].median()
    deltas = radar_df[metric_columns].sub(median_values, axis=1)
    distances = np.sqrt((deltas**2).sum(axis=1))
    outlier_count = min(4, len(radar_df))
    outlier_indices = distances.nlargest(outlier_count).index
    outlier_df = radar_df.loc[outlier_indices]

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    _, angles_closed = _setup_radar_axis(ax)

    _plot_radar_series(
        ax,
        [float(value) for value in median_values.tolist()],
        angles_closed,
        label="dataset median",
        color="#616161",
        fill_alpha=0.1,
        linewidth=2.4,
        linestyle="--",
    )

    colors = plt.cm.Set2(np.linspace(0, 1, len(outlier_df)))
    for color, (_, row) in zip(colors, outlier_df.iterrows()):
        _plot_radar_series(
            ax,
            _radar_metric_values(row),
            angles_closed,
            label=str(row["display_name"]),
            color=color,
            fill_alpha=0.06,
            linewidth=1.8,
        )

    ax.set_title("Radar Median Plus Structural Outliers")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.05), fontsize=8)

    out_path = output_dir / "radar_median_plus_outliers.png"
    _save_current_figure(out_path)
    return out_path


def generate_radar_chart(row: pd.Series[Any], output_dir: str) -> Path | None:
    """Generate one radar chart per repository and save it to disk."""
    normalized_values = _normalized_radar_values(row)
    if normalized_values is None:
        return None

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, polar=True)
    _, angles_closed = _setup_radar_axis(ax)
    _plot_radar_series(
        ax,
        normalized_values,
        angles_closed,
        label=_display_repo_name(row),
        color="#4c78a8",
        fill_alpha=0.25,
    )

    repo_name = _safe_repo_id(row)
    ax.set_title(_display_repo_name(row))

    out_path = Path(output_dir) / f"radar_{repo_name}.png"
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
        ordered_labels = ["green", "yellow", "orange", "red"]
        color_by_label = {
            "green": "#2e7d32",
            "yellow": "#f9a825",
            "orange": "#ef6c00",
            "red": "#c62828",
        }
        counts = (
            df["traffic_light"]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("nan", np.nan)
            .dropna()
            .value_counts()
            .reindex(ordered_labels, fill_value=0)
        )
        if int(counts.sum()) > 0:
            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            bar_colors = [color_by_label[label] for label in ordered_labels]
            ax.bar(ordered_labels, counts.values, color=bar_colors)
            ax.set_title("Repo Classification (Traffic Light)")
            ax.set_xlabel("Traffic Light")
            ax.set_ylabel("Count")
            _save_current_figure(output_root / "repo_classification.png")

    # D) Turnover vs Contributors
    if {"contributor_count", "developer_turnover"}.issubset(df.columns):
        plot_df = df[["repo_id", "url", "contributor_count", "developer_turnover"]].copy()
        plot_df[["contributor_count", "developer_turnover"]] = plot_df[
            ["contributor_count", "developer_turnover"]
        ].apply(
            pd.to_numeric,
            errors="coerce",
        )
        plot_df = plot_df.dropna(subset=["contributor_count", "developer_turnover"])
        plot_df = plot_df[plot_df["contributor_count"] > 0]
        if not plot_df.empty:
            zero_turnover_count = int((plot_df["developer_turnover"] == 0).sum())
            total_count = int(len(plot_df))
            outliers = plot_df[plot_df["developer_turnover"] > 0]

            fig = plt.figure(figsize=(7, 5))
            ax = fig.add_subplot(111)
            ax.scatter(
                plot_df["contributor_count"],
                plot_df["developer_turnover"],
                color="#4c78a8",
                alpha=0.75,
            )
            if not outliers.empty:
                ax.scatter(
                    outliers["contributor_count"],
                    outliers["developer_turnover"],
                    color="#d62728",
                    s=70,
                    zorder=3,
                )
                for _, outlier in outliers.iterrows():
                    label = _safe_repo_id(outlier)
                    ax.annotate(
                        label,
                        (outlier["contributor_count"], outlier["developer_turnover"]),
                        textcoords="offset points",
                        xytext=(6, 6),
                        fontsize=8,
                    )

            ax.set_xscale("log")
            ax.set_title("Turnover vs Contributors")
            ax.set_xlabel("Contributor Count (log scale)")
            ax.set_ylabel("Developer Turnover")
            ax.text(
                0.02,
                0.98,
                f"zero turnover: {zero_turnover_count}/{total_count}",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.85},
            )
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

    radar_df = _build_radar_frame(df)
    _generate_aggregate_radar_by_traffic_light(radar_df, output_root)
    _generate_top_ai_radar(radar_df, output_root)
    _generate_median_plus_outliers_radar(radar_df, output_root)

    for _, row in df.iterrows():
        generate_radar_chart(row, str(output_root))
