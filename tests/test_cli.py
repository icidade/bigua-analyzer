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

    def test_analyze_accepts_profile_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "analyze",
            "https://github.com/example/repo",
            "--profile",
        ])
        self.assertTrue(args.profile)

    def test_analyze_accepts_fast_scope_arguments(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "analyze",
            "https://github.com/example/repo",
            "--mode",
            "fast",
            "--time-window",
            "180",
            "--sample-size",
            "64",
            "--no-analysis-cache",
        ])
        self.assertEqual(args.mode, "fast")
        self.assertEqual(args.time_window, 180)
        self.assertEqual(args.sample_size, 64)
        self.assertTrue(args.no_analysis_cache)


if __name__ == "__main__":
    unittest.main()