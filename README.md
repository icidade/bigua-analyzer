# bigua-analyzer

![alt text](docs/bigua-preto.png)
> Observe the surface. Dive for the signal.

A research tool that analyzes public GitHub repositories to extract engineering and security-relevant development metrics.


[![Release](https://img.shields.io/github/v/release/icidade/bigua-analyzer)](https://github.com/icidade/bigua-analyzer/releases)
[![License](https://img.shields.io/github/license/icidade/bigua-analyzer)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()
[![Support on Patreon](https://img.shields.io/badge/Support-Patreon-ff424d?logo=patreon)](https://patreon.com/bigua_analyzer)

## Why the name?

“Biguá” is the Portuguese name for a **cormorant**, a diving bird commonly found along Brazilian coasts and rivers.

Cormorants are known for carefully observing their surroundings and diving beneath the surface to find what is hidden. In a similar way, **bigua-analyzer** inspects public repositories and dives into their history and structure to uncover patterns in how software is built.

The name reflects this idea: observing the ecosystem and extracting insights that are not immediately visible on the surface.

## What metrics does it analyze?

'bigua-analyzer' inspects public GitHub repositories and extracts a set of engineering and development signals that help reveal real-world software development patterns.

The analyzer focuses exclusively on publicly available repository metadata and commit history.

For the full metric catalogue and the traffic-light signal quality layer (`green/yellow/orange/red`), see [bigua_project_docs/metrics.md](bigua_project_docs/metrics.md#signal-quality-interpretation-layer-traffic-light).

### Repository activity

- Total number of commits
- Commit frequency over time
- Commit burst patterns
- Time between commits
- Repository age

### Contributor dynamics

- Total number of contributors
- Contribution distribution (top contributors vs long tail)
- Bus factor estimation
- New contributor arrival rate
- Maintainer activity patterns

### Project structure

- Repository size
- File count
- Directory depth
- Language distribution
- Presence of dependency declaration files (package.json, requirements.txt, pom.xml, etc.)

### Development behavior

- Pull request frequency
- Merge latency
- Commit message patterns
- Code churn over time
- Branching activity

### Security-related signals

- Presence of security-related files (SECURITY.md, CODEOWNERS)
- Dependency update patterns
- Signals of automated tooling (CI/CD, linters, security scanners)
- Indicators associated with security maturity

These metrics can be aggregated across repositories to study large-scale patterns in open-source software development and engineering practices.

## Usage

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/icidade/bigua-analyzer.git
cd bigua-analyzer
pip install -e .
```

bigua-analyzer uses **subcommands**:

| Subcommand | Purpose |
|---|---|
| `analyze` | Clone repositories and extract metrics to CSV/JSONL across human, hybrid, or AI-aware SDLC modes |
| `analyze-report` | Generate an AI-assisted Markdown + HTML report from a metrics CSV |

---

### `analyze` — Extract metrics

#### Analyze a single repository

```bash
bigua-analyzer analyze https://github.com/microsoft/vscode
```

This will analyze the default branch (usually `main` or `master`) and output results to `out/results.csv` and `out/results.jsonl`.

#### Analyze multiple repositories from a dataset

Create a CSV file `repos.csv` with repository URLs:

```csv
url
https://github.com/microsoft/vscode
https://github.com/facebook/react
https://github.com/golang/go
```

Then run:

```bash
bigua-analyzer analyze --dataset repos.csv --out analysis-results
```

#### Advanced options

- Specify a branch/tag/SHA: `--ref main`
- Limit number of repos: `--max-repos 10`
- Parallel processing: `--max-workers 8` (default 4)
- Analysis depth: `--mode full|fast` (default `full`)
- Scope history by date: `--since YYYY-MM-DD`
- Scope history by relative window: `--time-window 365`
- Limit analyzed commits inside the selected scope: `--sample-size 240`
- Disable persistent scope cache: `--no-analysis-cache`
- SDLC analysis mode: `--sdlc-mode auto|human|hybrid|ai` (default `auto`)
- Output format: `--format csv` or `--format jsonl` or `--format both` (default)
- Custom cache directory: `--cache-dir /path/to/cache`

#### Fast mode

`--mode fast` keeps the default output schema but scopes the expensive history-based calculations to a recent window and optional sampled commit subset.

- Default fast-mode window: last 365 days
- Default fast-mode sample size: 240 commits
- Sampling strategy: time-bucketed commit sampling to preserve chronological coverage
- Persistent cache: scoped commit listings and AI scan inputs are cached under the analysis cache directory inside `--cache-dir`

Use `full` when you need maximum fidelity over the entire repository history. Use `fast` when you need a materially quicker approximation on very large repositories.

#### SDLC modes

`bigua-analyzer analyze` supports four SDLC modes:

- `auto`: computes a repository-level AI Influence Score and derives the effective mode automatically
- `human`: keeps traditional repository metrics as the primary analysis lens
- `hybrid`: combines traditional metrics with AI-aware metrics
- `ai`: prioritizes AI-aware metrics while preserving existing output fields for compatibility

When `--sdlc-mode auto` is used, the effective mode is resolved from the AI Influence Score:

- `< 0.30` → `human`
- `>= 0.30` and `< 0.60` → `hybrid`
- `>= 0.60` → `ai`

The AI Influence Score is repository-level and is based on normalized heuristics for commit patterns, temporal anomalies, style uniformity, and metadata signals. Repository age is used only as a weak contextual prior and is never sufficient on its own to classify a project as `hybrid` or `ai`.

#### Examples

1. **Quick analysis of a popular repo:**
   ```bash
   bigua-analyzer analyze https://github.com/elastic/elasticsearch --ref v8.11.0
   ```

2. **Batch analysis with parallel processing:**
   ```bash
   bigua-analyzer analyze --dataset all_repos.csv --max-workers 8 --out batch-results --format both
   ```

3. **Testing with small dataset:**
   ```bash
   bigua-analyzer analyze --dataset repos.csv --max-repos 5 --max-workers 2 --out test-output
   ```

4. **Hybrid SDLC analysis:**
    ```bash
    bigua-analyzer analyze https://github.com/org/repo --sdlc-mode hybrid --out hybrid-results
    ```

5. **Auto-detect effective SDLC mode:**
    ```bash
    bigua-analyzer analyze https://github.com/org/repo --sdlc-mode auto --out auto-results
    ```

6. **Fast analysis for a very large repository:**
    ```bash
    bigua-analyzer analyze https://github.com/hashicorp/terraform --mode fast --out terraform-fast
    ```

7. **Fast dataset run with an explicit time scope and sample cap:**
    ```bash
    bigua-analyzer analyze --dataset all_repos.csv --mode fast --time-window 180 --sample-size 120 --max-workers 2 --out fast-results
    ```

8. **Full analysis constrained to recent history only:**
    ```bash
    bigua-analyzer analyze https://github.com/org/repo --mode full --since 2024-01-01 --out scoped-full-results
    ```

---

### `analyze-report` — Generate an AI report

Takes a metrics CSV produced by `analyze` and sends it to the selected LLM provider to generate a professional Markdown analysis report, optionally rendered as HTML.

Supported providers include `openai-compatible`, `openai`, `xai`, `gemini`, and local models via `ollama`.

> **Privacy warning:** Repository metadata and derived metrics may be sent to an external LLM API when using `analyze-report`. If you are working with private or sensitive repositories, verify your organization policy before running this command.

`analyze-report` asks for interactive confirmation before sending data to the configured LLM backend.
Use `--yes` to bypass this prompt in CI or scripted runs.

#### Pipeline

```
metrics CSV
    ↓
prompt builder  (metrics + derived signals)
    ↓
LLM  (provider-selected: cloud or local)
    ↓
analysis_report.md
    ↓
analysis_report.html
```

Derived signals are computed automatically before the prompt is sent:

| Signal | Logic |
|---|---|
| `contribution_concentration` | `high` if `gini_coefficient > 0.7`, else `moderate` |
| `bus_factor_risk` | `high` if `bus_factor < 2`, else `moderate` |
| `contributor_stability` | `unstable` if `developer_turnover > 0.5`, else `stable` |
| `change_velocity` | `high` if `code_churn > 1000`, else `normal` |

If the input CSV contains SDLC context fields such as `sdlc_mode`, `effective_sdlc_mode`, and `ai_influence_score`, `analyze-report` includes that context in the LLM prompt and asks the model to interpret the repository according to human, hybrid, or AI-assisted development conditions.

#### Quick start

```bash
# 1. Set your API key
export LLM_API_KEY=sk-...

# 2. Run the analyzer
bigua-analyzer analyze https://github.com/org/repo --out out/results

# 3. Generate the AI report
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --out-md analysis_report.md \
    --out-html analysis_report.html
```

Outputs `analysis_report.md` and `analysis_report.html`.

If `--repo-url` is omitted and the CSV contains multiple rows, `analyze-report` runs in batch mode and generates one report per repository under `analysis_reports/` by default.

#### Options

| Flag | Default | Description |
|---|---|---|
| `--csv` | _(required)_ | Path to the metrics CSV |
| `--repo-url` | auto | Filter to a specific URL; omit it to generate one report per CSV row |
| `--out-dir` | `analysis_reports` | Output directory for batch mode |
| `--out-md` | `analysis_report.md` | Markdown output path |
| `--out-html` | `analysis_report.html` | HTML output path (pass `""` to skip) |
| `--llm` | `openai-compatible` | LLM adapter: `openai-compatible`, `openai`, `xai`, `gemini`, `ollama` (`--provider` is an alias) |
| `--model` | provider-specific | LLM model name |
| `--base-url` | provider-specific | API base URL override |
| `--api-key` | provider-specific | API key override |
| `--temperature` | `0.2` | Sampling temperature |
| `--top-p` | `0.9` | Nucleus sampling probability mass |
| `--max-tokens` | `4096` | Max tokens in LLM response |
| `--suppress-external-llm-warning` | `false` | Suppress runtime privacy warning |
| `--yes` | `false` | Bypass interactive confirmation prompt |

The LLM call uses a **system/user split** for better output consistency:

- **System role:** persona, rules, and output constraints (static)
- **User role:** repository metadata, metrics, derived signals, and format instructions (dynamic)

Defaults are tuned for factual, analytical output: `temperature=0.2`, `top_p=0.9`.

Provider-specific environment variables are respected automatically:

- Generic (all providers): `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- `openai` / `openai-compatible`: `OPENAI_BASE_URL`, `OPENAI_MODEL` (legacy `OPENAI_API_KEY` also supported)
- `xai`: `XAI_API_KEY`, `XAI_BASE_URL`, `XAI_MODEL`
- `gemini`: `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL`
- `ollama`: `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (no API key required by default)

#### Using a self-hosted or alternative LLM

```bash
# Ollama native API
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --llm ollama \
    --base-url http://localhost:11434 \
    --model llama3.1 \
    --yes

# OpenAI-compatible endpoint
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --llm openai-compatible \
    --base-url http://localhost:11434/v1 \
    --model llama3 \
    --api-key dummy

# Gemini native API
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --llm gemini \
    --model gemini-2.0-flash

# xAI (Grok via OpenAI-compatible API)
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --llm xai \
    --model grok-2-latest

# Non-interactive mode (CI/scripts)
bigua-analyzer analyze-report \
    --csv out/results.csv \
    --yes
```

#### Batch report generation

Generate one Markdown and HTML report per repository from a multi-row CSV:

```bash
bigua-analyzer analyze-report \
    --csv out/results-parallel.csv \
    --out-dir out/analysis_reports \
    --yes
```

This writes files such as `owner__repo_analysis_report.md` and `owner__repo_analysis_report.html` under the chosen output directory.

#### HTML rendering

HTML output is always available. By default, bigua-analyzer uses a built-in Markdown converter that covers the subset typically produced by LLMs: headings, bold, italic, inline code, fenced code blocks, lists, and links.

For higher-fidelity rendering — including tables and extended Markdown syntax — install the optional [`markdown`](https://pypi.org/project/Markdown/) package:

```bash
# If installed from source
pip install -e ".[ai]"

# If installed from PyPI
pip install "bigua-analyzer[ai]"
```

### Output

Results are saved as CSV and/or JSONL files. Each row/object contains:
- Repository metadata (URL, ref, repo_id)
- Success status and error messages (if any)
- All calculated metrics

When SDLC-aware analysis is enabled, outputs also include additive fields such as:

- `sdlc_mode`
- `effective_sdlc_mode`
- `analysis_mode`
- `analysis_since`
- `analysis_time_window_days`
- `analysis_sample_size`
- `analysis_sampling_strategy`
- `analysis_cache_enabled`
- `analysis_cache_hit`
- `commit_scope_total_commits`
- `commit_scope_analyzed_commits`
- `commit_scope_is_approximate`
- `ai_influence_score`
- `ai_weighted_base_score`
- `ai_temporal_adoption_prior`
- `ai_temporal_anomaly_weight`
- `ai_commit_pattern_score`
- `ai_temporal_anomaly_score_raw`
- `ai_temporal_anomaly_score`
- `ai_style_uniformity_score`
- `ai_metadata_signal_score`
- `ai_influence_rationale`

The `commit_scope_*` and `analysis_*` fields make scoped runs explicit, so downstream analysis can distinguish full-history metrics from fast approximations.

In JSONL output, AI-aware metrics are preserved under `metrics.ai_metrics`.
In CSV output, nested AI-aware metrics are flattened into columns such as `ai_metrics_aidr`, `ai_metrics_cbf`, `ai_metrics_amr`, `ai_metrics_aich`, and `ai_metrics_aci`.

> **Note:** For the `analyze` command, if `--out` is provided as a bare filename (no directory), output is written under `out/` by default (e.g., `--out results` → `out/results.csv`). If you specify a path (e.g., `--out data/results`), that path is used as given.

See `bigua_project_docs/metrics.md` for detailed metric definitions.

### Dataset Format

Datasets can be CSV or JSONL:

**CSV:**
```csv
url,ref,repo_id
https://github.com/org/repo,main,my-repo
```

**JSONL:**
```json
{"url": "https://github.com/org/repo", "ref": "main", "repo_id": "my-repo"}
```

### Performance Notes

- First run clones repositories (cached for future runs).
- Use `--max-workers` for parallel processing on multi-core systems.
- Large repos may take time; start with small datasets for testing.

## Project Policies

- See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution workflow and pull request guidance.
- See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations.
- See [SECURITY.md](SECURITY.md) for vulnerability reporting guidance.
- See [CHANGELOG.md](CHANGELOG.md) for notable release history.

---

## Support

If this research is useful for your work or organization,
consider supporting its development:

👉 https://patreon.com/bigua_analyzer
