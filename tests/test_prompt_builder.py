from __future__ import annotations

import unittest

from bigua_analyzer.ai.prompt_builder import build_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_includes_adaptive_framing_and_confidence_structure(self) -> None:
        prompt = build_prompt(
            repo_name="example",
            repo_url="https://github.com/example/repo",
            metrics_dict={
                "analysis_mode": "fast",
                "analysis_window_days": 730,
                "window_expanded": True,
                "analyzed_commits": 12,
                "recent_signal_strength": "weak",
                "classification_status": "HYBRID",
                "classification_confidence": "very_low",
                "recommended_validation_mode": "rerun_full_and_metadata_review",
                "low_recent_signal": True,
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": True,
                "classification_guardrail_applied": True,
                "gini_coefficient": 0.72,
                "top_contributor_share": 0.41,
                "bus_factor_50p": 2,
                "developer_turnover": 0.18,
                "ai_influence_score": 0.58,
                "effective_sdlc_mode": "hybrid",
                "sdlc_mode": "auto",
            },
        )

        self.assertIn("Dominant framing to use:", prompt)
        self.assertIn("low-signal / insufficient-data", prompt)
        self.assertIn("Confidence context:", prompt)
        self.assertIn("Recent signal strength: weak", prompt)
        self.assertIn("Time window expanded: yes", prompt)
        self.assertIn("Metadata anomaly detected: yes", prompt)
        self.assertIn("Validation hints:", prompt)
        self.assertIn("rerun in full mode", prompt)
        self.assertIn("review metadata integrity", prompt)
        self.assertIn("## Confidence and limitations", prompt)
        self.assertIn("## Next validation step", prompt)

    def test_prompt_uses_distribution_led_framing_when_signals_are_broad(self) -> None:
        prompt = build_prompt(
            repo_name="example",
            repo_url="https://github.com/example/repo",
            metrics_dict={
                "analysis_mode": "fast",
                "recent_signal_strength": "strong",
                "insufficient_recent_data": False,
                "gini_coefficient": 0.31,
                "top_contributor_share": 0.11,
                "contributor_count": 240,
                "developer_turnover": 0.09,
                "effective_sdlc_mode": "human",
                "sdlc_mode": "auto",
            },
        )

        self.assertIn("distribution-led", prompt)


    def test_prompt_exposes_metric_reliability_warning_when_true(self) -> None:
        prompt = build_prompt(
            repo_name="example",
            repo_url="https://github.com/example/repo",
            metrics_dict={
                "analysis_mode": "fast",
                "analysis_window_days": 730,
                "window_expanded": True,
                "analyzed_commits": 8,
                "recent_signal_strength": "weak",
                "classification_status": "HYBRID",
                "classification_confidence": "very_low",
                "recommended_validation_mode": "rerun_full",
                "low_recent_signal": True,
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": False,
                "classification_guardrail_applied": False,
                "metric_reliability_warning": True,
                "effective_sdlc_mode": "hybrid",
                "sdlc_mode": "auto",
            },
        )

        self.assertIn("Metric reliability warning: yes", prompt)
        self.assertIn("treat output cautiously", prompt)

    def test_ai_driven_context_includes_non_causal_framing_hint(self) -> None:
        prompt = build_prompt(
            repo_name="example",
            repo_url="https://github.com/example/repo",
            metrics_dict={
                "analysis_mode": "fast",
                "recent_signal_strength": "strong",
                "insufficient_recent_data": False,
                "classification_status": "AI_DRIVEN",
                "effective_sdlc_mode": "ai",
                "sdlc_mode": "auto",
                "ai_influence_score": 0.75,
            },
        )

        self.assertIn("AI_DRIVEN", prompt)
        self.assertIn("do not state direct authorship causality", prompt)


if __name__ == "__main__":
    unittest.main()