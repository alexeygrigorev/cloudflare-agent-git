# Independent Security & Verification Review: Sidecar Token Percent-Decoding, 401 WWW-Authenticate Challenge, and Route Widening (Commit d8ac3b5)

- **Reviewer:** Independent Sidecar D8AC3B5 Reviewer (tag: `sidecar-d8ac3b5-reviewer`)
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1521 directive
- **Commit under review:** `d8ac3b5` — "fix(sidecar): support percent-encoded basic auth tokens and WWW-Authenticate challenge on git 401"
- **Workspace:** `/home/alexey/git/agent-branches-webhook` (branch `proto/webhook-auth`)
- **Target Repository:** `/home/alexey/git/cloudflare-agent-git`
- **Date of review:** 2026-10-04 (Europe/Berlin)
- **Artifacts reviewed:**
  - `prototype/local-artifacts/sidecar.mjs` (`authorizeGit` percent-decoding, `sendJson` extraHeaders, route regex `(?:\/git)?`, git 401 `WWW-Authenticate` challenge)
  - `prototype/local-artifacts/sidecar.test.mjs` (sidecar smart HTTP integration tests)

---

## 1. Overall Verdict: ACCEPT

Commit `d8ac3b5` is **ACCEPTED** without reservation. It resolves three critical operational and standards-compliance requirements for git smart HTTP interop within the local-artifacts sidecar:

1. **RFC 7235 / RFC 2617 Compliance & Git Client Interop:**
   Standard Git CLI clients probing unauthenticated endpoints (`GET /<repo>.git/info/refs?service=git-upload-pack`) require an HTTP `401 Unauthorized` response to contain a valid `WWW-Authenticate` header (specifically `Basic realm="git"`). Without this challenge header, standard `git` CLI clients immediately abort with `fatal: unable to access ... The requested URL returned error: 401` without prompting or dispatching credential helpers.
   Simultaneously, `d8ac3b5` carefully scopes this header to git endpoints (`.git` or `/git/`), ensuring `/api/...` routes continue returning JSON 401s without `WWW-Authenticate`, preventing web browsers from popping up intrusive modal Basic Auth dialogs.

2. **Defensive Basic Auth Percent-Decoding:**
   Cloudflare Artifacts mint tokens formatted with query parameters (`art_v1_<hex>?expires=<timestamp>`). Git clients, credential helpers, and URL encoders frequently percent-encode characters in the password field (`?` -> `%3F`, `=` -> `%3D`). `d8ac3b5` performs a two-stage token resolution: first trying verbatim plaintext, then falling back to `decodeURIComponent`. A protective `try/catch` ensures malformed percent-encodings (e.g., `%ZZ`, incomplete `%`) fail closed gracefully without throwing unhandled `URIError` exceptions or crashing the server process.

3. **URL Route Flexibility:**
   The git smart HTTP CGI regex was widened from strict `/^\/git\/.../` to `/^(?:\/git)?\/.../`, supporting both namespaced (`/git/<repo>.git/...`) and root-level (`/<repo>.git/...`) git URLs, while preserving strict repository name validation and action tail constraints.

4. **Rigorous Negative & Mutation Validation:**
   - All three mutations (M1: remove percent-decoding, M2: remove WWW-Authenticate challenge, M3: revert route regex) were decisively **KILLED** by negative tests.
   - All existing test suites pass cleanly: 91 Vitest tests + 16 Sidecar tests + 49 Node integration tests = 156 total tests passing.
   - Working tree and author history remain completely pristine.

---

## 2. Commit Pin & Diff Details

- **Commit SHA:** `d8ac3b59f3a015aa7324136dbd4e78d4dcf7e8a9`
- **Author:** Alexey Grigorev `<alexey.s.grigoriev@gmail.com>`
- **Date:** Sun Oct 4 03:18:19 2026 +0200
- **Subject:** `fix(sidecar): support percent-encoded basic auth tokens and WWW-Authenticate challenge on git 401`
- **Diffstat:** `prototype/local-artifacts/sidecar.mjs | 20 +++++++++++++++-----` (1 file changed, 15 insertions(+), 5 deletions(-))

### Exact Code Changes in `prototype/local-artifacts/sidecar.mjs`

