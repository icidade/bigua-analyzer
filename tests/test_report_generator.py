from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from bigua_analyzer.ai.report_generator import generate_report


class ReportGeneratorTests(unittest.TestCase):
    def test_generate_report_writes_markdown_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "metrics.csv"
            out_md = Path(tmpdir) / "report.md"
            out_html = Path(tmpdir) / "report.html"

            df = pd.DataFrame(
                [
                    {
                        "url": "https://github.com/example/repo",
                        "ref": "main",
                        "repo_id": "example/repo",
                        "ok": True,
                        "error": None,
                        "commit_count": 10,
                        "effective_sdlc_mode": "hybrid",
                    }
                ]
            )
            df.to_csv(csv_path, index=False)

            with patch("bigua_analyzer.ai.report_generator.call_llm", return_value="# Report\n\nhello"):
                markdown = generate_report(csv_path=csv_path, out_md=out_md, out_html=out_html)

            self.assertIn("# Report", markdown)
            self.assertTrue(out_md.exists())
            self.assertTrue(out_html.exists())


if __name__ == "__main__":
    unittest.main()