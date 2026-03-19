from __future__ import annotations

import math
from typing import Any, Dict

from ..sdlc import clamp01
from .ai_influence import AIInfluenceDetails


def _mean_available(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _normalize_human_score(base_metrics: Dict[str, Any]) -> float | None:
    bus_factor = base_metrics.get("bus_factor_50p")
    gini = base_metrics.get("gini_coefficient")
    volatility = base_metrics.get("commit_volatility")
    turnover = base_metrics.get("developer_turnover")

    bus_score = None if bus_factor is None else clamp01(float(bus_factor) / 5.0)
    equality_score = None if gini is None else 1.0 - clamp01(float(gini))
    stability_score = None if volatility is None else 1.0 - clamp01(float(volatility) / 2.0)
    retention_score = None if turnover is None else 1.0 - clamp01(float(turnover))
    return _mean_available([bus_score, equality_score, stability_score, retention_score])


def _contributor_diversity_risk(base_metrics: Dict[str, Any]) -> float | None:
    contributor_count = base_metrics.get("contributor_count")
    gini = base_metrics.get("gini_coefficient")
    top_share = base_metrics.get("top_contributor_share")

    contributor_count_risk = None
    if contributor_count is not None:
        contributor_count_risk = 1.0 - clamp01(math.log(float(max(contributor_count, 1)), 10) / math.log(20, 10))

    return _mean_available([
        contributor_count_risk,
        None if gini is None else clamp01(float(gini)),
        None if top_share is None else clamp01(float(top_share)),
    ])


def compute_ai_aware_metrics(
    base_metrics: Dict[str, Any],
    ai_details: AIInfluenceDetails,
    effective_sdlc_mode: str,
) -> Dict[str, Any]:
    ai_score = clamp01(ai_details.ai_influence_score)
    style_uniformity = ai_details.style_uniformity_score
    metadata_signal = ai_details.metadata_signal_score

    aidr = ai_score

    bus_factor = base_metrics.get("bus_factor_50p")
    cbf = None if bus_factor is None else max(0.0, float(bus_factor) * (1.0 - ai_score))

    diversity_risk = _contributor_diversity_risk(base_metrics)
    amr = _mean_available([style_uniformity, diversity_risk])
    aich = style_uniformity
    aci = metadata_signal

    human_score = _normalize_human_score(base_metrics)
    ai_metrics_score = _mean_available([aidr, amr, aich, aci])

    hybrid_analysis_score = None
    if effective_sdlc_mode == "hybrid" and human_score is not None and ai_metrics_score is not None:
        hybrid_analysis_score = (human_score * (1.0 - ai_score)) + (ai_score * ai_metrics_score)

    mode_adjusted_analysis_score = None
    if effective_sdlc_mode == "human":
        mode_adjusted_analysis_score = human_score
    elif effective_sdlc_mode == "hybrid":
        mode_adjusted_analysis_score = hybrid_analysis_score
    elif effective_sdlc_mode == "ai":
        mode_adjusted_analysis_score = ai_metrics_score

    return {
        "aidr": round(aidr, 6),
        "cbf": None if cbf is None else round(cbf, 6),
        "amr": None if amr is None else round(amr, 6),
        "aich": None if aich is None else round(aich, 6),
        "aci": None if aci is None else round(aci, 6),
        "human_metrics_score": None if human_score is None else round(human_score, 6),
        "ai_metrics_score": None if ai_metrics_score is None else round(ai_metrics_score, 6),
        "hybrid_analysis_score": None if hybrid_analysis_score is None else round(hybrid_analysis_score, 6),
        "mode_adjusted_analysis_score": None if mode_adjusted_analysis_score is None else round(mode_adjusted_analysis_score, 6),
    }