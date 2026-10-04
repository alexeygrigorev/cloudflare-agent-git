# REV-PUBLICATION-GUARD — Independent Security Re-Review of Publication Credential Guard

- **Reviewer Tag:** `publication-guard-re-reviewer`
- **Session ID:** `c571d108-b056-477a-a5a7-e2fb0e4429aa`
- **Parent Session:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives:** Codex Principal C1621 / C1622 / C1625 / C1630 / C1632
- **Review Date / As-of:** 2026-10-04, Europe/Berlin
- **Target Files under Review (Pinned Hashes):**
  - `research/antigravity/tooling/publication_guard.py` (blob `db69e55339b8c94884d2fcbb521a510675814e27`, mode `100755`, committed in `f9c2050`)
  - `tests/test_publication_guard.py` (blob `e3b235d0c2f60b3a49a70a6041582f09979bec0f`, mode `100644`)
- **Bounded Verdict:** **ACCEPT_REMEDIATED_SOURCE (db69e553)**
  - All three live bypasses uncovered by Codex Principal C1621 and both predicted edge-case failures have been fully remediated in source `db69e553` and verified through dedicated unit tests and independent scratch execution.
  - C1630/C1632 provenance audit successfully reconciled the initial uncommitted prompt label artifact (`0f4cdbfb`) with the actual committed blob (`db69e553`).
  - Previous overbroad claim of "complete against all evasions" is explicitly withdrawn and superseded by this bounded verification record.
  - **Operating Status:** Publication coordinator remains on **DRAFT guard**; the tool is verified as a mandatory pre-commit tripwire and automated filter, but must not be treated as a sole, infallible privacy gate.
  - Pinned test suite executes **32/32 tests cleanly in 2.300s** with zero failures and zero errors.
  - Test suite self-verification passes with exit code 0 (zero self-referential false positives).
  - All 7 repository public research deliverables pass publication guard verification with exit code 0.
  - Operational invariants strictly observed: scratch disk usage 620 KB (budget <= 512 MB, mode `0700`), zero `/tmp` growth, memory within cooperative limit (<= 1500 MB), and strictly zero raw secrets printed.

---

## 1. Context & Disclosure of Codex Principal Findings

### 1.1. C1621 / C1622 Negative Findings
In commit `2eacf83` (`research/codex/publication-guard-review-2026-10-04.md`), Codex Principal conducted an in-memory audit of the previously committed blob `05fc18e2` and test blob `c6590cd3`. The principal demonstrated that despite 26 passing unit tests and 3 killed mutants, the source retained prefix matching and overly broad bracket exemptions that permitted three live bypasses where `scan_content()` returned 0 violations:

1. **`tok_` Fixture Prefix Bypass:** `tok_alpha_12345` was matched with `.startswith()`, allowing arbitrary secret payloads appended to the documented test fixture (e.g. `tok_` + `alpha_12345` + `_arbitrary_extra_secret`) to bypass detection undetected.
2. **Local Secret Prefix Bypass:** Local secret suffix matching used loose prefix/substring checks, allowing appended payloads (e.g. `admin-secret-` + `token_12345` + `_arbitrary_extra_secret`) to bypass detection.
3. **Arbitrary Bracketed URL Password Bypass:** URL password redaction accepted arbitrary bracketed/angled strings (e.g. `[some_raw_secret]` or `<some_raw_secret>`), creating a bypass vector for raw credentials formatted inside brackets.

Furthermore, two operational fail-closed defects were predicted and confirmed:
4. **Staged Corrupted/NUL Text Files:** Staged text deliverables containing NUL bytes were silently skipped as binary blobs rather than failing closed with operational error (exit code 2).
5. **Unmatched Explicit Staged Targets:** Explicit file targets passed to `--staged <path>` that did not match any file in the git index returned exit code 0 rather than failing closed with operational error (exit code 2).

Under C1622 and C1625, the previous review's unqualified claim of being "complete against all evasions" was rejected, and publication coordinator was placed on DRAFT guard.

