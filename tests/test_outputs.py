from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bigua_analyzer.io_utils import write_csv, write_jsonl
from bigua_analyzer.models import RepoResult, RepoSpec


class OutputCompatibilityTests(unittest.TestCase):
    def test_csv_flattens_nested_ai_metrics(self) -> None:
        result = RepoResult(
            repo=RepoSpec(url="https://github.com/example/repo"),
            ok=True,
            metrics={
                "sdlc_mode": "hybrid",
                "effective_sdlc_mode": "hybrid",
                "ai_influence_score": 0.42,
                "ai_metrics": {"aidr": 0.42, "cbf": 1.1},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "results.csv"
            write_csv([result], out_path)

            df = pd.read_csv(out_path)
            self.assertIn("ai_metrics_aidr", df.columns)
            self.assertIn("ai_metrics_cbf", df.columns)
            self.assertEqual(df.loc[0, "effective_sdlc_mode"], "hybrid")

    def test_jsonl_preserves_nested_ai_metrics(self) -> None:
        result = RepoResult(
            repo=RepoSpec(url="https://github.com/example/repo"),
            ok=True,
            metrics={
                "effective_sdlc_mode": "ai",
                "ai_metrics": {"aidr": 0.8, "aci": 0.7},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "results.jsonl"
            write_jsonl([result], out_path)

            payload = json.loads(out_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["metrics"]["effective_sdlc_mode"], "ai")
            self.assertEqual(payload["metrics"]["ai_metrics"]["aidr"], 0.8)


if __name__ == "__main__":
    unittest.main()