from __future__ import annotations

import unittest

from bigua_analyzer.ai.ai_influence import compute_ai_influence_details
from bigua_analyzer.sdlc import resolve_effective_sdlc_mode


class AIInfluenceTests(unittest.TestCase):
    def test_temporal_prior_is_weak_context_only(self) -> None:
        repo_data = {
            "commits": [
                {"message": "implement parser", "timestamp": 1735689600, "author": "Dev <dev@example.com>", "files_changed": 1, "lines_changed": 10},
                {"message": "document data model", "timestamp": 1735776000, "author": "Maintainer <maintainer@example.com>", "files_changed": 1, "lines_changed": 8},
            ],
            "file_paths": [
                "README.md",
                "src/app.py",
                "docs/architecture.adoc",
                "config/tooling.yaml",
            ],
        }

        details = compute_ai_influence_details(repo_data)

        self.assertEqual(details.temporal_adoption_prior, 0.10)
        self.assertLess(details.ai_influence_score, 0.30)
        self.assertGreaterEqual(details.ai_influence_confidence, 0.0)
        self.assertLessEqual(details.ai_influence_confidence, 1.0)
        self.assertEqual(resolve_effective_sdlc_mode("auto", details.ai_influence_score), "human")

    def test_missing_subscores_are_renormalized(self) -> None:
        repo_data = {
            "commits": [],
            "file_paths": [".github/workflows/ci.yml", "AGENTS.md", "src/agent.py"],
        }

        details = compute_ai_influence_details(repo_data)

        self.assertIsNone(details.commit_pattern_score)
        self.assertIsNone(details.temporal_anomaly_score)
        self.assertIsNotNone(details.style_uniformity_score)
        self.assertIsNotNone(details.metadata_signal_score)
        self.assertGreaterEqual(details.ai_influence_score, 0.0)
        self.assertLessEqual(details.ai_influence_score, 1.0)
        self.assertIsInstance(details.ai_influence_rationale, list)
        self.assertGreaterEqual(details.ai_influence_confidence, 0.0)

    def test_temporal_anomaly_is_downscaled_for_new_repositories(self) -> None:
        commits = [
            {"message": "update", "timestamp": 1735689600 + (i * 1800), "author": "Dev <dev@example.com>", "files_changed": 2, "lines_changed": 30}
            for i in range(12)
        ]
        base_data = {
            "commits": commits,
            "file_paths": ["src/app.py", "README.md", ".github/workflows/ci.yml"],
        }

        details_new = compute_ai_influence_details({**base_data, "repo_age_days": 1})
        details_mature = compute_ai_influence_details({**base_data, "repo_age_days": 180})

        self.assertIsNotNone(details_new.temporal_anomaly_score_raw)
        self.assertIsNotNone(details_new.temporal_anomaly_score)
        self.assertLess(details_new.temporal_anomaly_score, details_new.temporal_anomaly_score_raw)
        self.assertLess(details_new.temporal_anomaly_weight, 1.0)
        self.assertAlmostEqual(details_mature.temporal_anomaly_weight, 1.0, places=6)
        self.assertTrue(details_new.ai_influence_rationale)

    def test_pre_2022_repositories_are_not_classified_as_ai_driven(self) -> None:
        commits = [
            {"message": "copilot assisted refactor", "timestamp": 1609459200 + (i * 86400), "author": "Dev <dev@example.com>", "files_changed": 16, "lines_changed": 450}
            for i in range(80)
        ]
        repo_data = {
            "commits": commits,
            "file_paths": [
                "src/agent.py",
                "src/copilot_adapter.py",
                ".github/workflows/ci.yml",
                "README.md",
            ],
            "repo_age_days": 5000,
        }

        details = compute_ai_influence_details(repo_data)

        self.assertEqual(details.dominant_activity_period, "before-2022")
        self.assertLess(details.ai_influence_score, 0.60)
        self.assertNotEqual(resolve_effective_sdlc_mode("auto", details.ai_influence_score), "ai")
        self.assertTrue(details.historical_constraint_applied)
        self.assertIn("historical feasibility constraint", details.ai_influence_rationale)

    def test_small_repositories_have_lower_confidence_and_scaled_style_signal(self) -> None:
        file_paths = ["src/app.py", "src/core.py", "README.md", "docs/guide.md", ".github/workflows/ci.yml"]
        small_repo = {
            "commits": [
                {"message": f"update {i}", "timestamp": 1735689600 + i, "author": "Dev <dev@example.com>", "files_changed": 2, "lines_changed": 20}
                for i in range(10)
            ],
            "file_paths": file_paths,
            "repo_age_days": 10,
        }
        larger_repo = {
            "commits": [
                {"message": f"feature {i}", "timestamp": 1735689600 + i, "author": "Dev <dev@example.com>", "files_changed": 2, "lines_changed": 20}
                for i in range(120)
            ],
            "file_paths": file_paths,
            "repo_age_days": 1200,
        }

        small_details = compute_ai_influence_details(small_repo)
        larger_details = compute_ai_influence_details(larger_repo)

        self.assertLess(small_details.ai_influence_confidence, larger_details.ai_influence_confidence)
        self.assertIsNotNone(small_details.ai_h5_style_shift)
        self.assertIsNotNone(larger_details.ai_h5_style_shift)
        self.assertLess(small_details.ai_h5_style_shift, larger_details.ai_h5_style_shift)

    def test_modern_small_repo_receives_controlled_sensitivity_boost(self) -> None:
        repo_data = {
            "commits": [
                {
                    "message": "copilot assisted update",
                    "timestamp": 1735689600 + (i * 3600),
                    "author": f"Dev{i % 2} <dev{i % 2}@example.com>",
                    "files_changed": 8,
                    "lines_changed": 220,
                }
                for i in range(40)
            ],
            "file_paths": [
                "src/core.py",
                "src/agent_integration.py",
                "scripts/copilot_helper.py",
                "README.md",
                "docs/guide.md",
            ],
            "repo_age_days": 180,
            "contributor_count": 2,
        }

        details = compute_ai_influence_details(repo_data)

        self.assertGreaterEqual(details.ai_influence_score, 0.30)
        self.assertLess(details.ai_influence_score, 0.70)
        self.assertIn("modern development context", details.ai_influence_rationale)
        self.assertIn("high output asymmetry", details.ai_influence_rationale)

    def test_low_confidence_applies_conservative_adjustment(self) -> None:
        repo_data = {
            "commits": [
                {
                    "message": "update",
                    "timestamp": 1735689600 + i,
                    "author": "Dev <dev@example.com>",
                    "files_changed": 10,
                    "lines_changed": 260,
                }
                for i in range(30)
            ],
            "file_paths": [],
            "repo_age_days": 60,
            "contributor_count": 1,
        }

        details = compute_ai_influence_details(repo_data)

        self.assertLess(details.ai_influence_confidence, 0.4)
        self.assertIn("low-confidence evidence adjustment", details.ai_influence_rationale)
        self.assertLess(details.ai_influence_score, 0.7)

    def test_legacy_variance_protection_flag_is_exposed(self) -> None:
        repo_data = {
            "commits": [
                {"message": f"feature {i}", "timestamp": 1136073600 + (i * 86400), "author": f"Dev{i % 20} <dev{i % 20}@example.com>", "files_changed": 10, "lines_changed": 300}
                for i in range(1200)
            ],
            "file_paths": [
                "src/core.py",
                "src/legacy/module.py",
                "scripts/agent_helper.py",
                ".github/workflows/ci.yml",
                "README.md",
            ],
            "repo_age_days": 7000,
        }

        details = compute_ai_influence_details(repo_data)

        self.assertTrue(details.legacy_variance_protection_applied)


if __name__ == "__main__":
    unittest.main()