### 1.2. Provenance Audit & C1630 / C1632 Label Reconciliation
During initial dispatch under C1625, the target source file was referenced with a label artifact `0f4cdbfbaf58f5b8e45da6629ba2bcbc8c54530c`. A provenance audit conducted under C1630 / C1632 verified:
- `git cat-file -t 0f4cdbfb...` returned fatal error; `0f4cdbfb` was an uncommitted prompt label artifact rather than an object stored in git history.
- The actual committed file implementing all strict allowlists and staged fail-closed handling in commit `f9c2050` is blob `db69e55339b8c94884d2fcbb521a510675814e27` (mode `100755`).
- In `.local/scratch/publication-guard-re-review/`, `git hash-object research/antigravity/tooling/publication_guard.py` was executed directly, confirming that all unit tests, self-scans, and scratch negative CLI checks ran on the exact committed `db69e553` source blob.

---

## 2. Deep Function Body Inspection (Blob `db69e553`)

Inspection of the exact function bodies in `research/antigravity/tooling/publication_guard.py` (blob `db69e55339b8c94884d2fcbb521a510675814e27`):

### 2.1. Strict `tok_` Fixture Equality (`is_safe_tok`)
```python
def is_safe_tok(tok_val: str) -> bool:
    """
    Check if tok_ payload is strictly an allowed documented synthetic fixture or known marker.
    Per C1621 / C1622: Strict equality ONLY. No startswith or prefix matching.
    """
    t = tok_val.strip().strip('"\'`')
    if t == "alpha_12345":
        return True
    if t in KNOWN_REDACTION_MARKERS:
        return True
    return False
```
- **Verification:** Replaced `.startswith("alpha_12345")` with strict equality `t == "alpha_12345"`. Any appended arbitrary payload evaluates to `False`, triggering `[HIGH_ENTROPY_BEARER_TOKEN]` (exit code 1).

### 2.2. Strict Local Secret Equality (`is_safe_local_secret`)
```python
EXACT_SAFE_LOCAL_SECRET_FIXTURES = {
    "token_12345",
    "secret_12345",
    "dummy_12345",
}

EXACT_SAFE_LOCAL_SECRET_REDACTIONS = {
    "[REDACTED]",
    "[REDACTED_SECRET]",
    "[REDACTED_TOKEN]",
    "<secret>",
    "<token>",
    "***",
    "...",
}

def is_safe_local_secret(suffix: str, filepath: str) -> bool:
    """
    Check if local secret suffix is safely redacted or standard documented fixture.
    Per C1621 / C1622: Strict equality ONLY. No startswith or prefix matching.
    """
    s = suffix.strip().strip('"\'`')
    if s in EXACT_SAFE_LOCAL_SECRET_REDACTIONS:
        return True
    if s in EXACT_SAFE_LOCAL_SECRET_FIXTURES:
        return True
    is_test_file = 'test_' in filepath or '/tests/' in filepath or filepath.startswith('tests/')
    if is_test_file and s.lower() in ('dummy', 'test', 'sample', 'example', 'mock'):
        return True
    return False
```
- **Verification:** Suffix matching strictly enforces membership in `EXACT_SAFE_LOCAL_SECRET_FIXTURES` or `EXACT_SAFE_LOCAL_SECRET_REDACTIONS`. No `startswith` or prefix allowance exists. Appended payloads fail closed (exit code 1).

### 2.3. Strict Redacted Token & URL Password Allowlist (`is_safe_redacted_token` & `is_safe_redacted_url_password`)
```python
def is_safe_redacted_url_password(pw: str) -> bool:
    """
    Check if URL password component is safely redacted.
    Per C1621 / C1622: Strict known marker allowlist ONLY.
    Arbitrary bracketed strings like [raw_secret] or <raw_secret> without known marker are REJECTED.
    """
    p = pw.strip().strip('"\'`')
    p_lower = p.lower()
    if p_lower in KNOWN_REDACTION_MARKERS or p in KNOWN_REDACTION_MARKERS:
        return True
    if re.match(r'^<[a-z0-9_]*token[a-z0-9_]*>$', p_lower):
        return True
    if re.match(r'^\[redacted(_[a-z0-9_]+)?\]$', p_lower):
        return True
    # Allow composite URL query redactions:
    # e.g. art_v1_[REDACTED_HASH]%3Fexpires%3D[REDACTED_EXPIRY]
    if p_lower.startswith('art_v1_[redacted_hash]') and (
        p_lower.endswith('%3fexpires%3d[redacted_expiry]') or p_lower.endswith('?expires=[redacted_expiry]')
    ):
        return True
    if p_lower in ('art_v1_[redacted]', 'art_v1_...'):
        return True
    return False
