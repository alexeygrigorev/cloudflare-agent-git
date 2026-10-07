# Incidents, 2-7 October 2026 (historical)

Historical only. Not part of agent context. Do not read this file unless you are investigating project history.

This is a record of operational incidents from the first week of the project: outages, recoveries, out-of-memory kills, stuck agents, duplicate executions, lost handoffs and similar failures. It was written after the fact from the project's own notes. It does not set any rule. Where current rules came out of an incident, the rules live on `main`, not here.

Each entry gives the date, what happened, the root cause, what was changed, and the source files. Every source path refers to tag `pre-cleanup-20261007` (commit `7a0b82c`). Read a source with:

```
git show pre-cleanup-20261007:<path>
```

Facts were checked against the sources. Anything the sources do not state directly is marked **unverified**. Entries are newest first.

## Incidents
