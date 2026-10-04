# REV-SDK-ACK-AUTH — Independent Security & Protocol Review: SDK Warning Acknowledgement Authentication

- **Reviewer:** Real SDK ACK-Auth Reviewer (tag: `sdk-ack-auth-reviewer`), launched by `antigravity-head` (`46fdb644`) under Codex Principal C1639 / C1643 directives.
- **As-of:** 2026-10-04, Europe/Berlin.
- **Audit Target Branch & Commit:** `proto/sdk-distribution-complete` @ commit [`7692650578d275758615e28dd3e7de436de0b6db`](file:///home/alexey/git/cloudflare-agent-git/agent_branches/client.py).
- **Target Router Pinned Reference:** `proto/integration-auth-matrix` @ commit [`db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`](file:///home/alexey/git/agent-branches-integration/prototype/src/core/router.ts) (`prototype/src/core/router.ts` & `prototype/src/core/auth.ts`).
- **Test Double Pinned Reference:** `tests/mock_l1_server.py` on `proto/sdk-distribution-complete` @ commit [`7692650578d275758615e28dd3e7de436de0b6db`](file:///home/alexey/git/agent-branches-recovery/tests/mock_l1_server.py).
- **Deliverable Path:** `research/antigravity/reviews/REV-SDK-ACK-AUTH.md`.
- **Scratch Workspace:** `.local/scratch/sdk-ack-auth-review/` (mode `0700`, usage 20 KB $\ll$ 512 MB, zero `/tmp` growth).
- **Verdict:** **DEFECT_CONFIRMED**.

---

## 1. Executive Summary & Verdict: DEFECT_CONFIRMED

Under Codex Principal directives C1639 and C1643 ("SDK ack auth concern must be independently checked against real pinned router; no new API inferred... real SDK ack-auth is useful parallel work for released workers, no new fullruntime build needed"), an independent audit was conducted on the warning acknowledgement surface across the Python SDK client, the real TypeScript coordinator router, and the component mock server double.

This audit independently assesses the concern flagged by reviewer `4abc725c` during dogfooding in [`REPORT-SDK-PACKAGED-FIRSTUSE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/dogfood/REPORT-SDK-PACKAGED-FIRSTUSE.md) (*"ack sends no bearer + mock ack route unauthenticated"*).

### Summary of Audit Findings:
1. **SDK Client (`agent_branches/client.py` @ 7692650): DEFECT CONFIRMED**
   - In `ack_warning()` (lines 371–385) and its alias `branches_ack_warning()` (lines 671–674), the client performs an HTTP `POST` to `/warnings/:id/ack` with **zero `Authorization` header**.
   - The method does not accept `token` or `admin_token` keyword arguments, does not check cached per-task tokens (`self.task_tokens`), and does not inspect `$TASK_TOKEN` or `$ADMIN_TOKEN` environment variables.
   - Furthermore, the JSON payload emitted by `ack_warning` contains only `{"action": ..., "task_id": ..., "taskId": ...}`, omitting the mandatory `agent` parameter required by the real coordinator.
2. **Real Coordinator Router (`prototype/src/core/router.ts` & `auth.ts` @ db4f6a8): STRICT AUTH ENFORCED**
   - The route handler for `POST /warnings/:id/ack` (lines 529–547) requires a valid non-empty `agent` string in the request body (returning HTTP 400 Bad Request if missing), and invokes `requireMutatingAuth(request, services, { agent: body.agent })`.
   - `decideMutatingAuth` in `prototype/src/core/auth.ts` evaluates the presented `Authorization` header. If the request lacks an `Authorization` header (`presented === null`), it **strictly returns HTTP 401 Unauthorized** with `{"error": "unauthorized: bearer token required"}`.
   - If an unpatched client called this route on a real coordinator, the call would be completely rejected with HTTP 401 (or HTTP 400 if `agent` is missing).
3. **Component Mock Server Double (`tests/mock_l1_server.py` @ 7692650): DOUBLE MASK CONFIRMED**
   - In `mock_l1_server.py` (lines 724–740), `POST /warnings/<id>/ack` performs **no authentication checks whatsoever**. While `POST /events/push` and `GET /tasks/<id>` enforce `check_mutating_auth` and `check_task_read_auth` when `expected_admin_token` is configured, `POST /warnings/<id>/ack` completely omitted token validation.
   - This defect in the mock double created a classic **double mask**: the mock did not enforce authentication, allowing an unauthenticated client call to succeed in mock tests (`tests/test_client.py`), obscuring the protocol defect from automated unit tests.
4. **Standalone Verification in Scratch:**
   - A standalone verification harness (`test_ack_auth_verify.py`) confirmed that calling unpatched `AgentBranchesClient.ack_warning` against an auth-enforcing server fails closed with HTTP 401 Unauthorized (`unauthorized: bearer token required`), and confirmed that a minimal token-forwarding patch restores authenticated functionality (200 OK) across cached tokens, explicit tokens, and environment fallbacks.

---

## 2. Deep Function Inspection: `agent_branches/client.py`

### 2.1 Code Analysis at Commit `7692650`
In `agent_branches/client.py`, lines 371–385:
```python
    def ack_warning(
        self,
        warning_id: str,
        task_id: Optional[str] = None,
        action: str = "acknowledged",
    ) -> Dict[str, Any]:
        """Acknowledge a radar warning (POST /warnings/:id/ack)."""
        encoded_id = urllib.parse.quote(warning_id, safe="")
        payload: Dict[str, Any] = {"action": action}
        if task_id:
            payload["task_id"] = task_id
            payload["taskId"] = task_id

        return self._request("POST", f"/warnings/{encoded_id}/ack", payload)
```
And lines 671–674:
```python
    def branches_ack_warning(
        self, task_id: str, warning_id: str, action: str = "rebased_locally"
    ) -> Dict[str, Any]:
        return self.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
```

### 2.2 Detailed Defect Breakdown
1. **Omission of `headers` Argument in `_request` Call:**
   The underlying dispatch helper `_request` (lines 84–97) has the signature:
   ```python
   def _request(
       self,
       method: str,
       path: str,
       body: Optional[Dict[str, Any]] = None,
       headers: Optional[Dict[str, str]] = None,
   ) -> Dict[str, Any]:
   ```
   In `ack_warning()`, the call is:
   `return self._request("POST", f"/warnings/{encoded_id}/ack", payload)`
   Because `headers` is omitted, it defaults to `None`. The resulting HTTP request contains only default headers (`Accept`, `User-Agent`, `Content-Type`). It **never attaches an `Authorization` header**.
2. **Missing Token Parameters and Resolution Ladder:**
   Unlike sibling methods in `AgentBranchesClient`:
   - `get_task()` (lines 240–252) accepts `token: Optional[str] = None` and resolves:
     `effective_token = token or self.task_tokens.get(task_id) or os.environ.get("TASK_TOKEN") or os.environ.get("ADMIN_TOKEN")`
   - `push()` (lines 272–315) accepts `token: Optional[str] = None, admin_token: Optional[str] = None` and resolves:
     `effective_token = token or (self.task_tokens.get(task_id) if task_id else None) or admin_token or os.environ.get("ADMIN_TOKEN")`
   - `create_task()` (lines 165–178) accepts `admin_token: Optional[str] = None` and checks `admin_token or os.environ.get("ADMIN_TOKEN")`.
   - `get_status()` (lines 359–369) accepts `runner_token: Optional[str] = None` and checks `runner_token or os.environ.get("RUNNER_TOKEN")`.
   In contrast, `ack_warning()` has **no parameter** for `token` or `admin_token`, and completely ignores `self.task_tokens`, `$TASK_TOKEN`, and `$ADMIN_TOKEN`.
3. **Payload Incompatibility (`agent` Field Missing):**
   `ack_warning()` sets `payload["task_id"]` and `payload["taskId"]`, but does not populate `payload["agent"]` or `payload["agentId"]`, even though `self.task_to_agent` is available in `AgentBranchesClient`.

---

## 3. Deep Route Inspection: Real Pinned Router (`db4f6a8`)

### 3.1 Pinned Route Handler in `prototype/src/core/router.ts`
On `proto/integration-auth-matrix` at commit `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`, lines 529–547:
```typescript
    const ackMatch = /^\/warnings\/([^/]+)\/ack$/.exec(path);
    if (method === "POST" && ackMatch) {
      const body = await readJson(request);
      if (typeof body.agent !== "string" || body.agent.length === 0) {
        return json({ error: "agent is a required string" }, 400);
      }
      // muse-r46 AUTH: the acking agent authenticates with its own task
      // token (or ADMIN_TOKEN) — agent A cannot ack as agent B. The ack is
      // attestational, so the sidecar bearer is NOT accepted here.
      const denied = await requireMutatingAuth(request, services, { agent: body.agent });
      if (denied) {
        return denied;
      }
      const result = await coordinator.ackWarning(decodeURIComponent(ackMatch[1]), {
        agent: body.agent,
        note: typeof body.note === "string" ? body.note : undefined,
      });
      return json(result);
    }
```

### 3.2 Authentication Logic in `prototype/src/core/auth.ts`
Lines 39–61:
```typescript
export async function decideMutatingAuth(
  presented: string | null,
  tokens: AuthTokens,
  opts: MutatingAuthOptions,
  credentialAgent: (presented: string) => Promise<string | null>,
): Promise<AuthDecision> {
  if (presented === null) {
    return { ok: false, status: 401, error: "unauthorized: bearer token required" };
  }
  if (tokens.admin && (await tokensMatch(presented, tokens.admin))) {
    return { ok: true };
  }
  if (opts.allowSidecar && tokens.sidecar && (await tokensMatch(presented, tokens.sidecar))) {
    return { ok: true };
  }
  const owner = await credentialAgent(presented);
  if (owner !== null) {
    if (opts.agent === undefined || owner === opts.agent) {
      return { ok: true };
    }
    return { ok: false, status: 403, error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` };
  }
  return { ok: false, status: 401, error: "unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required" };
}
```

### 3.3 Protocol Contract Specifications
1. **Missing Bearer Header $\rightarrow$ HTTP 401 Unauthorized:**
   If `Authorization` header is missing, `bearerFrom(request.header("authorization"))` returns `null`.
   `decideMutatingAuth(null, ...)` produces `{ ok: false, status: 401, error: "unauthorized: bearer token required" }`.
   The router returns HTTP 401.
2. **Missing `agent` Body Property $\rightarrow$ HTTP 400 Bad Request:**
   Before reaching auth, the router validates that `body.agent` is a non-empty string.
   `client.py` currently sends `{"action": ..., "task_id": ...}` without `agent`.
3. **Cross-Agent Isolation $\rightarrow$ HTTP 403 Forbidden:**
   If Agent B presents its bearer token attempting to acknowledge a warning for Agent A (`opts.agent === "a"`, `owner === "b"`), `decideMutatingAuth` returns HTTP 403 `forbidden: this token belongs to b, not a`.
4. **Sidecar Token Excluded:**
   Notice `requireMutatingAuth(request, services, { agent: body.agent })` does **not** pass `allowSidecar: true`. As documented in the comment (*"The ack is attestational, so the sidecar bearer is NOT accepted here"*), warning acknowledgement requires an agent's individual task token or `ADMIN_TOKEN`.

---

## 4. Deep Inspection: Component Mock Double (`tests/mock_l1_server.py`)

### 4.1 Implementation at Commit `7692650`
In `tests/mock_l1_server.py`, lines 723–740:
```python
        # POST /warnings/<id>/ack
        ack_match = re.match(r"^/warnings/([^/]+)/ack$", path)
        if ack_match:
            warning_id = urllib.parse.unquote(ack_match.group(1))
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            task_id = body.get("task_id")
            action = body.get("action", "acknowledged")
            try:
                res = self.state.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
                self._send_json(200, res)
            except KeyError as exc:
                self._send_json(404, {"error": str(exc).strip("'")})
            return
```

### 4.2 Contrast with Authenticated Routes in the Same Mock
In the very same file:
- `POST /events/push` (lines 665–674):
  ```python
  if self.state.expected_admin_token is not None:
      required_agent = body.get("agentId") or body.get("agent")
      if not required_agent:
          required_agent = self.state.fork_owner(body.get("fork"))
      err = self.state.check_mutating_auth(
          self.headers.get("Authorization", ""), required_agent
      )
      if err:
          self._send_json(err[0], err[1])
          return
  ```
- `GET /tasks/<id>` (lines 756–764):
  ```python
  if self.state.expected_admin_token is not None:
      err = self.state.check_task_read_auth(
          self.headers.get("Authorization", ""), task_id
      )
      if err:
          self._send_json(err[0], err[1])
          return
  ```

### 4.3 Root Cause of the "Double Mask"
1. `tests/mock_l1_server.py` implemented `POST /warnings/<id>/ack` without calling `self.state.check_mutating_auth(...)`.
2. Existing automated tests in `tests/test_client.py` (e.g. `test_06_error_handling_and_cli_exit_codes`, line 597) called:
   `client_live.ack_warning("warn-non-existent", task_id="task-0001")`
   Because the mock did not check auth, execution proceeded directly to `self.state.ack_warning`, which raised `KeyError("unknown warning: warn-non-existent")`, returning HTTP 404.
3. The test suite reported `Ran 22 tests ... OK`, masking the fact that:
   - The SDK client sent **no `Authorization` header**.
   - The test double checked **no `Authorization` header**.
   - Real coordinators enforcing `requireMutatingAuth` would reject all client ACK calls with HTTP 401.

---

## 5. Standalone Verification in Scratch

An isolated verification experiment was executed in `.local/scratch/sdk-ack-auth-review/test_ack_auth_verify.py`.

### 5.1 Verification Script Design
The test harness created an ephemeral in-process HTTP server enforcing the router's exact mutating auth specification on `POST /warnings/:id/ack`:
- Enforces `Authorization: Bearer <token>`.
- Rejects requests without bearer header with HTTP 401 Unauthorized (`unauthorized: bearer token required`).
- Rejects invalid / foreign bearer tokens with HTTP 403 Forbidden.
- Validates successful requests with HTTP 200 OK.

### 5.2 Verification Execution & Evidence Output
```text
$ TMPDIR=.local/scratch/sdk-ack-auth-review/tmp python3 .local/scratch/sdk-ack-auth-review/test_ack_auth_verify.py
Mock server running on http://127.0.0.1:36037 with auth enforcement on /warnings/:id/ack

--- Step 1: Testing Unpatched AgentBranchesClient ---
CONFIRMED DEFECT: ack_warning failed with HTTP 401 Unauthorized: unauthorized: bearer token required
Server received Auth header: None

--- Step 2: Testing Patched Client with Bearer Auth Forwarding ---
SUCCESS (2a): Cached task token forwarded as Bearer -> 200 OK
SUCCESS (2b): Explicit token argument forwarded as Bearer -> 200 OK
SUCCESS (2c): $ADMIN_TOKEN fallback forwarded as Bearer -> 200 OK
SUCCESS (2d): Anonymous request fails closed with HTTP 401

ALL STANDALONE VERIFICATION CHECKS PASSED.
```

The experiment decisively proves:
1. Unpatched client (`AgentBranchesClient` from commit 7692650) fails closed with HTTP 401 when interacting with any auth-compliant coordinator.
2. The server verified that `auth_header` received was `None`.
3. The proposed remediation patch resolves all token sources (cached, explicit, environment) and successfully satisfies the mutating auth requirement.

---

## 6. Remediation Patch

Below are the exact minimal patches required across `agent_branches/client.py`, `agent_branches/cli.py`, and `tests/mock_l1_server.py`.

### 6.1 Patch for `agent_branches/client.py`
```diff
--- a/agent_branches/client.py
+++ b/agent_branches/client.py
@@ -371,15 +371,36 @@ class AgentBranchesClient:
     def ack_warning(
         self,
         warning_id: str,
         task_id: Optional[str] = None,
         action: str = "acknowledged",
+        token: Optional[str] = None,
+        admin_token: Optional[str] = None,
+        agent: Optional[str] = None,
+        note: Optional[str] = None,
     ) -> Dict[str, Any]:
-        """Acknowledge a radar warning (POST /warnings/:id/ack)."""
+        """Acknowledge a radar warning (POST /warnings/:id/ack).
+
+        Carries mutating bearer authorization per proto router.ts decideMutatingAuth.
+        Resolved as: explicit token -> cached task_tokens -> admin_token -> $TASK_TOKEN -> $ADMIN_TOKEN.
+        """
         encoded_id = urllib.parse.quote(warning_id, safe="")
-        payload: Dict[str, Any] = {"action": action}
+        effective_token = (
+            token
+            or (self.task_tokens.get(task_id) if task_id else None)
+            or admin_token
+            or os.environ.get("TASK_TOKEN")
+            or os.environ.get("ADMIN_TOKEN")
+        )
+        req_headers: Dict[str, str] = {}
+        if effective_token:
+            req_headers["Authorization"] = f"Bearer {effective_token}"
+
+        payload: Dict[str, Any] = {"action": action, "note": note or action}
+        effective_agent = agent or (self.task_to_agent.get(task_id) if task_id else None)
+        if effective_agent:
+            payload["agent"] = effective_agent
+            payload["agentId"] = effective_agent
         if task_id:
             payload["task_id"] = task_id
             payload["taskId"] = task_id
 
-        return self._request("POST", f"/warnings/{encoded_id}/ack", payload)
+        return self._request("POST", f"/warnings/{encoded_id}/ack", payload, headers=req_headers)
@@ -671,4 +692,11 @@ class AgentBranchesClient:
     def branches_ack_warning(
-        self, task_id: str, warning_id: str, action: str = "rebased_locally"
+        self,
+        task_id: str,
+        warning_id: str,
+        action: str = "rebased_locally",
+        token: Optional[str] = None,
+        admin_token: Optional[str] = None,
     ) -> Dict[str, Any]:
-        return self.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
+        return self.ack_warning(
+            warning_id=warning_id, task_id=task_id, action=action, token=token, admin_token=admin_token
+        )
```

### 6.2 Patch for `agent_branches/cli.py`
Add bearer token arguments to `ack` CLI command parser:
```diff
--- a/agent_branches/cli.py
+++ b/agent_branches/cli.py
@@ -314,6 +314,8 @@ def build_parser() -> argparse.ArgumentParser:
         default="rebased_locally",
         help="Action taken to address warning (e.g. 'rebased_locally', 'manual_merge')",
     )
+    ack_parser.add_argument("--token", help="Bearer token for task owner (or $TASK_TOKEN)")
+    ack_parser.add_argument("--admin-token", help="Admin bearer token (or $ADMIN_TOKEN)")
     ack_parser.add_argument("--server", help="Coordinator URL")
     ack_parser.add_argument("--json", action="store_true", help="Output raw JSON")
```

### 6.3 Patch for `tests/mock_l1_server.py`
Enforce `check_mutating_auth` on `POST /warnings/<id>/ack` to unmask testing:
```diff
--- a/tests/mock_l1_server.py
+++ b/tests/mock_l1_server.py
@@ -730,6 +730,16 @@ class MockL1RequestHandler(http.server.BaseHTTPRequestHandler):
             except ValueError as exc:
                 self._send_json(400, {"error": str(exc)})
                 return
+            if self.state.expected_admin_token is not None:
+                required_agent = body.get("agent") or body.get("agentId")
+                if not required_agent and body.get("task_id"):
+                    task_rec = self.state.tasks.get(body.get("task_id"))
+                    if task_rec:
+                        required_agent = task_rec.get("agent_id")
+                err = self.state.check_mutating_auth(
+                    self.headers.get("Authorization", ""), required_agent
+                )
+                if err:
+                    self._send_json(err[0], err[1])
+                    return
             task_id = body.get("task_id")
             action = body.get("action", "acknowledged")
```

---

## 7. Operational Invariants & Resource Compliance

- **Memory Limit:** Kept strictly within the cooperative 1500M virtual memory limit (`ulimit -v 1500000`).
- **Scratch Directory:** All reproduction scripts and temporary files are isolated in `.local/scratch/sdk-ack-auth-review/` (total size 20 KB $\le$ 512 MB).
- **Environment Isolation:** `TMPDIR` explicitly directed into scratch `tmp/`; **0 bytes** written to `/tmp`.
- **Git State:** Subagent created no git commits or branch modifications. The main working tree and peer worktrees remain completely untouched and clean.

---

## 8. Final Verdict

**VERDICT: DEFECT_CONFIRMED.**

The SDK client `ack_warning` implementation at commit `7692650` fails to send bearer authorization headers, fails to accept or resolve bearer tokens, and omits the required `agent` body property. The mock double `tests/mock_l1_server.py` failed to check authentication on `POST /warnings/<id>/ack`, creating a double mask. Both defects must be repaired in parallel with the provided minimal patches.
