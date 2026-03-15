# bigua-analyzer


[![Release](https://img.shields.io/github/v/release/icidade/bigua-analyzer)](https://github.com/icidade/bigua-analyzer/releases)
[![License](https://img.shields.io/github/license/icidade/bigua-analyzer)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()

> Observe the surface. Dive for the signal.

A research tool that analyzes public GitHub repositories to extract engineering and security-relevant development metrics.

## Why the name?

“Biguá” is the Portuguese name for a **cormorant**, a diving bird commonly found along Brazilian coasts and rivers.

Cormorants are known for carefully observing their surroundings and diving beneath the surface to find what is hidden. In a similar way, **bigua-analyzer** inspects public repositories and dives into their history and structure to uncover patterns in how software is built.

The name reflects this idea: observing the ecosystem and extracting insights that are not immediately visible on the surface.

## What metrics does it analyze?

'bigua-analyzer' inspects public GitHub repositories and extracts a set of engineering and development signals that help reveal real-world software development patterns.

The analyzer focuses exclusively on publicly available repository metadata and commit history.

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

### Basic Usage

#### Analyze a single repository

```bash
bigua-analyzer https://github.com/microsoft/vscode
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
bigua-analyzer --dataset repos.csv --out analysis-results
```

#### Advanced options

- Specify a branch/tag/SHA: `--ref main`
- Limit number of repos: `--max-repos 10`
- Parallel processing: `--max-workers 8` (default 4)
- Output format: `--format csv` or `--format jsonl` or `--format both` (default)
- Custom cache directory: `--cache-dir /path/to/cache`

#### Examples

1. **Quick analysis of a popular repo:**
   ```bash
   bigua-analyzer https://github.com/elastic/elasticsearch --ref v8.11.0
   ```

2. **Batch analysis with parallel processing:**
   ```bash
   bigua-analyzer --dataset all_repos.csv --max-workers 8 --out batch-results --format both
   ```

3. **Testing with small dataset:**
   ```bash
   bigua-analyzer --dataset repos.csv --max-repos 5 --max-workers 2 --out test-output
   ```

### Output

Results are saved as CSV and/or JSONL files. Each row/object contains:
- Repository metadata (URL, ref, repo_id)
- Success status and error messages (if any)
- All calculated metrics

> **Note:** If `--out` is provided as a bare filename (no directory), output is written under `out/` by default (e.g., `--out results` → `out/results.csv`). If you specify a path (e.g., `--out data/results`), that path is used as given.

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
