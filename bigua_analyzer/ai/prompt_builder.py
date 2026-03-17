"""Build the prompts sent to the LLM, including derived signals."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Resolve template relative to the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = _PROJECT_ROOT / "templates" / "analysis_prompt.txt"

SYSTEM_PROMPT = (
    "You are a senior software engineering analytics and repository health analyst.\n"
    "Your task is to analyze a GitHub repository using engineering and sociotechnical "
    "metrics extracted by bigua-analyzer.\n"
    "You must produce a professional technical report written in clear English.\n\n"
    "Rules:\n"
    "- Do not invent facts.\n"
    "- Base conclusions only on the provided metrics.\n"
    "- Do not claim security vulnerabilities unless explicitly supported by the input.\n"
    "- If evidence is weak, explicitly say the conclusion is uncertain.\n"
    "- Prefer cautious wording such as 'may indicate', 'suggests', or 'is consistent with'."
)


def _derive_signals(metrics: Dict[str, Any]) -> Dict[str, str]:
    """Compute human-readable derived signals from raw metric values."""
    signals: Dict[str, str] = {}

    gini = metrics.get("gini_coefficient")
    if gini is not None:
        try:
            signals["contribution_concentration"] = (
                "high" if float(gini) > 0.7 else "moderate"
            )
        except (TypeError, ValueError):
            pass

    bus_factor = metrics.get("bus_factor")
    if bus_factor is not None:
        try:
            signals["bus_factor_risk"] = (
                "high" if float(bus_factor) < 2 else "moderate"
            )
        except (TypeError, ValueError):
            pass

    turnover = metrics.get("developer_turnover")
    if turnover is not None:
        try:
            signals["contributor_stability"] = (
                "unstable" if float(turnover) > 0.5 else "stable"
            )
        except (TypeError, ValueError):
            pass

    churn = metrics.get("code_churn")
    if churn is not None:
        try:
            signals["change_velocity"] = (
                "high" if float(churn) > 1000 else "normal"
            )
        except (TypeError, ValueError):
            pass

    return signals


def build_prompt(
    repo_name: str,
    repo_url: str,
    metrics_dict: Dict[str, Any],
) -> str:
    """Return the fully rendered prompt string ready to send to the LLM."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    metrics_lines = [f"- {k}: {v}" for k, v in metrics_dict.items()]
    metrics_block = "\n".join(metrics_lines) if metrics_lines else "(no metrics available)"

    signals = _derive_signals(metrics_dict)
    signals_lines = [f"- {k}: {v}" for k, v in signals.items()]
    signals_block = (
        "\n".join(signals_lines) if signals_lines else "(no signals derived)"
    )

    prompt = template.format(
        repo_name=repo_name,
        repo_url=repo_url,
        analysis_date=datetime.now(timezone.utc).isoformat(),
        metrics_block=metrics_block,
        signals_block=signals_block,
    )

    return prompt
