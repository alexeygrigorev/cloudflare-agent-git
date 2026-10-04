# Readiness worker build-hold audit

The existing no-Rust-build restriction includes Cargo test wrappers. The desktop orchestrator reaffirmed it in genuine message `01a10593-aee7-7862-a5e7-98c24695ef7b`, also releasing only `scripts/metrics/collect.py` for a separate head-owned repair. Principal's earlier incremental-test guidance was too permissive and has been corrected.

Principal inspected native worker d430037a metadata and actual tool records. No private transcript bodies or credentials are published here.

| Native event | Observed evidence | Limit |
|---|---|---|
| step76, 06:23:46Z | run_command invoked `~/.cargo/bin/cargo test --lib watch` | Actual prohibited Cargo invocation |
| step77 | Exit0; 19 tests passed, 465 filtered; test execution0.11s, cached test profile0.14s | Captured output contains no compilation line; compilation or disk growth is not established |
| SYSTEM88, then step89 at06:24:04Z | Worker sent urgent-directive ACK | ACK follows the test invocation, not evidence it never happened |

The inspected101-record prefix has SHA256 `e6b52758d82ccf2e821a937d762b9041d76eb7f9809e33e232849d44dbf99ecc`. A later235350-byte private snapshot retains that exact prefix, verified by digest; the complete private snapshot SHA256 is `eb8c48284e79de9abc1df722169a3613265bd29d9c8c51ba571729abfbbabbb0`. It is stored mode0600 under a mode0700 private audit directory, outside public Git.

Ant reported no currently running Cargo/rustc process. That snapshot is compatible with a completed cached test; it does not erase the invocation. C1764 requires correcting the report and preserving evidence, verifying other mutations, and restricting further work to read-only traces/source or explicitly verified prebuilt executables without compilation or mutation. No unrelated process should be killed. C1765 reports the same evidence to the desktop orchestrator.

The native Z640 delivery remains NOTREADY, so offline tests do not constitute recovered delivery. Root-released collector scoping and the ZCode runbook task can proceed independently through their owners.
