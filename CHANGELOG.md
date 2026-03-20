# Changelog

This file tracks notable changes to bigua-analyzer.

## Unreleased

## v0.4.3

 fast mode and scalable analysis for very large repositories.

- Added FAST-mode signal quality guardrails with automatic fallback across 365, 730, and 1095 day windows when recent activity is too sparse for screening.
- Added explicit output transparency and quality fields for screening interpretation, including `analysis_window_days`, `window_expanded`, `candidate_recent_commits`, `analyzed_commits`, `sample_size_used`, `recent_signal_strength`, `classification_status`, `classification_confidence`, `recommended_validation_mode`, `low_recent_signal`, `insufficient_recent_data`, and `classification_guardrail_applied`.
- Added `metric_reliability_warning` and the intermediate quality status `screening_grade_review_recommended` for analytically fragile but structurally valid outputs that should be reviewed before being used as evidence.
- Added a traffic-light interpretation layer with `traffic_light` (`green`, `yellow`, `orange`, `red`), `traffic_light_score`, and `is_research_grade` as stable derived fields for filtering, charting, and research-quality dataset selection.
- Kept `metadata_anomaly_detected` reserved for structurally inconsistent or internally contradictory outputs instead of using it as a catch-all for low-sample oddities.
- Kept the SDLC classification guardrail targeted at scores within `±0.05` of the decision thresholds for weak or moderate recent signal.
- Added `insufficient_recent_data` as an explicit effective SDLC outcome when FAST fallback windows still produce no usable recent sample.
- Reworked LLM prompt generation to adapt framing by signal quality, separate confidence and limitations more clearly, and label low-signal or review-recommended results as screening-grade only.
- Tightened report wording for `AI_DRIVEN` classifications to avoid causal overstatement and favor language based on consistency of observed metrics rather than direct authorship claims.
- Added regression tests covering FAST fallback behavior, confidence and quality field emission, guardrail behavior near thresholds, and prompt wording for low-signal and AI-driven cases.
- Added `--mode full|fast` while keeping `full` as the default behavior for backward compatibility.
- Added `--since`, `--time-window`, and `--sample-size` so large repositories can be analyzed with explicit temporal scoping and bounded commit sampling.
- Added time-bucketed commit sampling in fast mode to preserve chronological coverage while reducing expensive history scans.
- Added a persistent analysis cache for scoped commit listings and AI scan inputs, plus a `--no-analysis-cache` escape hatch.
- Reduced the cost of history-derived metrics by reusing scoped commit metadata across bus factor, volatility, turnover, and contributor concentration calculations.
- Added explicit output transparency fields including `analysis_mode`, `analysis_sampling_strategy`, `commit_scope_total_commits`, and `commit_scope_analyzed_commits`.
- Added tests covering fast-mode CLI parsing, scoped output metadata, and analysis cache reuse.

## v0.4.2

Release focus: performance observability and benchmarking support for large repositories.

- Added pipeline performance instrumentation with per-stage timing breakdown for analysis and report generation internals.
- Added `--profile` mode to print compact per-repository timing summaries during analysis runs.
- Added profiling coverage for expensive steps including clone/fetch, commit history read/parse, standard metric calculation, temporal aggregation, AI inference, and report LLM/render stages.
- Added `scripts/benchmark_workers.py` to benchmark dataset throughput across different worker counts.
- Kept backward-compatible output defaults by emitting `performance` metrics only when profiling is explicitly enabled.
- Added tests covering profile flag parsing, profiling breakdown capture, and report generation flow stability.

## v0.4.1

Release focus: patch improvements for maintainability, typing safety, and runtime behavior.

- Removed direct progress printing from core repository analysis to keep programmatic usage clean and avoid noisy interleaved output in multi-threaded dataset runs.
- Reduced worst-case runtime for explicit `human` mode by skipping expensive repository-wide AI data scans while preserving AI influence output fields.
- Added a dedicated `EffectiveSDLCMode` type alias and narrowed return typing in SDLC mode resolution to avoid static type ambiguity.
- Centralized duration/elapsed/ETA formatting in shared utilities to remove duplicated logic across CLI and report generation paths.
- Added integration test coverage to ensure `human` mode does not trigger the expensive AI repository scan.

## v0.4.0

Release focus: hybrid SDLC analysis, AI-aware repository metrics, and AI Influence Score refinement (v1.2/v1.3 calibration).

- Added `--sdlc-mode` with `auto`, `human`, `hybrid`, and `ai` modes.
- Added repository-level AI Influence Score with weighted heuristics and weak temporal adoption prior.
- Added AI-aware metrics: AIDR, CBF, AMR, AICH, and ACI.
- Added effective SDLC mode resolution for `auto` mode.
- Added SDLC and AI context to LLM analysis prompts.
- Extended JSONL and CSV outputs with additive SDLC and AI-related fields.
- Added tests covering CLI parsing, score computation, SDLC integration, and output compatibility.
- Downscaled temporal anomaly signals for very young repositories while keeping the temporal adoption prior as a weak standalone signal.
- Added historical feasibility constraints for repositories dominated by pre-2022 activity and legacy variance protection for large long-lived projects.
- Added `ai_influence_confidence` and exposed mandatory intermediate AI heuristic outputs `ai_h1` through `ai_h9`.
- Added explicit flags `ai_historical_constraint_applied` and `ai_legacy_variance_protection_applied`.
- Changed `ai_influence_rationale` to a signal-oriented explanation list derived from dominant heuristics.
- Hardened calibration for small repositories by reducing style and sparse metadata sensitivity.
- Preserved v1.2 safeguards while adding controlled modern-context sensitivity boosts for recent repositories with sufficient supporting signals.
- Added output asymmetry boost for low-contributor, high-output repositories under modern context.
- Added confidence-aware conservative boundary and hard boost cap to avoid aggressive or unrealistic classifications.
- Extended rationale generation to include applied v1.3 boost and boundary factors.
- Added regression tests covering temporal downscaling, historical plausibility, confidence behavior, intermediate-output visibility, and v1.3 controlled sensitivity behavior.

## v0.3.0

- Added multi-LLM integration for report generation.
- Added page info.
- Added important OSS documents kit.

## v0.2.0

Release focus: new metrics and multithreading.

- Added contributor inequality and developer turnover metrics.
- Improved metric documentation.
- Added parallel dataset processing with configurable worker count.
- Improved CLI usage documentation for open source users.
- Fixed default output path behavior for bare `--out` names.

## v0.1.0

Initial dataset analysis release.

- Introduced the first CLI workflow for analyzing repositories.
- Added dataset processing and output generation.
- Added the initial metrics and research-oriented project documentation.