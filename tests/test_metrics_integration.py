from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bigua_analyzer.analysis_scope import AnalysisConfig
from bigua_analyzer.ai.ai_influence import AIInfluenceDetails
from bigua_analyzer.metrics import collect_all_metrics, compute_traffic_light
from bigua_analyzer.perf import PerformanceRecorder


class MetricsIntegrationTests(unittest.TestCase):
    def _git(self, repo_dir: Path, *args: str, env: dict[str, str] | None = None) -> None:
        merged_env = os.environ.copy()
        if env is not None:
            merged_env.update(env)
        subprocess.run(["git", *args], cwd=repo_dir, check=True, capture_output=True, text=True, env=merged_env)

    def _commit_file(self, repo_dir: Path, relative_path: str, content: str, message: str, when: str | None = None) -> None:
        target = repo_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._git(repo_dir, "add", relative_path)
        env = None
        if when is not None:
            env = {
                "GIT_AUTHOR_DATE": when,
                "GIT_COMMITTER_DATE": when,
            }
        self._git(repo_dir, "commit", "-m", message, env=env)

    def _create_repo(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        repo_dir = Path(tmpdir.name)

        self._git(repo_dir, "init", "-b", "main")
        self._git(repo_dir, "config", "user.name", "Test Dev")
        self._git(repo_dir, "config", "user.email", "dev@example.com")

        self._commit_file(repo_dir, "README.md", "hello\n", "initial commit")
        self._commit_file(repo_dir, "scripts/agent_helper.py", "print('agent')\n", "update")

        return repo_dir

    def _create_repo_with_dated_commits(self, commits: list[tuple[str, str, str, str]]) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        repo_dir = Path(tmpdir.name)

        self._git(repo_dir, "init", "-b", "main")
        self._git(repo_dir, "config", "user.name", "Test Dev")
        self._git(repo_dir, "config", "user.email", "dev@example.com")

        for relative_path, content, message, when in commits:
            self._commit_file(repo_dir, relative_path, content, message, when=when)

        return repo_dir

    def test_human_mode_keeps_ai_metrics_optional(self) -> None:
        repo_dir = self._create_repo()
        metrics = collect_all_metrics(repo_dir, "main", sdlc_mode="human")
        self.assertEqual(metrics["sdlc_mode"], "human")
        self.assertEqual(metrics["effective_sdlc_mode"], "human")
        self.assertIn("ai_influence_score", metrics)
        self.assertNotIn("ai_metrics", metrics)

    def test_human_mode_skips_expensive_ai_repository_scan(self) -> None:
        repo_dir = self._create_repo()
        with patch("bigua_analyzer.metrics.collect_repository_ai_data") as mock_collect:
            collect_all_metrics(repo_dir, "main", sdlc_mode="human")
            mock_collect.assert_not_called()

    def test_hybrid_mode_adds_ai_metrics(self) -> None:
        repo_dir = self._create_repo()
        metrics = collect_all_metrics(repo_dir, "main", sdlc_mode="hybrid")
        self.assertEqual(metrics["effective_sdlc_mode"], "hybrid")
        self.assertIn("ai_metrics", metrics)
        self.assertIn("aidr", metrics["ai_metrics"])
        self.assertIn("hybrid_analysis_score", metrics["ai_metrics"])

    def test_ai_intermediate_outputs_are_exposed(self) -> None:
        repo_dir = self._create_repo()
        metrics = collect_all_metrics(repo_dir, "main", sdlc_mode="auto")

        self.assertIn("ai_influence_confidence", metrics)
        self.assertIn("ai_influence_rationale", metrics)
        self.assertIn("ai_historical_constraint_applied", metrics)
        self.assertIn("ai_legacy_variance_protection_applied", metrics)
        self.assertIn("ai_h1_textual_markers", metrics)
        self.assertIn("ai_h2_explicit_attribution", metrics)
        self.assertIn("ai_h3_temporal_prior", metrics)
        self.assertIn("ai_h4_burstiness", metrics)
        self.assertIn("ai_h5_style_shift", metrics)
        self.assertIn("ai_h6_large_low_discussion", metrics)
        self.assertIn("ai_h7_output_asymmetry", metrics)
        self.assertIn("ai_h8_tooling_footprint", metrics)
        self.assertIn("ai_h9_generated_text_pattern", metrics)

    def test_profiler_captures_breakdown_for_auto_mode(self) -> None:
        repo_dir = self._create_repo()
        profiler = PerformanceRecorder()

        collect_all_metrics(repo_dir, "main", sdlc_mode="auto", profiler=profiler)

        timings = profiler.snapshot_ms()
        self.assertIn("repository_basics_ms", timings)
        self.assertIn("standard_metric_calculation_ms", timings)
        self.assertIn("commit_history_read_ms", timings)
        self.assertIn("commit_history_parse_ms", timings)
        self.assertIn("file_tree_read_ms", timings)
        self.assertIn("temporal_aggregation_ms", timings)
        self.assertIn("ai_inference_ms", timings)

    def test_fast_mode_exposes_scope_transparency(self) -> None:
        repo_dir = self._create_repo()

        metrics = collect_all_metrics(
            repo_dir,
            "main",
            sdlc_mode="auto",
            analysis_config=AnalysisConfig.resolve(mode="fast", sample_size=1),
            analysis_cache_dir=repo_dir / ".analysis-cache",
        )

        self.assertEqual(metrics["analysis_mode"], "fast")
        self.assertEqual(metrics["analysis_sampling_strategy"], "time-bucket-sample")
        self.assertEqual(metrics["commit_scope_total_commits"], 2)
        self.assertEqual(metrics["commit_scope_analyzed_commits"], 1)
        self.assertTrue(metrics["commit_scope_is_approximate"])
        self.assertEqual(metrics["analysis_window_days"], 730)
        self.assertTrue(metrics["window_expanded"])
        self.assertEqual(metrics["candidate_recent_commits"], 2)
        self.assertEqual(metrics["analyzed_commits"], 1)
        self.assertEqual(metrics["sample_size_used"], 1)
        self.assertEqual(metrics["recent_signal_strength"], "weak")
        self.assertEqual(metrics["classification_confidence"], "very_low")
        self.assertEqual(metrics["data_quality_status"], "screening_grade_review_recommended")
        self.assertEqual(metrics["recommended_validation_mode"], "rerun_full")
        self.assertTrue(metrics["low_recent_signal"])
        self.assertFalse(metrics["insufficient_recent_data"])
        self.assertFalse(metrics["classification_guardrail_applied"])
        self.assertTrue(metrics["metric_reliability_warning"])
        self.assertEqual(metrics["traffic_light"], "orange")
        self.assertEqual(metrics["traffic_light_score"], 1)
        self.assertFalse(metrics["is_research_grade"])

    def test_fast_mode_expands_window_when_recent_signal_is_insufficient(self) -> None:
        repo_dir = self._create_repo_with_dated_commits(
            [
                ("README.md", "old\n", "old commit", "2025-01-10T12:00:00+00:00"),
            ]
        )

        metrics = collect_all_metrics(
            repo_dir,
            "main",
            sdlc_mode="human",
            analysis_config=AnalysisConfig.resolve(mode="fast", time_window_days=365, sample_size=240),
            analysis_cache_dir=repo_dir / ".analysis-cache",
        )

        self.assertEqual(metrics["analysis_window_days"], 730)
        self.assertTrue(metrics["window_expanded"])
        self.assertEqual(metrics["candidate_recent_commits"], 1)
        self.assertEqual(metrics["analyzed_commits"], 1)
        self.assertEqual(metrics["recent_signal_strength"], "weak")
        self.assertFalse(metrics["insufficient_recent_data"])
        self.assertEqual(metrics["classification_status"], "HUMAN")
        self.assertEqual(metrics["recommended_validation_mode"], "rerun_full")

    def test_fast_mode_marks_insufficient_after_all_window_fallbacks(self) -> None:
        repo_dir = self._create_repo_with_dated_commits(
            [
                ("README.md", "very old\n", "very old commit", "2022-01-10T12:00:00+00:00"),
            ]
        )

        metrics = collect_all_metrics(
            repo_dir,
            "main",
            sdlc_mode="human",
            analysis_config=AnalysisConfig.resolve(mode="fast", time_window_days=365, sample_size=240),
            analysis_cache_dir=repo_dir / ".analysis-cache",
        )

        self.assertEqual(metrics["analysis_window_days"], 1095)
        self.assertTrue(metrics["window_expanded"])
        self.assertEqual(metrics["candidate_recent_commits"], 0)
        self.assertEqual(metrics["analyzed_commits"], 0)
        self.assertEqual(metrics["recent_signal_strength"], "insufficient")
        self.assertEqual(metrics["classification_status"], "insufficient_recent_data")
        self.assertEqual(metrics["effective_sdlc_mode"], "insufficient_recent_data")
        self.assertEqual(metrics["classification_confidence"], "insufficient")
        self.assertEqual(metrics["data_quality_status"], "insufficient_recent_data")
        self.assertEqual(metrics["recommended_validation_mode"], "rerun_full")
        self.assertTrue(metrics["insufficient_recent_data"])
        self.assertEqual(metrics["traffic_light"], "red")
        self.assertEqual(metrics["traffic_light_score"], 0)
        self.assertFalse(metrics["is_research_grade"])

    def test_boundary_scores_apply_classification_guardrail_when_signal_is_not_strong(self) -> None:
        repo_dir = self._create_repo()
        ai_details = AIInfluenceDetails(
            ai_influence_score=0.58,
            ai_influence_confidence=0.8,
            weighted_base_score=0.48,
            temporal_adoption_prior=0.1,
            temporal_anomaly_weight=1.0,
            dominant_activity_period="2024+",
            historical_constraint_applied=False,
            legacy_variance_protection_applied=False,
            ai_influence_rationale=["test"],
            ai_h1_textual_markers=0.0,
            ai_h2_explicit_attribution=0.0,
            ai_h3_temporal_prior=0.1,
            ai_h4_burstiness=0.0,
            ai_h5_style_shift=0.4,
            ai_h6_large_low_discussion=0.0,
            ai_h7_output_asymmetry=0.0,
            ai_h8_tooling_footprint=0.0,
            ai_h9_generated_text_pattern=0.0,
            commit_pattern_score=0.3,
            temporal_anomaly_score=0.2,
            temporal_anomaly_score_raw=0.2,
            style_uniformity_score=0.4,
            metadata_signal_score=0.1,
        )

        with patch("bigua_analyzer.metrics.compute_ai_influence_details", return_value=ai_details):
            metrics = collect_all_metrics(
                repo_dir,
                "main",
                sdlc_mode="auto",
                analysis_config=AnalysisConfig.resolve(mode="fast", sample_size=1),
                analysis_cache_dir=repo_dir / ".analysis-cache",
            )

        self.assertTrue(metrics["classification_guardrail_applied"])
        self.assertEqual(metrics["recommended_validation_mode"], "rerun_full")
        self.assertIn(metrics["classification_confidence"], {"very_low", "low"})
        self.assertEqual(metrics["traffic_light"], "orange")

    def test_analysis_cache_is_reused_on_second_run(self) -> None:
        repo_dir = self._create_repo()
        cache_dir = repo_dir / ".analysis-cache"
        config = AnalysisConfig.resolve(mode="fast", sample_size=1)

        first = collect_all_metrics(
            repo_dir,
            "main",
            sdlc_mode="auto",
            analysis_config=config,
            analysis_cache_dir=cache_dir,
        )
        second = collect_all_metrics(
            repo_dir,
            "main",
            sdlc_mode="auto",
            analysis_config=config,
            analysis_cache_dir=cache_dir,
        )

        self.assertFalse(first["analysis_cache_hit"])
        self.assertTrue(second["analysis_cache_hit"])


class TrafficLightComputationTests(unittest.TestCase):
    def test_red_has_highest_priority(self) -> None:
        traffic_light = compute_traffic_light(
            {
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": True,
                "low_recent_signal": False,
                "metric_reliability_warning": False,
                "classification_confidence": "high",
                "recent_signal_strength": "strong",
                "window_expanded": False,
            }
        )

        self.assertEqual(traffic_light, "red")

    def test_orange_beats_yellow_when_both_match(self) -> None:
        traffic_light = compute_traffic_light(
            {
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": False,
                "low_recent_signal": False,
                "metric_reliability_warning": True,
                "classification_confidence": "moderate",
                "recent_signal_strength": "moderate",
                "window_expanded": True,
            }
        )

        self.assertEqual(traffic_light, "orange")

    def test_yellow_for_moderate_or_window_expanded_cases(self) -> None:
        traffic_light = compute_traffic_light(
            {
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": False,
                "low_recent_signal": False,
                "metric_reliability_warning": False,
                "classification_confidence": "high",
                "recent_signal_strength": "strong",
                "window_expanded": True,
            }
        )

        self.assertEqual(traffic_light, "yellow")

    def test_green_only_for_research_grade_cases(self) -> None:
        traffic_light = compute_traffic_light(
            {
                "insufficient_recent_data": False,
                "metadata_anomaly_detected": False,
                "low_recent_signal": False,
                "metric_reliability_warning": False,
                "classification_confidence": "high",
                "recent_signal_strength": "strong",
                "window_expanded": False,
            }
        )

        self.assertEqual(traffic_light, "green")

if __name__ == "__main__":
    unittest.main()