```
- **Verification:** Arbitrary bracketed strings (such as `[some_raw_secret]` or `<some_raw_secret>`) do NOT match explicit known redaction markers or the strict pattern `^\[redacted(_[a-z0-9_]+)?\]$`. They are rejected and flagged as `[CREDENTIAL_BEARING_URL]` (exit code 1).

### 2.4. Fail-Closed Handling for Staged Text with NUL Bytes (`read_staged_content`)
```python
def read_staged_content(filepath: str) -> str:
    """
    Read staged blob directly from git index as raw bytes.
    Per C1621 / C1622: Staged text deliverables containing NUL bytes fail closed with exit 2.
    Only recognized binary file extensions (.png, .jpg, .tar, .bin, etc.) can skip without error.
    """
    ...
    if is_binary_content(raw_bytes):
        ext = os.path.splitext(filepath)[1].lower()
        if ext in KNOWN_BINARY_EXTENSIONS:
            return ""
        # Staged text file containing NUL bytes -> fail closed!
        sys.stderr.write(
            f"publication_guard: error: binary content or NUL byte detected in staged text file: {sanitize_path_for_display(filepath)}\n"
        )
        sys.exit(2)

    return raw_bytes.decode("utf-8", errors="replace")
```
- **Verification:** Staged text files (e.g. `.md`, `.py`, `.json`, `.txt`) containing NUL bytes now trigger an operational error (`exit 2`) with an explicit stderr diagnostic, preventing silent evasion by inserting NUL bytes into public text files. Only recognized binary extensions (`KNOWN_BINARY_EXTENSIONS`) skip cleanly.

### 2.5. Fail-Closed Handling for Unmatched Explicit Staged Targets (`get_staged_files`)
```python
def get_staged_files(explicit_paths: Optional[Sequence[str]] = None) -> List[str]:
    ...
    if explicit_paths:
        ...
        # Check if any explicit path was unmatched
        unmatched = [p for p in explicit_paths if not normalized_targets.get(os.path.normpath(p), False)]
        if unmatched:
            for up in unmatched:
                sys.stderr.write(
                    f"publication_guard: error: explicit target not staged in git index: {sanitize_path_for_display(up)}\n"
                )
            sys.exit(2)

        return filtered

    return files
