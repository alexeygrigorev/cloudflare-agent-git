# Review: Sessionless Model Enrollment (Commit 6fcde3f)

**Commit**: `6fcde3f`
**Target**: Sessionless FileBus enrollment source, tests, and receipt `RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json`

## 1. Audit: Model Task CID Mapping to FileBus Identity
- **Model Task CID**: `042b1c0b` (`042b1c0b-9b80-4e6d-98bb-593b8831a4f1` from orchestrator logs)
- **FileBus Identity**: `5a1ef421` (`5a1ef421-6da2-4519-adb3-d0cb48683cc0`)
- **Verification**: The execution receipt `RECEIPT-SESSIONLESS-MODEL-ENROLLMENT-01.json` logs the `identity_id` as `5a1ef421-6da2-4519-adb3-d0cb48683cc0`. Orchestrator inbox logs map CID `042b1c0b` (Gemini 3.8 worker) directly to this execution output and FileBus identity. The mapping is mathematically solid and correctly recorded in the execution receipt.

## 2. Reconcile: `task-model-worker-handshake-01` vs `t-bus-sessionless-model-enroll-01`
- **`t-bus-sessionless-model-enroll-01`**: This is the top-level orchestrator/continuation task tracking the overall work execution assignment.
- **`task-model-worker-handshake-01`**: This is the localized string hardcoded in `run_sessionless_model_enrollment.py` and passed as the `task_id` during the FileBus `enroll_agent()` call.
- **Reconciliation**: The model task running under `t-bus-sessionless-model-enroll-01` executed a verification script that internally labeled the bus interaction as `task-model-worker-handshake-01`. Consequently, the FileBus `rendered_namespaced_id` is recorded as `linux-worker-01/agent-bus/model-worker-01/-/task-model-worker-handshake-01`. They refer to the same workload, but one tracks the system-level orchestrator assignment, and the other is the specific bus namespace payload used during execution.

## 3. Verify Initiator/Receiver Independent Credential Custody
- **Review of Source**: `run_sessionless_model_enrollment.py` establishes the "head" initiator (`ant-head-initiator`, ID `ae6e...`) and the "worker" receiver (`model-worker-01`, ID `5a1ef421...`).
- **Custody Assessment**: The tokens generated are distinct and written separately to disk (the worker credential has mode `0o600`). However, the script instantiates both the initiator and the receiver within the *same* Python runtime execution. While the generated credentials are cryptographically independent, process-level custody is shared because a single Python test/helper script memory-space handles both actors to produce the receipt. True independent custody (as requested by principal review feedback in `orchestrator-inbox.json`) will require distinct processes communicating over the bus rather than a single script orchestrating both sides of the handshake.

## 4. Verify Zero Leakage of Sensitive Credentials or Parent Tokens
- **Environment and Inheritance Isolation**: The code employs deliberate pollution tests (`APLEXER_SESSION_ID=forbidden...`) and uses `reject_head_cred_inheritance` to actively reject synthetic leaks.
- **Verification**: The generated receipt proves successful isolation:
  - `tokens_are_distinct`: `true`
  - `head_token_sha256`: `d60418afcf520a0a57a5cc300cbf6c261ac8ff0e57c74e27e24f8ca01a7ee581`
  - `worker_token_sha256`: `0c4cc861cf91a0495a9dff4e77b4f173b6a7bdbc20938f46e6f27d13242f5733`
  - `head_cred_inheritance_guard_verified`: `true`
  - `ambient_aplexer_session_ignored`: `true`
- **Result**: Zero leakage confirmed. The worker token does not inherit the parent orchestrator token, and the sessionless boundary correctly strips all ambient aplexer session IDs (`session_id: null`).
