from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bigua_analyzer.visualization import generate_all_plots


class VisualizationModuleTests(unittest.TestCase):
    def test_generate_all_plots_writes_expected_files(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "url": "https://github.com/example/repo-a",
                    "repo_id": "example__repo-a",
                    "gini_coefficient": 0.6,
                    "bus_factor_50p": 3,
                    "contributor_count": 40,
                    "developer_turnover": 0.2,
                    "release_cadence_days": 14,
                    "ai_influence_score": 0.4,
                    "traffic_light": "green",
                },
                {
                    "url": "https://github.com/example/repo-b",
                    "repo_id": "example__repo-b",
                    "gini_coefficient": 0.4,
                    "bus_factor_50p": 6,
                    "contributor_count": 120,
                    "developer_turnover": 0.1,
                    "release_cadence_days": 8,
                    "ai_influence_score": 0.65,
                    "traffic_light": "yellow",
                },
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "input.csv"
            out_dir = Path(tmpdir) / "plots"
            df.to_csv(csv_path, index=False)

            generate_all_plots(str(csv_path), str(out_dir))

            expected = [
                "gini_vs_bus_factor.png",
                "ai_influence_distribution.png",
                "repo_classification.png",
                "turnover_vs_contributors.png",
                "release_vs_ai.png",
                "radar_example__repo-a.png",
                "radar_example__repo-b.png",
                "traffic_light_example__repo-a.png",
                "traffic_light_example__repo-b.png",
            ]
            for filename in expected:
                self.assertTrue((out_dir / filename).exists(), msg=filename)


if __name__ == "__main__":
    unittest.main()
