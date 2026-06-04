# Security Policy

PriorStates runs entirely on your machine. It has no server or cloud component,
but it **writes to local files** — your data under `~/.priorstates/` (and
per-project `.priorstates/`) and your AI agents' config files (e.g. Claude /
Codex / Gemini settings) when you run `priorstates agents install`.

## Reporting a vulnerability

Please report security issues **privately** to **service@priorstates.com** —
not as a public GitHub issue. Include steps to reproduce and the affected version
(or commit). We'll acknowledge within a few days and keep you posted on a fix.
If GitHub's private vulnerability reporting is enabled, **Security → Report a
vulnerability** works too.

## Supported versions

v0.1 is pre-release; fixes land on `main` (best effort).
