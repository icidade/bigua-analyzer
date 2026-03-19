from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bigua_analyzer.analysis_scope import AnalysisConfig
from bigua_analyzer.metrics import collect_all_metrics
from bigua_analyzer.perf import PerformanceRecorder


class MetricsIntegrationTests(unittest.TestCase):
    def _git(self, repo_dir: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=repo_dir, check=True, capture_output=True, text=True)

    def _create_repo(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        repo_dir = Path(tmpdir.name)

        self._git(repo_dir, "init", "-b", "main")
        self._git(repo_dir, "config", "user.name", "Test Dev")
        self._git(repo_dir, "config", "user.email", "dev@example.com")

        (repo_dir / "README.md").write_text("hello\n", encoding="utf-8")
        self._git(repo_dir, "add", "README.md")
        self._git(repo_dir, "commit", "-m", "initial commit")

        (repo_dir / "scripts").mkdir()
        (repo_dir / "scripts" / "agent_helper.py").write_text("print('agent')\n", encoding="utf-8")
        self._git(repo_dir, "add", "scripts/agent_helper.py")
        self._git(repo_dir, "commit", "-m", "update")

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


if __name__ == "__main__":
    unittest.main()