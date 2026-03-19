# Changelog

This file tracks notable changes to bigua-analyzer.

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