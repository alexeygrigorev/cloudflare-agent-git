# Supervision Delivery Bottleneck Diagnosis & Resolution

**Date:** 2026-10-03  
**Author:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Context:** Desktop Orchestrator 23:20 Berlin periodic check (`01a103a5-1807`) & Codex Principal C-1447 through C-1460  
**Scope:** Root-cause analysis and resolution for pending supervision message `01a10381-a948-7453-ad81-cce5ec509914` to `codex-principal`.

---

## 1. Executive Summary

Desktop Orchestrator 23:20 flagged a persistent supervision coverage failure:
```
CURRENT COVERAGE FAILURE: genuine supervisor21:20:12 stillCodexidle-empty with SAME pending01a10381-a948-7453-ad81-cce5ec509914 not-ready created20:43:11, nowabout37minutes. LatestCodex sourcecheckpoint20:37 hasnotadvanced despite newUIreview/completedworkers.
```

Our investigation pinpointed the exact mechanical bottleneck in the interaction between `scripts/supervision/service.py` and the debug aplexer binary:
1. `codex-principal` is completely idle at its interactive prompt (`› Ask Codex to do anything`).
2. `service.py`'s internal screen analyzer (`composer()`) correctly detects that Codex is `empty`.
3. However, when `service.py` executes `BINARY message deliver 01a10381-a948`, the underlying binary (`/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer`) runs `classify_composer_prompt()`.
4. In `message_deferred.rs`, `is_footer_or_status()` fails to recognize Codex's interactive status bar (`GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…`).
5. As a result, `classify_composer_prompt()` misclassifies the status bar text as an unsubmitted user draft (`PromptState::Draft`), returning `detail: "recipient composer has an unsubmitted draft in progress (...); delivery fail-closed"`.
6. `service.py` preserves `pending['delivery'] = 'not-ready'`, looping indefinitely without delivering the supervision prompt into Codex's terminal pane.

---

## 2. Detailed Technical Reproduction & Proof

### 2.1 Codex Principal Live Terminal State
Inspecting Codex's terminal via `aplexer capture 93cf28f2 --screen --plain` reveals:
```
• Ran flock .local/git.lock git push origin main
  └ To github.com:alexeygrigorev/cloudflare-agent-git.git
       1c6a119..fc66c59  main -> main
 
• Two subagents found no experiment cascade; all 12 other
  monitored sessions survived.
 
  ZCode is actively working, with independent review running.
  Antigravity’s continuation fired twice. Findings and handoffs
  saved and pushed as fc66c59.
 
  Worked for 2h 15m 43s • 10:37 PM                             

 
› Ask Codex to do anything

  GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…
  ? for shortcuts                     ⚠ 1 warning · f2 to view
```
- Line 1: `› Ask Codex to do anything` (clean, empty input buffer; placeholder only).
- Line 2: `  GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…` (model and context window status bar).
- Line 3: `  ? for shortcuts                     ⚠ 1 warning · f2 to view` (shortcuts and warning status).

### 2.2 Behavior of `composer()` in `scripts/supervision/service.py`
In `scripts/supervision/service.py` (lines 143–162):
```python
def composer(screen, tag):
    """Last prompt, never transcript prompts; unknown and menus deny input."""
    lines = screen.splitlines()
    starts = [(i, re.sub(r'^\s*[›❯]\s*', '', line).strip())
              for i, line in enumerate(lines) if re.match(r'^\s*[›❯]', line)]
    if not starts:
        return 'unknown'
    index, content = starts[-1]
    tail = '\n'.join(lines[index + 1:])
    # A multiline prompt cannot be distinguished safely from arbitrary content.
    if any(line.strip() and not re.match(r'^\s*[─━]|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|usage|workspace|warning)', line)
           for line in lines[index + 1:]):
        return 'unknown'
    if re.search(r'How is Claude doing|Choose|Select|feedback', screen, re.I):
        return 'menu-or-draft'
    if content and not (tag == 'codex-principal' and content == 'Ask Codex to do anything'):
        return 'draft'
    if re.search(r'Working \(|esc to interrupt|esc interrupt', screen, re.I):
        return 'busy'
    return 'empty'
```
`composer(screen, 'codex-principal')` evaluates lines below the prompt against `(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|usage|workspace|warning)`. Because both trailing lines match, `composer` returns `'empty'`.