```
- **Verification:** If explicit paths are passed to `--staged <path>`, every specified path must match at least one staged entry in the git index. Any missing or unmatched path immediately exits with code 2.

---

## 3. Independent Verification Suite Execution on `db69e553`

### 3.1. Unit Test Suite (32/32 PASS)
Executed pure Python unittest suite in isolated scratch environment against committed source `db69e553`:
```bash
TMPDIR=.local/scratch/publication-guard-re-review python3 -m unittest -v tests/test_publication_guard.py
```
```text
test_arbitrary_bracketed_url_password_detected (tests.test_publication_guard.TestC1621StrictAllowlistNegativeCases.test_arbitrary_bracketed_url_password_detected) ... ok
test_caller_exit_code_propagation (tests.test_publication_guard.TestC1621StrictAllowlistNegativeCases.test_caller_exit_code_propagation) ... ok
test_local_secret_prefix_with_extra_payload_detected (tests.test_publication_guard.TestC1621StrictAllowlistNegativeCases.test_local_secret_prefix_with_extra_payload_detected) ... ok
test_tok_prefix_with_extra_payload_detected (tests.test_publication_guard.TestC1621StrictAllowlistNegativeCases.test_tok_prefix_with_extra_payload_detected) ... ok
test_clean_markdown_report (tests.test_publication_guard.TestCleanDocuments.test_clean_markdown_report) ... ok
test_clean_python_code (tests.test_publication_guard.TestCleanDocuments.test_clean_python_code) ... ok
test_explicit_binary_file_exits_2 (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_explicit_binary_file_exits_2) ... ok
test_missing_explicit_file_exit_2 (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_missing_explicit_file_exit_2) ... ok
test_no_arguments_exit_2 (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_no_arguments_exit_2) ... ok
test_sanitized_path_in_error (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_sanitized_path_in_error) ... ok
test_staged_binary_file_skips_cleanly (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_staged_binary_file_skips_cleanly) ... ok
test_staged_explicit_paths_filtering (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_staged_explicit_paths_filtering) ... ok
test_staged_flag_in_isolated_git_repo (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_staged_flag_in_isolated_git_repo) ... ok
test_staged_text_file_with_nul_byte_fails_closed (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_staged_text_file_with_nul_byte_fails_closed) ... ok
test_staged_unmatched_explicit_target_fails_closed (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_staged_unmatched_explicit_target_fails_closed) ... ok
test_stdin_flag_clean (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_stdin_flag_clean) ... ok
test_stdin_flag_violation (tests.test_publication_guard.TestCliFlagsAndEdgeCases.test_stdin_flag_violation) ... ok
test_credential_url_with_dummy_secret (tests.test_publication_guard.TestCredentialBearingUrls.test_credential_url_with_dummy_secret) ... ok
test_credential_url_with_raw_password (tests.test_publication_guard.TestCredentialBearingUrls.test_credential_url_with_raw_password) ... ok
test_mixed_newline_and_urlencoded_query_parameters (tests.test_publication_guard.TestCredentialBearingUrls.test_mixed_newline_and_urlencoded_query_parameters) ... ok
test_authorization_bearer_header (tests.test_publication_guard.TestHighEntropyBearerAndHeaders.test_authorization_bearer_header) ... ok
test_high_entropy_tok_token (tests.test_publication_guard.TestHighEntropyBearerAndHeaders.test_high_entropy_tok_token) ... ok
test_quoted_and_json_authorization_bearer_headers (tests.test_publication_guard.TestHighEntropyBearerAndHeaders.test_quoted_and_json_authorization_bearer_headers) ... ok
test_unredacted_admin_secret_literal (tests.test_publication_guard.TestLocalSecretLiterals.test_unredacted_admin_secret_literal) ... ok
test_unredacted_webhook_secret_literal (tests.test_publication_guard.TestLocalSecretLiterals.test_unredacted_webhook_secret_literal) ... ok
test_minted_art_v1_dummy_hex (tests.test_publication_guard.TestMintedTokenDetection.test_minted_art_v1_dummy_hex) ... ok
test_minted_art_v1_with_expiry_query (tests.test_publication_guard.TestMintedTokenDetection.test_minted_art_v1_with_expiry_query) ... ok
test_allowed_bracketed_redactions (tests.test_publication_guard.TestPublicRedactionPlaceholders.test_allowed_bracketed_redactions) ... ok
test_allowed_ellipsis_and_code_syntax (tests.test_publication_guard.TestPublicRedactionPlaceholders.test_allowed_ellipsis_and_code_syntax) ... ok
test_allowed_synthetic_fixtures (tests.test_publication_guard.TestPublicRedactionPlaceholders.test_allowed_synthetic_fixtures) ... ok
test_allowed_url_placeholders (tests.test_publication_guard.TestPublicRedactionPlaceholders.test_allowed_url_placeholders) ... ok
test_all_public_reports_pass (tests.test_publication_guard.TestPublicReportsSelfVerification.test_all_public_reports_pass) ... ok

----------------------------------------------------------------------
Ran 32 tests in 2.300s

OK
```

### 3.2. Test Suite Self-Verification
Executing the guard against `tests/test_publication_guard.py` (blob `e3b235d0c2f60b3a49a70a6041582f09979bec0f`):
```bash
python3 research/antigravity/tooling/publication_guard.py tests/test_publication_guard.py
```
- **Return Code:** `0`
- **Stdout:** (empty)
- **Stderr:** (empty)
- **Result:** Pinned test file does not trigger self-referential false positives.

### 3.3. Public Deliverables Self-Verification
Scanned all 7 public research deliverables:
```bash
python3 research/antigravity/tooling/publication_guard.py \
  research/antigravity/recovery/CHECK-DISTRIBUTION-RUNBOOK-PINS.md \
  research/antigravity/reviews/REV-A06-COMPARISON-CONTRACT.md \
  research/antigravity/dogfood/WARNING-LIFECYCLE-TRANSITION-REPORT.md \
  research/antigravity/adoption/A06-ADVISORY-ADOPTION-DECISION.md \
  research/antigravity/audit/PRIVATE-LINEAGE-AUDIT.md \
  research/antigravity/reviews/REV-PUBLICATION-GUARD.md \
  research/antigravity/reviews/REV-SDK-DISTRIBUTION-7692650.md
