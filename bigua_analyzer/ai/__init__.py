"""AI-assisted repository analysis report generation."""

from .ai_influence import AIInfluenceDetails, compute_ai_influence, compute_ai_influence_details
from .ai_metrics import compute_ai_aware_metrics
from .report_generator import generate_report, generate_reports

__all__ = [
    "AIInfluenceDetails",
    "compute_ai_aware_metrics",
    "compute_ai_influence",
    "compute_ai_influence_details",
    "generate_report",
    "generate_reports",
]
