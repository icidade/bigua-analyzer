# Contributing to bigua-analyzer

Thank you for contributing to bigua-analyzer.

This project is evolving as a research-oriented open source tool for analyzing public repositories and extracting socio-technical metrics. Contributions are welcome in code, documentation, datasets, bug reports, and research-oriented improvements.

## Ways to Contribute

- Report bugs and unexpected metric behavior.
- Improve documentation and examples.
- Add tests for metrics and CLI behavior.
- Improve performance and repository handling.
- Propose new metrics with a clear definition and rationale.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Keep changes focused and small when possible.
- Prefer changes that preserve metric definitions unless a definition change is explicitly intended and documented.
- If you change a metric, update the related documentation in `bigua_project_docs/metrics.md`.

## Development Setup

```bash
git clone https://github.com/icidade/bigua-analyzer.git
cd bigua-analyzer
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Suggested Workflow

1. Create a feature branch from `main`.
2. Make the smallest change that solves the problem.
3. Run the relevant checks locally.
4. Update documentation when behavior changes.
5. Open a pull request with a clear description.

## Pull Request Guidelines

- Explain what changed and why.
- Mention any tradeoffs or limitations.
- Include example output when CLI behavior changes.
- Note whether results or metric values may change compared to previous runs.
- Avoid mixing unrelated refactors into the same pull request.

## Metric Changes

Changes to metric logic should include:

- the metric definition,
- the reason for the change,
- expected impact on output values,
- any performance implications,
- any documentation updates.

If a performance optimization changes no semantics, state that explicitly in the pull request.

## Reporting Bugs

When opening a bug report, include:

- command used,
- dataset or repository URL,
- expected behavior,
- actual behavior,
- traceback or error message,
- environment details if relevant.

## Scope

This repository is currently focused on public repository analysis, reproducible metric extraction, and research support tooling. Contributions outside that scope may be declined or deferred.