```
- **Return Code:** `0`
- **Result:** All 7 repository public reports pass with zero violations.

---

## 4. Negative Test Verification Receipts on `db69e553` (Executed in Scratch)

To independently confirm detection, exit codes, and secret value suppression without test harness mediation, all 6 negative cases were executed directly against committed blob `db69e553` in `/home/alexey/git/cloudflare-agent-git/.local/scratch/publication-guard-re-review/neg_tests_db69e553`:

| Case | Test Description & Synthetic Payload | Expected Exit | Measured Exit | Violations / Output Verification | Secret Suppression |
|---|---|---|---|---|---|
| **Case 1** | Documented `tok_` fixture prefix with appended arbitrary payload (`tok_` + `alpha_12345` + `_arbitrary_extra_secret`) | `1` | `1` | `neg1.md:1: [HIGH_ENTROPY_BEARER_TOKEN] High-entropy bearer token detected (pattern: tok_***)` | **PASS:** Appended payload string NOT present in stdout or stderr |
| **Case 2** | Documented local-secret fixture prefix with appended arbitrary payload (`admin-secret-` + `token_12345` + `_arbitrary_extra_secret`) | `1` | `1` | `neg2.md:1: [LOCAL_SECRET_LITERAL] Unredacted local secret literal detected (key: ***)` | **PASS:** Appended payload string NOT present in stdout or stderr |
| **Case 3** | Credential URL with arbitrary bracketed password lacking redaction marker (`http://token:` + `[some_raw_secret]` + `@localhost:8080/repo.git`) | `1` | `1` | `neg3.md:1: [CREDENTIAL_BEARING_URL] Credential-bearing URL detected with unredacted credentials (URL: ***)` | **PASS:** Raw password string NOT present in stdout or stderr |
| **Case 4** | Staged Markdown file in temporary git index containing NUL byte (`\x00`) executed via `--staged` | `2` | `2` | `publication_guard: error: binary content or NUL byte detected in staged text file: report.md` | **PASS:** Operational fail-closed; error emitted to stderr |
| **Case 5** | Passing unmatched explicit target to `--staged unmatched_target.md` | `2` | `2` | `publication_guard: error: explicit target not staged in git index: unmatched_target.md` | **PASS:** Operational fail-closed; error emitted to stderr |
| **Case 6** | Shell caller exit code propagation (`$?`) across clean target, violation target, and missing target | `0`, `1`, `2` | `0`, `1`, `2` | `clean.md` &rarr; `rc=0`<br>`dirty.md` &rarr; `rc=1`<br>`missing.md` &rarr; `rc=2` | **PASS:** Nonzero exit codes reliably propagate to calling shell/scripts |

---

## 5. Operational Invariants & Resource Accounting

- **Scratch Space Bounds:**
  - Scratch Root: `/home/alexey/git/cloudflare-agent-git/.local/scratch/publication-guard-re-review/`
  - Permissions: Mode `0700` (`drwx------`)
  - Measured Disk Usage: `620 KB` (strictly `<= 512 MB` budget).
- **`/tmp` Directory Isolation:**
  - `TMPDIR` variable strictly pointed into scratch root during test execution.
  - Zero bytes written to `/tmp`.
- **Memory Cooperative Slice:**
  - Python test runner and subprocesses executed well within the `<= 1500 MB` slice.
- **Value Suppression Assurance:**
  - Verification confirmed across all rules: stdout only reports rule IDs and descriptive markers (`***`), never the raw token or password value.
- **Working Tree Integrity:**
  - Zero unowned files touched; test repositories created and cleaned up entirely inside the scratch boundary.

---

## 6. Bounded Verdict & Operating Recommendation

- **Verdict:** **ACCEPT_REMEDIATED_SOURCE (db69e553)**
  - Git blob `db69e55339b8c94884d2fcbb521a510675814e27` (`research/antigravity/tooling/publication_guard.py`)
  - Git blob `e3b235d0c2f60b3a49a70a6041582f09979bec0f` (`tests/test_publication_guard.py`)
- **Bounded Certification Notice:**
  - The tool is certified for its documented pattern rules: `art_v1_` minted bearer tokens, `tok_` high-entropy tokens, quoted and unquoted `Authorization: Bearer` headers, credential-bearing URLs (passwords, usernames, and query tokens), and `admin/runner/sidecar/webhook` local secret literals.
  - In accordance with Codex C1622, C1625, and C1632 directives, claims of "complete against all evasions" are explicitly avoided. Heuristic pattern matching cannot guarantee prevention of arbitrary obfuscation, novel encodings, or unpatterned private material.
- **Publication Coordinator Operating Mode:**
  - The publication coordinator MUST remain on **DRAFT guard**.
  - `publication_guard.py` serves as a mandatory pre-commit tripwire and automated filter, but does not substitute for explicit author verification, private scratch isolation, or independent lineage audits.
