# bigua-analyzer — Datasets

This document lists the public datasets used by bigua-analyzer for repository ecosystem analysis.

The project intentionally relies only on **publicly available data sources**.

Note on hybrid SDLC analysis:

- `sdlc_mode` is selected via CLI, not provided by the repository dataset schema.
- Existing CSV/JSONL input datasets remain backward-compatible.
- AI-aware fields such as `effective_sdlc_mode` and `ai_influence_score` are generated as output metadata during analysis.

---

## GitHub Repository Data

Primary source of ecosystem signals.

Collected via GitHub API.

Examples of extracted data:

- commits
- contributors
- pull requests
- issues
- releases
- repository metadata

Example API endpoints:

/repos/{owner}/{repo}
/repos/{owner}/{repo}/commits
/repos/{owner}/{repo}/contributors
/repos/{owner}/{repo}/issues
/repos/{owner}/{repo}/releases

---

## Vulnerability Data (Exploratory Analysis)

For the exploratory security experiment, vulnerability disclosure data may be collected from:

### OSV Database

https://osv.dev

Advantages:

- Links vulnerabilities to specific repositories
- Aggregates data from multiple ecosystems
- Supports GitHub repositories directly

---

### NVD (National Vulnerability Database)

https://nvd.nist.gov

Used for:

- CVE publication date
- vulnerability metadata

---

## Optional Datasets (Future Work)

### GitHub Advisory Database

https://github.com/advisories

Provides:

- security advisories
- patch references
- affected repositories

---

### Software Heritage

https://www.softwareheritage.org

Could enable historical analysis across ecosystems.

---

## Dataset Selection Criteria

Repositories used in the study should satisfy:

- Public GitHub repository
- Minimum activity threshold
- Minimum number of contributors
- Minimum project age

Example criteria:

- ≥ 1000 stars
- ≥ 50 contributors
- ≥ 3 years of history