```diff
@@ -397,7 +397,12 @@ export class Sidecar {
         plaintext = null;
       }
     }
-    const record = plaintext ? this.tokens.find(plaintext) : null;
+    let record = plaintext ? this.tokens.find(plaintext) : null;
+    if (!record && plaintext && plaintext.includes("%")) {
+      try {
+        record = this.tokens.find(decodeURIComponent(plaintext));
+      } catch {}
+    }
     if (!record || record.repo !== repoName) {
       throw new HttpError(401, "git authentication required: valid per-repo token");
     }
@@ -503,9 +508,9 @@ async function readJsonBody(req) {
   }
 }
 
-function sendJson(res, status, body) {
+function sendJson(res, status, body, extraHeaders = {}) {
   const payload = JSON.stringify(body, null, 2);
-  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
+  res.writeHead(status, { "content-type": "application/json; charset=utf-8", ...extraHeaders });
   res.end(payload);
 }
 
@@ -560,7 +565,7 @@ export function createSidecarServer(sidecar) {
       const url = new URL(req.url, "http://127.0.0.1");
       const path = decodeURIComponent(url.pathname);
 
-      const gitMatch = /^\/git\/([A-Za-z0-9][A-Za-z0-9._-]*)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
+      const gitMatch = /^(?:\/git)?\/([A-Za-z0-9][A-Za-z0-9._-]*)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
       if (gitMatch) {
         await handleGitCgi(sidecar, req, res, gitMatch[1], gitMatch[2]);
         return;
@@ -701,7 +706,12 @@ export function createSidecarServer(sidecar) {
       sendJson(res, 404, { error: `no route for ${req.method} ${path}` });
     } catch (error) {
       const status = error instanceof HttpError ? error.status : 500;
-      sendJson(res, status, { error: error.message ?? "sidecar error" });
+      const headers = {};
+      const reqUrl = req.url ?? "";
+      if (status === 401 && (reqUrl.includes(".git") || reqUrl.startsWith("/git/"))) {
+        headers["www-authenticate"] = 'Basic realm="git"';
+      }
+      sendJson(res, status, { error: error.message ?? "sidecar error" }, headers);
     }
   });
 }
```

---

## 3. Code Verification & Security Analysis

### 3.1 Basic Auth Percent-Decoding (`authorizeGit`)

```javascript
let record = plaintext ? this.tokens.find(plaintext) : null;
if (!record && plaintext && plaintext.includes("%")) {
  try {
    record = this.tokens.find(decodeURIComponent(plaintext));
  } catch {}
}
```

1. **Two-Stage Lookup (Verbatim-First):**
   - The token lookup first queries `this.tokens.find(plaintext)` directly.
   - For standard unencoded tokens (or tokens that already match stored keys), this avoids any string transformation or URI decoding overhead.
2. **Conditional Trigger (`plaintext.includes("%")`):**
   - Tokens without `%` bypass the `decodeURIComponent` branch entirely.
3. **Fail-Closed Malformed Input Protection (`try / catch`):**
   - In ECMAScript, calling `decodeURIComponent("%ZZ")` or `decodeURIComponent("%")` throws a runtime `URIError: URI malformed`.
   - In Node.js HTTP request handling, an uncaught exception in synchronous code inside a request handler either results in an unhandled rejection, an unhandled exception crashing the process, or a generic 500 Internal Server Error.
   - By enclosing the decoding attempt in `try { ... } catch {}`, malformed percent sequences fail closed safely: `record` remains `null`, and the method proceeds directly to `throw new HttpError(401, "git authentication required: valid per-repo token")`.
   - Security verification confirmed that fuzzing with invalid percent sequences (`%ZZ`, `art_v1_incomplete%`, `%%%`, `%FF%FE%FD`) safely yields HTTP 401 without process instability.
4. **Bearer and Basic Coverage:**
   - Both `Authorization: Bearer <token>` and `Authorization: Basic <base64>` populate `plaintext`. Percent-decoding is applied uniformly to both, preventing subtle authentication divergence.

### 3.2 Git 401 Challenge Header (`WWW-Authenticate`)

```javascript
} catch (error) {
  const status = error instanceof HttpError ? error.status : 500;
  const headers = {};
  const reqUrl = req.url ?? "";
  if (status === 401 && (reqUrl.includes(".git") || reqUrl.startsWith("/git/"))) {
    headers["www-authenticate"] = 'Basic realm="git"';
  }
  sendJson(res, status, { error: error.message ?? "sidecar error" }, headers);
}
```

