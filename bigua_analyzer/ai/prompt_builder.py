"""Build the prompts sent to the LLM, including derived signals."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Resolve template relative to the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = _PROJECT_ROOT / "templates" / "analysis_prompt.txt"

SYSTEM_PROMPT = (
    "You are a senior software engineering analytics and repository health analyst writing concise analyst notes.\n"
    "Your task is to analyze a GitHub repository using engineering and sociotechnical metrics extracted by bigua-analyzer.\n"
    "You must produce a professional technical report written in clear English that is suitable for research appendices, chart commentary, and presentations.\n\n"
    "Rules:\n"
    "- Do not invent facts.\n"
    "- Base conclusions only on the provided metrics.\n"
    "- Do not claim security vulnerabilities unless explicitly supported by the input.\n"
    "- If evidence is weak, explicitly say the conclusion is uncertain and screening-grade only.\n"
    "- Prefer cautious wording such as 'metrics suggest', 'signals are consistent with', 'may reflect', or 'should be interpreted cautiously'.\n"
    "- Avoid strong causal claims unless the evidence is overwhelming.\n"
    "- Vary sentence openings and lead with the most distinctive pattern, not with the score by default."
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
    if bus_factor is None:
        bus_factor = metrics.get("bus_factor_50p")
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


def _dominant_framing(metrics: Dict[str, Any]) -> str:
    if metrics.get("insufficient_recent_data") or metrics.get("recent_signal_strength") in {"weak", "insufficient"}:
        return "low-signal / insufficient-data"

    gini = metrics.get("gini_coefficient")
    top_share = metrics.get("top_contributor_share")
    contributor_count = metrics.get("contributor_count")
    turnover = metrics.get("developer_turnover")

    try:
        if gini is not None and float(gini) >= 0.65:
            return "concentration-led"
        if top_share is not None and float(top_share) >= 0.30:
            return "concentration-led"
        if contributor_count is not None and gini is not None and turnover is not None:
            if float(contributor_count) >= 50 and float(gini) <= 0.45 and float(turnover) <= 0.35:
                return "distribution-led"
    except (TypeError, ValueError):
        pass

    return "mixed-signal"


def _confidence_context_block(metrics: Dict[str, Any]) -> str:
    lines = [
        f"Recent signal strength: {metrics.get('recent_signal_strength', 'unknown')}",
        f"Analyzed in fast mode: {'yes' if metrics.get('analysis_mode') == 'fast' else 'no'}",
        f"Time window expanded: {'yes' if metrics.get('window_expanded') else 'no'}",
        f"Metadata anomaly detected: {'yes' if metrics.get('metadata_anomaly_detected') else 'no'}",
        f"Low recent signal flag: {'yes' if metrics.get('low_recent_signal') else 'no'}",
        f"Insufficient recent data flag: {'yes' if metrics.get('insufficient_recent_data') else 'no'}",
        f"Classification confidence: {metrics.get('classification_confidence', 'unknown')}",
        f"Recommended validation mode: {metrics.get('recommended_validation_mode', 'none')}",
    ]
    return "\n".join(lines)


def _validation_hints(metrics: Dict[str, Any]) -> list[str]:
    hints: list[str] = []
    validation_mode = metrics.get("recommended_validation_mode")
    if validation_mode in {"rerun_full", "rerun_full_and_metadata_review"}:
        hints.append("rerun in full mode")
    if validation_mode in {"metadata_review", "rerun_full_and_metadata_review"}:
        hints.append("review metadata integrity")

    framing = _dominant_framing(metrics)
    if metrics.get("metric_reliability_warning"):
        hints.append("treat output cautiously: sample is very small or window expansion did not materially improve signal")
    if framing == "concentration-led":
        hints.append("inspect contributor concentration over a longer window")
    elif framing == "distribution-led":
        hints.append("compare current distribution against the historical baseline")
    elif framing == "mixed-signal":
        hints.append("compare concentration and turnover against a longer historical baseline")
    else:
        hints.append("treat the result as screening-grade until a broader rerun is completed")

    return hints[:3]


def _build_sdlc_context(metrics: Dict[str, Any]) -> str:
    selected_mode = metrics.get("sdlc_mode", "auto")
    effective_mode = metrics.get("effective_sdlc_mode", selected_mode)
    classification_status = metrics.get("classification_status", effective_mode)
    ai_score = metrics.get("ai_influence_score")

    lines = [
        f"This project is analyzed under the {effective_mode} SDLC mode.",
        f"Selected SDLC mode: {selected_mode}",
        f"Effective SDLC mode: {effective_mode}",
        f"Classification status: {classification_status}",
    ]

    if ai_score is not None:
        lines.append(f"AI Influence Score: {ai_score}")

    lines.extend(
        [
            "Interpret metrics accordingly:",
            "- In AI-assisted contexts, contribution patterns may not reflect actual authorship intent",
            "- If the classification is AI_DRIVEN: prefer framing such as 'metrics are more consistent with AI-driven or strongly AI-assisted contribution patterns' or 'signals suggest a more AI-intensive workflow'; do not state direct authorship causality",
            "- In hybrid contexts, interpret human and AI-aware signals together",
            "- If recent signal strength is weak or insufficient, treat conclusions as screening-grade only",
        ]
    )

    return "\n".join(lines)


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
    validation_hints = _validation_hints(metrics_dict)
    validation_hints_block = "\n".join(f"- {hint}" for hint in validation_hints)

    prompt = template.format(
        repo_name=repo_name,
        repo_url=repo_url,
        analysis_date=datetime.now(timezone.utc).isoformat(),
        sdlc_context_block=_build_sdlc_context(metrics_dict),
        metrics_block=metrics_block,
        signals_block=signals_block,
        dominant_framing=_dominant_framing(metrics_dict),
        confidence_context_block=_confidence_context_block(metrics_dict),
        validation_hints_block=validation_hints_block or "- no specific validation hint available",
        metric_reliability_warning="yes" if metrics_dict.get("metric_reliability_warning") else "no",
    )

    return prompt
