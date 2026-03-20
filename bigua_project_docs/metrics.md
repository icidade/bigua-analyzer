# bigua-analyzer — Metrics Catalogue

## Core Ecosystem Metrics

### Commit Volatility

Measures irregularity in commit frequency over time.

Definition:
Coefficient of variation of commits per month.

Purpose:
Detect bursts or drops in development activity.

Interpretation:
Higher values may indicate unstable development activity.


---

### Contributor Concentration

Measures how much development depends on a small number of contributors.

Possible methods:

- Top contributor share
- Bus factor estimation (50% and 75%)

Purpose:

Identify projects where a small group carries most development activity.

Interpretation:

High concentration may indicate increased ecosystem fragility.


---

### Core Maintainer Continuity (Recent Bus Factor Activity)

Measures the recent activity of the core contributor set.

Method:

1. Consider commits within a recent time window (default: 365 days).
2. Identify the minimal contributor set responsible for:
   - 50% of commits
   - 75% of commits
3. Measure the median number of days since the last commit of these contributors.

Metrics produced:

- recent_bus_factor_50p_median_inactivity_days
- recent_bus_factor_75p_median_inactivity_days

Purpose:

Detect potential degradation of the core contributor ecosystem.

Interpretation:

Higher values may indicate loss of active maintainers or declining project continuity.


---

### Release Cadence Stability

Measures how regularly a project produces releases.

Two complementary metrics are used:

Historical cadence

- `release_cadence_days`

Definition:  
Average number of days between all Git tags across the entire repository history.

Purpose:  
Provide a long-term view of the project’s release discipline.

Interpretation:  
Higher values may indicate slower or irregular release cycles.


Recent cadence

- `recent_release_cadence_days`

Definition:  
Average number of days between Git tags created within the last 365 days.

Purpose:  
Capture the **current release rhythm**, which may differ from the historical average.

Interpretation:  
A significant difference between historical and recent cadence may indicate:

- slowing development activity  
- reduced maintainer availability  
- project transition or decline

---

## Supporting Metrics

These metrics provide contextual information about the repository.

- repo_age_days
- commit_count
- contributor_count

They help normalize and interpret ecosystem signals.


---

## Signal Quality Interpretation Layer (Traffic Light)

This layer provides a simple, explicit quality classification for repository-level outputs.
It is a pure interpretation layer and does not modify AI score, SDLC classification, or signal-strength computation.

Primary field:

- `traffic_light`: one of `green`, `yellow`, `orange`, `red`

Derived fields:

- `traffic_light_score`:
  - green = 3
  - yellow = 2
  - orange = 1
  - red = 0
- `is_research_grade`: `true` when `traffic_light == green`, otherwise `false`

Rule priority (first match wins):

1. RED (do not trust / reprocess required)
   - `insufficient_recent_data == true`
   - OR `metadata_anomaly_detected == true`

2. ORANGE (screening only, low reliability)
   - `low_recent_signal == true`
   - OR `classification_confidence` in `low`, `very_low`
   - OR `metric_reliability_warning == true`

3. YELLOW (usable with caution)
   - `recent_signal_strength == moderate`
   - OR `classification_confidence == moderate`
   - OR `window_expanded == true`

4. GREEN (research-grade signal)
   - Assigned when none of the higher-priority conditions match.
   - In practice, this corresponds to strong/high confidence paths without critical quality flags.

Implementation notes:

- Computed by `compute_traffic_light(row: dict) -> str`.
- Uses only already-computed quality fields.
- Deterministic and stable for charting and dataset filtering.

Typical uses:

- filter high-quality rows for research/paper plots (`traffic_light == green`)
- separate screening-only rows (`orange`) from stronger evidence (`green`)
- color scatter or comparison charts via `traffic_light` / `traffic_light_score`

Example CSV row (selected quality columns):

```csv
url,analysis_mode,analysis_window_days,window_expanded,analyzed_commits,recent_signal_strength,classification_confidence,low_recent_signal,insufficient_recent_data,metadata_anomaly_detected,metric_reliability_warning,traffic_light,traffic_light_score,is_research_grade
https://github.com/example/repo,fast,365,false,182,strong,high,false,false,false,false,green,3,true
```

Interpretation:

- this row is research-grade for screening and can be prioritized in charts and comparative analyses
- rows with `orange` should be treated as screening-only and validated before strong claims
- rows with `red` should be excluded from evidence-oriented analyses until reprocessed


---

## AI Influence Calibration Outputs

The AI Influence Score now includes additional calibration and interpretability outputs intended to reduce false positives in young and legacy repositories.

Key fields:

- `ai_influence_score`
- `ai_influence_confidence`
- `ai_influence_rationale`
- `ai_temporal_adoption_prior`
- `ai_temporal_anomaly_weight`
- `ai_dominant_activity_period`

Intermediate heuristic outputs:

- `ai_h1_textual_markers`
- `ai_h2_explicit_attribution`
- `ai_h3_temporal_prior`
- `ai_h4_burstiness`
- `ai_h5_style_shift`
- `ai_h6_large_low_discussion`
- `ai_h7_output_asymmetry`
- `ai_h8_tooling_footprint`
- `ai_h9_generated_text_pattern`

Interpretation notes:

- Very young repositories have their burstiness signal downscaled to avoid startup-phase false positives.
- Repositories dominated by pre-2022 activity are constrained by a historical feasibility rule so they are not labeled as AI-driven without strong non-temporal evidence.
- Large, long-lived repositories receive legacy variance protection to avoid confusing structural evolution with AI influence.
- Confidence reflects evidence coverage and repository size; small or sparse repositories should not produce highly confident AI judgments.


---

### Developer Turnover

Measures the proportion of contributors who have become inactive.

Definition:
Proportion of unique contributors who have not committed in the last 365 days.

Calculation:
inactive_contributors / total_unique_contributors

Where inactive_contributors are those whose last commit is more than 365 days ago.

Purpose:
Quantify contributor churn or loss of engagement.

Interpretation:
Higher values may indicate declining community or project stagnation.


---

### Gini Coefficient

Measures inequality in commit distribution among contributors.

Definition:
Gini coefficient calculated on the share of commits per contributor.

Purpose:
Quantify how unevenly commits are distributed (complements Bus Factor).

Interpretation:
Values closer to 1 indicate high inequality (few contributors dominate), closer to 0 indicate equality.


---

## AI-aware and Hybrid SDLC Metrics

These metrics are additive and are designed for repositories analyzed under `auto`, `hybrid`, or `ai` SDLC contexts.

### AI Influence Score

Repository-level estimate of how strongly the development process appears to be AI-assisted.

Definition:
Weighted combination of four normalized repository-level sub-scores:

- commit_pattern_score
- temporal_anomaly_score
- style_uniformity_score
- metadata_signal_score

Default weights:

- commit_pattern_score: 0.30
- temporal_anomaly_score: 0.20
- style_uniformity_score: 0.30
- metadata_signal_score: 0.20

If one or more sub-scores are unavailable, the remaining weights are renormalized proportionally.

Temporal prior:

- dominant activity before 2022: +0.00
- dominant activity in 2022-2023: +0.05
- dominant activity in 2024 onward: +0.10

Important:

- The score is repository-level, not per-commit.
- Date is only a weak contextual prior.
- Date alone must never classify a repository as hybrid or AI-driven.

Output fields:

- ai_influence_score
- ai_weighted_base_score
- ai_temporal_adoption_prior
- ai_dominant_activity_period
- ai_commit_pattern_score
- ai_temporal_anomaly_score
- ai_style_uniformity_score
- ai_metadata_signal_score

---

### AI Dependency Ratio (AIDR)

Definition:
In v1, this returns AI Influence Score directly.

Purpose:
Expose the current estimated dependency on AI-assisted development in a simple normalized form.

---

### Cognitive Bus Factor (CBF)

Definition:
Human-maintainability proxy derived by degrading the existing bus factor proportionally to AI Influence Score.

Purpose:
Estimate how many human contributors could plausibly maintain the system without AI assistance.

Interpretation:
Lower values may indicate stronger dependence on AI-assisted productivity for continuity.

---

### AI Monoculture Risk (AMR)

Definition:
Risk proxy that increases when style uniformity is high and contributor diversity is low.

Purpose:
Highlight repositories that may be converging toward homogeneous AI-mediated change patterns.

---

### AI Contribution Homogeneity (AICH)

Definition:
Structural homogeneity proxy derived from repeated file patterns, extension concentration, and path-depth uniformity.

Purpose:
Capture unusually consistent repository structure that may be associated with repeated AI-assisted workflows.

---

### Agentic Complexity Index (ACI)

Definition:
Automation-oriented signal derived from bot activity, automation metadata, scripts, pipelines, and detectable agent-related references.

Purpose:
Estimate how much of the repository workflow appears to rely on automation or agentic tooling.

---

### Effective SDLC Mode

Definition:
Resolved SDLC interpretation for the repository.

Modes:

- human
- hybrid
- ai

Resolution rule when the selected mode is `auto`:

- AI Influence Score < 0.30 → human
- AI Influence Score >= 0.30 and < 0.60 → hybrid
- AI Influence Score >= 0.60 → ai

## Experimental Metrics

### Security Incident Distance

Measures time between ecosystem instability signals and publicly disclosed vulnerabilities (CVE / OSV).

Example analysis windows:

- 30 days before disclosure
- 90 days before disclosure
- 180 days before disclosure

Goal:

Explore whether observable ecosystem instability signals appear before vulnerability disclosure.

Important:

This experiment does **not attempt to predict vulnerabilities**, but to investigate possible correlations.