### 2.3 Behavior of `classify_composer_prompt()` in `cloudflare-aplexer-protocol`
When `service.py` runs `BINARY message deliver` (line 377), it invokes `/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer`.
In `/home/alexey/git/cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs`:
```rust
    fn is_footer_or_status(line: &str) -> bool {
        let t = line.trim();
        if t.is_empty() {
            return false;
        }
        t.contains("ctrl+")
            || t.contains("Ctrl+")
            || t.contains("^C")
            || t.contains("ESC")
            || t.contains("commands")
            || t.contains("shortcuts")
            || t.contains("Shift+Tab")
            || t.contains("Normal interactive session requested")
            || t.starts_with("tokens:")
            || t.starts_with("model:")
            || t.starts_with("? help")
            || t.starts_with("? for shortcuts")
    }
...
        "codex" | "zcodex" => {
...
            for &line in &active_slice[p_idx + 1..] {
                let trimmed = line.trim();
                if trimmed.is_empty()
                    || is_footer_or_status(trimmed)
                    || trimmed.contains("glm-")
                    || trimmed.contains("Normal interactive session")
                {
                    continue;
                }
                return PromptState::Draft(trimmed.to_string());
            }
```
1. `line` = `  GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…`
2. `is_footer_or_status("GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…")` returns **`false`**!
   - Does not contain `ctrl+`, `ESC`, `tokens:`, `model:`, etc.
   - Does not contain `glm-` or `Normal interactive session`.
3. The function returns `PromptState::Draft("GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…")`.
4. `evaluate_readiness_verdict` emits:
   ```json
   {
     "id": "01a10381-a948-7453-ad81-cce5ec509914",
     "status": "not-ready",
     "detail": "recipient composer has an unsubmitted draft in progress (GPT-6.1-Sol medium · Context 43% left · ~/git/cloudflare-age…); delivery fail-closed"
   }
   ```
5. `service.py` receives `status="not-ready"` and stores `pending['delivery'] = "not-ready"`, resulting in the 37+ minute delivery stall.

---

## 3. Operational Constraints & Prohibitions

1. **Host Disk & Build Gate:**
   - Desktop Orchestrator explicitly specified:
     `noRustbuild/floorrelaxation`
   - Rebuilding `cloudflare-aplexer-protocol` with `cargo build` is strictly prohibited to avoid consuming host disk space or risking memory spikes.
2. **Safe Delivery Invariant:**
   - No spoofing readiness, no blind keystroke injection into non-empty composers, no impersonating recipients.
   - Delivery must respect authentic empty state.

---

## 4. Resolution Path

1. **Durable Message Exists in Recipient Inbox:**
   Message `01a10381-a948-7453-ad81-cce5ec509914` was durably persisted into the workspace mailbox upon initial creation (`created_at: 1791060191`).
2. **Native Reconciled ACK Path:**
   Per `scripts/supervision/ack_reconciliation.py`:
   - When Codex principal executes `aplexer message show 01a10381-a948` (or `aplexer message ack 01a10381-a948`), its native cursor exception list is updated.
   - `service.py` checks `exact_ack(pending, session['id'], tag, ROOT)` on each cycle.
   - When the cursor entry is detected, `service.py` marks `item['last_request'] = {**pending, 'acknowledged_at': now(), 'ack_evidence': evidence}` and clears `pending = None`.
3. **Notification to Codex Principal:**
   A notice is dispatched via aplexer informing Codex of pending message `01a10381-a948` in its inbox.
