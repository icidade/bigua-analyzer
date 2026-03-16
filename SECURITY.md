# Security Policy

## Supported Versions

Security fixes are currently applied on a best-effort basis to the latest development state of the project.

At this stage, the project does not guarantee backports to older tags or releases.

## Reporting a Vulnerability

Please do not open a public issue for security-sensitive problems.

If GitHub private vulnerability reporting is enabled for this repository, use that channel.

Otherwise, contact the maintainer privately through available GitHub contact channels and include:

- a clear description of the issue,
- affected component or file,
- reproduction steps,
- expected impact,
- any proposed mitigation if known.

## What to Expect

Best-effort process:

- acknowledgement after the report is reviewed,
- validation and impact assessment,
- a fix or mitigation plan when the issue is confirmed,
- coordinated public disclosure after a fix is available when appropriate.

## Scope Notes

This project analyzes public repositories and may process untrusted metadata from remote repositories. Security reports are especially useful for:

- command execution risks,
- unsafe handling of remote input,
- path traversal or filesystem issues,
- data leakage in outputs,
- dependency-related risks in the local analysis workflow.
