# bigua-analyzer

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