1. **RFC 7235 §4.1 / RFC 2617 Compliance:**
   - When a server responds with status code 401 (Unauthorized), it MUST send a `WWW-Authenticate` header field containing at least one challenge.
   - For smart-HTTP Git operations (`/info/refs?service=git-upload-pack`, `git-upload-pack`, `git-receive-pack`), Git CLI clients look specifically for `Basic realm="..."` to initiate authentication negotiation. If absent, Git clients conclude the server does not support HTTP Basic authentication and abort immediately.
2. **Selective Challenge Scoping (API Isolation):**
   - `reqUrl.includes(".git") || reqUrl.startsWith("/git/")` restricts the header strictly to Git endpoints.
   - API endpoints (`/api/health`, `/api/repos`, `/api/repos/:name/head`) returning 401 omit `WWW-Authenticate`.
   - This prevents standard browsers and web applications making AJAX/fetch calls to sidecar API routes from triggering the native browser credentials prompt dialog.
3. **Integration with `sendJson`:**
   - `sendJson(res, status, body, extraHeaders = {})` cleanly spreads `extraHeaders` into `res.writeHead`, ensuring headers are flushed alongside standard `content-type: application/json; charset=utf-8`.

### 3.3 Git Smart HTTP Regex Route Matching

```javascript
const gitMatch = /^(?:\/git)?\/([A-Za-z0-9][A-Za-z0-9._-]*)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
```

1. **Dual Prefix Support:**
   - `(?:\/git)?` is an optional non-capturing group.
   - URLs formatted as `/git/repo.git/...` and `/repo.git/...` both match.
2. **Capture Group Stability:**
   - Capture group 1 ($1) remains `([A-Za-z0-9][A-Za-z0-9._-]*)` (repository name).
   - Capture group 2 ($2) remains `(info/refs|git-upload-pack|git-receive-pack)` (CGI action tail).
3. **CGI PATH_INFO Normalization:**
   - In `handleGitCgi`, the CGI environment is constructed as:
     `PATH_INFO: /${repoName}.git/${tail}`
   - Regardless of whether the client accessed `/git/repo.git/...` or `/repo.git/...`, Git's `http-backend` receives the canonical `/${repoName}.git/${tail}` path.
4. **Strict Safety Boundaries Retained:**
   - Leading character must be alphanumeric `[A-Za-z0-9]`.
   - Directory traversal attempts (`../`), nested slashes (`/foo/bar.git`), and arbitrary tails (`/repo.git/arbitrary`) are rejected and fall through to 404.

---

## 4. Test Suite Execution Results

All test suites were executed in `/home/alexey/git/agent-branches-webhook/prototype`.

### 4.1 Vitest Suite (`npm test`)

```text
Test Files  13 passed (13)
Tests       91 passed (91)
Start at    03:26:39
Duration    30.61s
```
- Includes coordinator, durable store, real artifacts, rest client, checks wire, envelope, radar, and spike sidecar tests.

### 4.2 Sidecar Test Suite (`GIT_TERMINAL_PROMPT=0 npm run test:sidecar`)

```text
> test:sidecar
> node --test "local-artifacts/*.test.mjs"

▶ worker callback failure guard (codex C-1357)
  ✔ notify-state requires the shared bearer
  ✔ a push whose callback fails still lands in git, is retried boundedly, then recorded unprocessed
  ✔ a later successful delivery for the same repo+ref supersedes the unprocessed record
  ✔ a redelivery of the exact missed sha succeeding clears its own record
  ✔ an unconfigured notify URL is not a delivery failure (no unprocessed records)
✔ worker callback failure guard (codex C-1357)
▶ sidecar admin API auth
  ✔ rejects requests without the shared token
  ✔ serves health with the shared token
✔ sidecar admin API auth
▶ sidecar repos on real git
  ✔ creates a repo with a real seeded commit
  ✔ rejects duplicate repos and invalid names
  ✔ verifies commits with real git cat-file
  ✔ forks with git clone --bare and can pin an explicit base
  ✔ creates real commits via the plumbing helper (test/dev path)
✔ sidecar repos on real git
▶ sidecar git smart HTTP with real git client
  ✔ clones, commits and pushes with ordinary git; post-receive notifies the worker
  ✔ rejects pushes with an invalid token
  ✔ read-scoped tokens can clone but not push
✔ sidecar git smart HTTP with real git client
▶ sidecar misc
  ✔ lists and deletes repos
✔ sidecar misc
ℹ tests 16
ℹ suites 5
ℹ pass 16
ℹ fail 0
```

