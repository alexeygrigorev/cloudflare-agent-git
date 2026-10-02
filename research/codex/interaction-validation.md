# Same-oracle semantic interaction fixture

2026-10-02. Run `python3 research/codex/interaction-fixture.py`. Python 3 and Git only; creates/removes its own tiny temporary repository, no agents, package installs, credentials or cloud calls. Sanitized output: interaction-measurements.json.

Base already has read, single-update and bulk-update APIs. Scripted patch A caches reads and invalidates the cache through the existing update path. Scripted patch B makes bulk updates write directly to storage. They edit different files. The **identical externally supplied oracle** sets a value, reads it, bulk-updates it and checks the next read. Its SHA-256 is `1786fdbfde44dd75b123ea3b196ff4af053214ae32cb8f0d0135cfef076d8586` in every state.

| State | Same oracle exit |
|---|---:|
| Base | 0 |
| Base + A | 0 |
| Base + B | 0 |
| Clean Git merge A+B | 1: stale cached value after bulk update |

This reproduces a deliberately constructed interaction under one fixed test. It does not establish frequency, real-agent behavior, usefulness of warnings, or security of executing hostile candidates. The acceptance command sits outside candidate Git history, but this simple local Python runner is not a hostile-code sandbox.

The earlier greeting fixture used different branch suites and an approved API migration. It remains a useful stale-contract hazard illustration; it cannot be counted as a controlled same-oracle interference estimate. This new experiment addresses that methodological limitation. It is still a synthetic research fixture, not a competition demonstration or an A03 arm result.

The [STALE benchmark paper](https://arxiv.org/html/2609.25396v1) motivated the equal-suite check. Its mined reviewed-PR cohort and deliberately constructed tasks are distinct; neither this fixture nor its constructed examples estimates production prevalence. Ordinary merged-tree CI with this oracle catches the same failure. A01 must earn value through earlier actionable delivery and replayable diagnosis, beyond discovering that combined code needs tests.
