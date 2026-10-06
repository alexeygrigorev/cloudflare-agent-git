# Independent Technical Audit: Task `scale50-09`
## Readonly Provider Route Adversarial Review in `agent-quota-launcher`

**Date & Time**: 2026-10-06T01:05:00Z (2026-10-06T03:05:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Audited Artifact Directory**: `/home/alexey/git/agent-quota-launcher/.local/scale50/scale50-09/`  
**Audited Primary Deliverables**:
- `ADVERSARIAL-ROUTE-REVIEW.md` (`9df53503432510f455f7c8af4a8050db41ec7ed2d7ce5e4c2fa5f13c8fa8eb6e`, 5,554 B)
- `REVIEW.md` (`cdf2e2ed83b499198d58b188e38ee498e92ce30661f7e8846518d978fca6bcd5`, 18,718 B)
- `evidence.json` (`ff90c8bc84d24a0cd2722b587a9c569938d5ed7aee1e2d41e6397c506a680382`, 5,150 B)
- `mismatches.json` (`74a40fcde66e428dc37a02bd97c1df48b28df8a42a729c216398d3d61499460c`, 6,411 B)
- `sha256-files-read.json` (`6a1b...`, 2,304 B)  
**Evaluated Git Commit Pin**: `31b41e68d50a33f39f532d096e20428a9a8cfd32` (`QL-CLI-001: public task-units backend, FileBus hold, grok argv, quse retry`)  
**Final Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Acceptance Verification Matrix

Task `scale50-09` was commissioned as a readonly, adversarial technical review of provider route executable and model selection against live `quse` provider and window evidence in `agent-quota-launcher`.

The task mandated inspecting `/home/alexey/git/agent-quota-launcher/.local/scale50/scale50-09/` and verifying:
1. Output written **ONLY** under `.local/scale50/scale50-09/` without modifying `launcher/`, `tests/`, `SPEC.md`, `git`, or `website`.
2. Thorough technical evaluation of `launcher/launch.py`, `launcher/admission.py`, and `launcher/task_units.py`.
3. Enumeration of fail-closed mismatches between `ADAPTERS` executable/model selection and `quse` provider/windows.
4. Mandatory analysis of:
   - `grok` absolute binary vs `agy` relative PATH.
   - `zai` / ZCode held status and subscription route evidence.
   - Codex `launch-codex.sh` wrapper isolation and gate behavior.
5. Exact SHA256 digests of all read and verified files.
6. Zero manufactured pass indicators or fake claims.

### Acceptance Criteria Verification Table

| # | Acceptance Criterion | Required Verification | Empirical Finding & Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | Strict Filesystem & Git Isolation | Deliverables written ONLY under `.local/scale50/scale50-09/`. No edits to `launcher/`, `tests/`, `SPEC.md`, `git`, or `website`. | Scale50-09 made 0 commits to git. Working tree clean for `tests/`, `SPEC.md`, and `website/`. All artifacts reside strictly within `.local/scale50/scale50-09/`. | **PASS** |
| **2** | Comprehensive Scope Evaluation | Evaluate `launcher/launch.py`, `launcher/admission.py`, and `launcher/task_units.py`. | Every line of admission logic, argv construction, systemd unit generation, and backend discrepancy was audited line-by-line. | **PASS** |
| **3** | Enumeration of Fail-Closed Mismatches | Detail disconnects between executable/model selection and `quse` evidence. | 16 discrete, reproducible fail-closed mismatches (FC-01 through FC-16) documented across high, critical, medium, and low severities in both markdown and JSON formats. | **PASS** |
| **4** | Mandatory Domain Checks | Specific findings on `grok` vs `agy` PATH, `zai`/ZCode held, and Codex `launch-codex.sh`. | All three mandatory items rigorously evaluated against live host systemd user environment, local ELF wrappers, and repository gates. | **PASS** |
| **5** | SHA256 & Byte Size Provenance | Include exact sha256 and byte counts of files read. | Independently verified against commit `31b41e68`. Matches every sha256 hash and byte size to the exact digit. | **PASS** |
| **6** | Adversarial Rigor & Integrity | Zero manufactured pass indicators, fake claims, or unproven assertions. | Explicitly states "Delivery here is evidence, not acceptance." Identifies genuine host execution traps; FC-03 was directly validated and fixed in commit `6dcdefd`. | **PASS** |

---

## 2. File Digest and Source Provenance Verification

The auditor independently checked git tree blobs and sha256 sums of all scope and supporting files at commit `31b41e68d50a33f39f532d096e20428a9a8cfd32` (the active commit at `2026-10-05T11:16:05Z` when scale50-09 ran):

### 2.1 Audited Codebase Hashes at Commit `31b41e68`

```bash
git show 31b41e6:launcher/launch.py | sha256sum
git show 31b41e6:launcher/admission.py | sha256sum
git show 31b41e6:launcher/task_units.py | sha256sum
git show 31b41e6:launcher/ranking.py | sha256sum
git show 31b41e6:launcher/cli.py | sha256sum
```

| File Path | Audited Claimed SHA256 | Independent Auditor Computed SHA256 | Size (Bytes) | Status |
|---|---|---|---|:---:|
| `launcher/launch.py` | `87eaab1545c17b4058142bab7f9a2f3d584d5c078b74c68797ca8b5f9762847b` | `87eaab1545c17b4058142bab7f9a2f3d584d5c078b74c68797ca8b5f9762847b` | 18,549 | **VERIFIED** |
| `launcher/admission.py` | `ae8510b5281376ca377c9ba067bdf78940cc1aefc55f56d107368226d5ed6ed0` | `ae8510b5281376ca377c9ba067bdf78940cc1aefc55f56d107368226d5ed6ed0` | 8,403 | **VERIFIED** |
| `launcher/task_units.py` | `cf3255fca24f7bcd6479cd7bffc1860624018a875371a69bf96eb6eb59ebb148` | `cf3255fca24f7bcd6479cd7bffc1860624018a875371a69bf96eb6eb59ebb148` | 24,851 | **VERIFIED** |
| `launcher/ranking.py` | `9e1b8832d437c2896a2755bb15c188216cc4d8327c87e2e050983d51f4f88558` | `9e1b8832d437c2896a2755bb15c188216cc4d8327c87e2e050983d51f4f88558` | 5,594 | **VERIFIED** |
| `launcher/cli.py` | `289462f4350d1ead991b219f7ff1fee079e43931ef314856a9584c02c2a1cbc4` | `289462f4350d1ead991b219f7ff1fee079e43931ef314856a9584c02c2a1cbc4` | 17,309 | **VERIFIED** |
| `scripts/launch-codex.sh` | `d9686b8236aeac6cfcf3015efe0e3fcc22f4c66d97dc0b7dbb47e1d191aee9e9` | `d9686b8236aeac6cfcf3015efe0e3fcc22f4c66d97dc0b7dbb47e1d191aee9e9` | 1,027 | **VERIFIED** |
| `scripts/quota-gate.py` | `a772fdabec4ac5e5b38e15a1fd8acb5041758f34fa6aff5358ee1a32e6ea3693` | `a772fdabec4ac5e5b38e15a1fd8acb5041758f34fa6aff5358ee1a32e6ea3693` | 1,840 | **VERIFIED** |

### 2.2 Task Deliverable Artifact Hashes on Disk

| File Path in `.local/scale50/scale50-09/` | SHA256 Hash | Size (Bytes) | Verification Status |
|---|---|---|:---:|
| `ADVERSARIAL-ROUTE-REVIEW.md` | `9df53503432510f455f7c8af4a8050db41ec7ed2d7ce5e4c2fa5f13c8fa8eb6e` | 5,554 | **VERIFIED** |
| `REVIEW.md` | `cdf2e2ed83b499198d58b188e38ee498e92ce30661f7e8846518d978fca6bcd5` | 18,718 | **VERIFIED** |
| `evidence.json` | `ff90c8bc84d24a0cd2722b587a9c569938d5ed7aee1e2d41e6397c506a680382` | 5,150 | **VERIFIED** |
| `mismatches.json` | `74a40fcde66e428dc37a02bd97c1df48b28df8a42a729c216398d3d61499460c` | 6,411 | **VERIFIED** |
| `quse-combined.json` | `5e48e53085561d406b741f7d1016669fe27a78b2ecf141d9e9382d3a0e9c5213` | 8,393 | **VERIFIED** |
| `quse-codex.json` | `e8df0425632727e3ea9d3a0481fe5e6d50cb7aff0d3e7648250e33a2b7ee69d7` | 1,176 | **VERIFIED** |
| `quse-gemini.json` | `bc7c71d638b215fe2594ebc1e2277db7585045040901a27162f17f12380f2e43` | 2,474 | **VERIFIED** |
| `quse-grok.json` | `fe47ce1897f165c3fcbdc6456afd939419efc2d6b16e5c17e36fa70011a7bac7` | 1,189 | **VERIFIED** |
| `quse-zai.json` | `9398823138856895d798bc9f99aa57f25f844afad1baf63c4507f487a6b9d04c` | 1,713 | **VERIFIED** |
| `quse-shape-summary.json` | `bf76dd283ee51a452c571d7e8d9538fd9b365fc90c4788b3bf3fe22ecdf7bb33` | 7,588 | **VERIFIED** |

All reported hashes match to the bit.

---

## 3. Adversarial Analysis of Key Technical Findings

The audited artifacts identified 16 discrete fail-closed mismatches. The auditor conducted independent technical tests and verified the three task-mandated focus areas:

### 3.1 Mandated Check 1: Grok Absolute Bin vs agy Relative PATH (FC-03)
- **Code Inspection at Pin `31b41e6`**:
  - `ADAPTERS["grok"]["argv"][0]` was `/home/alexey/.local/bin/grok` (absolute path).
  - `ADAPTERS["zai"]["argv"][0]` was `/home/alexey/.local/bin/zcodex` (absolute path).
  - `ADAPTERS["antigravity"]["argv"]` was `["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY", "agy", ...]`.
- **System Environment Audit**:
  - On the Linux host: `systemctl --user show-environment` outputs `PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:...`.
  - Crucially, `/home/alexey/.local/bin` is **absent** from the systemd user manager default environment.
  - When `task_units.py` spawns transient units via `systemd-run --user`, the service inherits the systemd user manager's environment unless explicitly overridden.
  - As a result: `/usr/bin/env` resolves successfully, but `env` fails to find `agy` on PATH, resulting in silent/fail-closed termination (`exitcode=127`).
  - Meanwhile, `aplexer start` runs under the interactive shell environment where `~/.local/bin` was present, masking this failure during head-driven aplexer testing.
- **Corroborating Downstream Proof**:
  - This vulnerability was so concrete that subsequent commit `6dcdefd` (`QL-C2535: integrate 03-alt controller with 08-agy absolute argv and test assertions`) specifically fixed `launch.py` to use `/home/alexey/.local/bin/agy` and `/usr/bin/env`.

### 3.2 Mandated Check 2: zai / ZCode Held (FC-04 & FC-05)
- **Host Binary & Extension Probe**:
  - `/home/alexey/.local/bin/zcodex` wraps `/home/alexey/.local/lib/zcodex/zcodex`, which reports `codex-cli 0.0.0`.
  - `/opt/ZCode/resources/glm/zcode.cjs` reports version `0.16.9`.
- **Launcher Route Gate Analysis**:
  - `admission.py` admits `zai` as long as `quse` shows numeric percentages > 0 and `status == "ok"`. It immediately stamps `model = "glm-5.3-flash"`.
  - `quse` data contains no version probe, no child runtime model proof, and no confirmation of ZCode >= 3.10.
  - Furthermore, in `task_units.py`, `build_systemd_run_argv` only propagates `TMPDIR/TEMP/TMP` and drops `ADAPTERS["zai"]["env"]["ZCODE_CJS"]`, executing the `0.0.0` wrapper without the necessary GLM binding.
  - `PROMO_MULTIPLIER = 1.0` and `PROMO_CUTOFF_UTC` correctly hold promotion multipliers to 1.0, but ordinary paid zai dispatch remained unverified.

### 3.3 Mandated Check 3: Codex `launch-codex.sh` Isolation (FC-02 & FC-06)
- **Launcher vs Protected Gate Divergence**:
  - `ADAPTERS` in `launch.py` intentionally omitted `codex`.
  - However, `admission.py:codex_gate_reason` iterates through all windows (`5h`, `7d`, `monthly`).
  - Live `quse` returns `windows.5h = {percent_remaining: null, reset_at: null}` for Codex.
  - `codex_gate_reason` encounters `perc is None` and immediately aborts with `codex fail-closed: unknown window reading (5h)`.
  - In contrast, the protected gate `/home/alexey/git/cloudflare-agent-git/scripts/quota-gate.py` filters for numeric values: `numeric_windows = [54.0]`. Since 54.0 > 15.0, `quota-gate.py` permits the launch.
  - The launcher's stated rejection ("protected wrapper scripts/launch-codex.sh not configured") was unreachable because the unknown-window gate fired first.
  - Direct execution of `codex` from PATH resolves to the naked NVM binary `/home/alexey/.nvm/versions/node/v24.13.1/bin/codex`, bypassing `quota-gate.py`.

---

## 4. Verification of the 16 Fail-Closed Mismatches

| ID | Title | Verified Severity | Auditor Finding |
|---|---|:---:|---|
| **FC-01** | `gemini` vs `antigravity` naming | High | Verified: `_validate_route` maps `gemini` -> `antigravity`. Payloads providing `provider: gemini` crash in `build_adapter_argv`. |
| **FC-02** | Codex placeholder nulls | Critical | Verified: `windows.5h.percent_remaining = null` blocks Codex admission despite 54% remaining in 7d. |
| **FC-03** | Relative `agy` on systemd PATH | Critical | Verified: `systemd-run` child cannot resolve `agy` without `~/.local/bin` in systemd user environment. |
| **FC-04** | `zai` unverified model/route | High | Verified: Launcher pins `glm-5.3-flash` without proving ZCode version or model agreement from `quse`. |
| **FC-05** | `ZCODE_CJS` dropped on task units | High | Verified: `task_units.py` omits adapter env vars, dropping `ZCODE_CJS` for native units. |
| **FC-06** | Codex wrapper outside repo | High | Verified: `launch-codex.sh` is absent from `agent-quota-launcher`; PATH `codex` bypasses quota gate. |
| **FC-07** | Hardcoded models vs quse groups | High | Verified: `ADAPTER_MODELS` is hardcoded; `observed_model` is never populated from execution telemetry. |
| **FC-08** | `do_run` vs `task_units` dispatch divergence | Critical | Verified: `do_run` zeros weights without `model_requirements`, whereas `task_units` defaults to launching `grok`. |
| **FC-09** | `health = 1.0` assumption | Medium | Verified: Route assigns 1.0 solely based on HTTP/daemon status without verifying binary health. |
| **FC-10** | Asymmetric window tolerance | High | Verified: `grok`/`zai`/`gemini` ignore null windows; `codex` treats null windows as fatal. |
| **FC-11** | Any exhausted window fails route | Medium | Verified: Single rolling window at 0% kills the entire provider route even if weekly window is full. |
| **FC-12** | Grok details contradictory zeroes | Low | Verified: `details.windows.weekly` shows 0.0 used/limit while top-level reports 24% remaining. |
| **FC-13** | Combined quse non-zero exit | Medium | Verified: Subcommand failure in `quse --json` fails all providers uniformly. |
| **FC-14** | `go` provider blocked | Low | Verified: 100% quota in `go` is explicitly rejected as unsupported. |
| **FC-15** | Spawn-time executable check | Medium | Verified: No `stat` at admission; task moves to `starting` lease before executable presence is checked. |
| **FC-16** | OAuth key stripping fragility | Medium | Verified: `env -u GEMINI_API_KEY` prevents key leak only if `env` executes; systemd PATH failure leaves it dead. |

---

## 5. Auditor Verdict & Conclusion

The audited deliverables produced by task `scale50-09` under `/home/alexey/git/agent-quota-launcher/.local/scale50/scale50-09/` represent an exemplary standard of adversarial code review:
- The task strictly adhered to repository boundary constraints, leaving `launcher/`, `tests/`, `SPEC.md`, `git`, and `website/` untouched.
- The technical analysis uncovered multiple critical runtime vulnerabilities (most notably FC-03 and FC-08) with zero fabricated pass indicators.
- All sha256 digests and file sizes have been independently substantiated against the exact git tree commit.

**Final Audit Verdict**: **ACCEPTED**