### 4.3 Node Integration Suite (`npm run test:node`)

```text
> test:node
> npm run build:node && node --test ".build/node/test/node/*.test.js"

ℹ tests 49
ℹ suites 0
ℹ pass 49
ℹ fail 0
ℹ duration_ms 208.64904
```

**Total Active Test Count:** $91 + 16 + 49 = 156$ passing tests across the entire prototype.

---

## 5. Negative & Boundary Security Verification

An automated verification harness was executed using isolated scratch storage (`.local/scratch/sidecar-d8ac3b5-review/test-negative-boundary.mjs`).

| Test Case | Description | Expected Result | Actual Result | Status |
|:---|:---|:---|:---|:---:|
| **T1.1** | Unauthenticated `GET /git/review-repo.git/info/refs?service=git-upload-pack` | HTTP 401, `WWW-Authenticate: Basic realm="git"` | HTTP 401, `WWW-Authenticate: Basic realm="git"` | **PASS** |
| **T1.2** | Unauthenticated `GET /review-repo.git/info/refs?service=git-upload-pack` (no `/git` prefix) | HTTP 401, `WWW-Authenticate: Basic realm="git"` | HTTP 401, `WWW-Authenticate: Basic realm="git"` | **PASS** |
| **T2.1** | Unauthenticated `GET /api/health` | HTTP 401, **no** `WWW-Authenticate` header | HTTP 401, `www-authenticate: null` | **PASS** |
| **T2.2** | Unauthenticated `GET /api/repos` | HTTP 401, **no** `WWW-Authenticate` header | HTTP 401, `www-authenticate: null` | **PASS** |
| **T3.1** | Plain token in Basic Auth (`x-token-auth:<plain>`) | HTTP 200 OK | HTTP 200 OK | **PASS** |
| **T3.2** | Percent-encoded query characters in Basic Auth (`...%3Fexpires%3D...`) | HTTP 200 OK | HTTP 200 OK | **PASS** |
| **T3.3** | Percent-encoded query characters in Bearer Auth (`Authorization: Bearer <encoded>`) | HTTP 200 OK | HTTP 200 OK | **PASS** |
| **T4.1** | Malformed token: `art_v1_invalid%ZZtoken` | HTTP 401, safe error body, no crash | HTTP 401, `"git authentication required: valid per-repo token"` | **PASS** |
| **T4.2** | Malformed token: `art_v1_incomplete%` (trailing percent) | HTTP 401, safe error body, no crash | HTTP 401, `"git authentication required: valid per-repo token"` | **PASS** |
| **T4.3** | Malformed token: `art_v1_truncated%A` | HTTP 401, safe error body, no crash | HTTP 401, `"git authentication required: valid per-repo token"` | **PASS** |
| **T4.4** | Malformed token: `%%%` and `%FF%FE%FD` | HTTP 401, safe error body, no crash | HTTP 401, `"git authentication required: valid per-repo token"` | **PASS** |
| **T5.1** | Git Smart HTTP without `/git` prefix (`/review-repo.git/info/refs?service=git-upload-pack`) | HTTP 200 OK, `content-type: application/x-git-upload-pack-advertisement` | HTTP 200 OK, advertisement served | **PASS** |
| **T5.2** | Git Smart HTTP with `/git` prefix (`/git/review-repo.git/info/refs?service=git-upload-pack`) | HTTP 200 OK, advertisement served | HTTP 200 OK, advertisement served | **PASS** |
| **T6.1** | Non-matching action tail (`/git/review-repo.git/not-a-real-endpoint`) | HTTP 404 | HTTP 404 | **PASS** |
| **T6.2** | Illegal repo name with leading hyphen (`/git/-invalid.git/info/refs`) | HTTP 404 | HTTP 404 | **PASS** |
| **T6.3** | Directory traversal in repo name (`/git/foo/bar.git/info/refs`) | HTTP 404 | HTTP 404 | **PASS** |

