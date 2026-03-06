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

Measures the regularity of project releases.

Method:

Average number of days between Git tags.

Purpose:

Detect projects where release discipline has slowed or become irregular.

Interpretation:

Very large gaps between releases may indicate project stagnation.


---

## Supporting Metrics

These metrics provide contextual information about the repository.

- repo_age_days
- commit_count
- contributor_count

They help normalize and interpret ecosystem signals.


---

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