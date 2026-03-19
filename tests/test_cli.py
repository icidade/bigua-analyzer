from __future__ import annotations

import unittest

from bigua_analyzer.cli import _build_parser


class CLISdlcModeTests(unittest.TestCase):
    def test_analyze_defaults_to_auto_mode(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["analyze", "https://github.com/example/repo"])
        self.assertEqual(args.sdlc_mode, "auto")

    def test_analyze_accepts_explicit_sdlc_mode(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "analyze",
            "https://github.com/example/repo",
            "--sdlc-mode",
            "hybrid",
        ])
        self.assertEqual(args.sdlc_mode, "hybrid")


if __name__ == "__main__":
    unittest.main()