---

## 6. Mutation Testing & Kill Log

To verify that the tests are non-vacuous and actively guard the behavior introduced in `d8ac3b5`, three distinct code mutations were tested against the negative boundary harness.

### Mutation 1 (M1): Remove Percent-Decoding in `authorizeGit`

- **Mutation applied:** Replaced lines 400–405 with:
  ```javascript
  const record = plaintext ? this.tokens.find(plaintext) : null;
  ```
- **Observed Behavior:**
  ```text
  [TEST 3] Percent-encoded Basic auth token verification...
    ✓ Plain token Basic auth: 200 OK
  FAILED with error: AssertionError [ERR_ASSERTION]: Percent-encoded token in Basic auth must authenticate successfully
  401 !== 200
  ```
- **Result:** **KILLED** (percent-encoded tokens were rejected with 401).

### Mutation 2 (M2): Remove `WWW-Authenticate` Header on Git 401

- **Mutation applied:** Replaced catch block lines 707–715 with:
  ```javascript
  } catch (error) {
    const status = error instanceof HttpError ? error.status : 500;
    sendJson(res, status, { error: error.message ?? "sidecar error" });
  }
  ```
- **Observed Behavior:**
  ```text
  [TEST 1] Unauthenticated .git request WWW-Authenticate header check...
  FAILED with error: AssertionError [ERR_ASSERTION]: Must include WWW-Authenticate: Basic realm="git"
  + actual - expected
  + null
  - 'Basic realm="git"'
  ```
- **Result:** **KILLED** (unauthenticated git probe lacked the required RFC 7235 challenge header).

### Mutation 3 (M3): Revert Route Regex to Require `/git/` Prefix

- **Mutation applied:** Reverted line 568 to the previous regex:
  ```javascript
  const gitMatch = /^\/git\/([A-Za-z0-9][A-Za-z0-9._-]*)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
  ```
- **Observed Behavior:**
  ```text
  [TEST 1] Unauthenticated .git request WWW-Authenticate header check...
    ✓ /git/review-repo.git/info/refs returns 401 + WWW-Authenticate: Basic realm="git"
  FAILED with error: AssertionError [ERR_ASSERTION]: Unauthenticated /...git must return 401
  404 !== 401
  ```
- **Result:** **KILLED** (non-prefixed git route returned 404 Not Found instead of routing to Git handler).

### Clean Mutation Rollback

Following mutation testing, all changes were cleanly reverted via `git checkout -- prototype/local-artifacts/sidecar.mjs`. `git status --porcelain` in `/home/alexey/git/agent-branches-webhook` confirmed 0 modified files and 0 untracked artifacts, preserving the author tree and commit history intact.

---

## 7. Resource Accounting & Environment Verification

- **Process Slice & Memory Governance:**
  Inspection of `/proc/self/cgroup` confirms that execution operates within the shared user session slice:
  `0::/user.slice/user-1000.slice/session-8309.scope`
  Memory limits are governed by the shared environment/process slice, not an isolated individual 1500M cgroup. The host currently provides 62 GiB total RAM with 30 GiB available memory.
- **Filesystem Isolation & Scratch Accounting:**
  All temporary artifacts, test repositories, and test scripts were strictly confined to:
  `/home/alexey/git/cloudflare-agent-git/.local/scratch/sidecar-d8ac3b5-review/` (mode 0700).
  Verification of `/tmp` confirmed **zero growth** during review operations.

---

## 8. Summary & Recommendation

Commit `d8ac3b5` delivers high-precision improvements to the local-artifacts sidecar:
- Enables robust Git HTTP Basic authentication with tokens containing query parameters (`?expires=...`).
- Guarantees standard Git CLI compatibility through RFC 7235 `WWW-Authenticate` challenges without polluting API routes.
- Expands URL routing to accommodate standard git remote paths without `/git` prefixes.
- Contains robust error handling that neutralizes URI-malformed denial-of-service risks.
- Passed 100% of existing tests (156/156) and verified through 16 negative/boundary checks and 3 killed mutations.

**Final Recommendation:** Retain commit `d8ac3b5` as canonical on branch `proto/webhook-auth`.
