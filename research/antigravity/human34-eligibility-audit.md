# HUMAN34 Time-Aware Provider Routing & Z.AI Eligibility Audit

**Date:** 2026-10-03T06:52:00+02:00 (Berlin)  
**Auditor / Team:** `antigravity-head` / `a16-runtime-protocol`  
**Reference Directives:** HUMAN34, `coordination/RESOURCE-POLICY.md`, peer requests `01a1000f-e6df`, `01a10011-1781`, `01a10018-dcbf`  

---

## 1. Executive Summary

This audit verifies host and account eligibility for the official Z.AI zero-quota promotional campaign ([`https://docs.z.ai/devpack/notice/event-glm-5.3-flash`](https://docs.z.ai/devpack/notice/event-glm-5.3-flash)) and documents current routing rules under `coordination/RESOURCE-POLICY.md`.

### Verdict: **ELIGIBLE (When Inside Campaign Window)**
- **Installed ZCode Version:** `3.14.0-7681` ($\ge 3.10$ required) — **PASS**
- **Model Configured & Used:** `glm-5.3-flash` — **PASS**
- **Entitled Route / Plan:** `builtin:zai-coding-plan` is active (`available`) — **PASS**
- **Campaign Temporal Window:** 23:00–09:00 SGT = **17:00–03:00 Berlin** daily through October 7, 2026.
- **Current Operational Status (06:52 Berlin):** **OUTSIDE the free window**. Current ZCode executions consume regular paid ZAI quota (currently 96% 5h / 81% weekly remaining). New independent execution should be prioritized on OpenCode and Gemini outside the window per policy.

---

## 2. Technical Evidence & Provenance

### 2.1 Installed ZCode Version
- **Command:** `dpkg -l | grep -i zcode`
- **Output:**
  ```text
  ii  zcode    3.14.0-7681    amd64
  ```
- **Harness CJS Path:** `/opt/ZCode/resources/glm/zcode.cjs`
- **Criteria:** Official notice requires ZCode version $\ge 3.10$. The installed version `3.14.0` satisfies this requirement.

### 2.2 Model Configuration in Codex-ZCode
- **Configuration File:** `/home/alexey/.zcodex/config.toml`
- **Settings:**
  ```toml
  model = "glm-5.3-flash"
  model_reasoning_effort = "max"
  model_provider = "zcode"
  ```
- **Criteria:** The official promotional event applies exclusively to `glm-5.3-flash`. Other models or tiers are ineligible or receive doubled allowance rather than zero quota. `zcodex` is strictly pinned to `glm-5.3-flash`.

### 2.3 Paid Coding Plan Entitlement & Route
- **Plan Cache:** `/home/alexey/.zcode/v2/coding-plan-cache.json`
- **Status:**
  ```json
  "builtin:zai-coding-plan": {
    "status": "available"
  },
  "builtin:zai-start-plan": {
    "status": "unavailable",
    "reason": "coding_plan_not_entitled"
  }
  ```
- **Criteria:** Campaign requires an active paid Coding Plan. The cache confirms `builtin:zai-coding-plan` is authenticated and entitled.

### 2.4 Quota Status & Measurement
- **Reading as of 2026-10-03 06:32 UTC:**
  - 5-hour window: **96.0% remaining** (used 4.0%, resets 07:16 UTC)
  - Weekly window: **81.0% remaining** (used 19.0%, resets Oct 6 15:47 UTC)
  - Banked resets available: **5** (must remain untouched per policy)
  - Limit reached: **false**

---

## 3. Operational Routing Policy

1. **Window Alignment:**
   - **Free Promotional Window:** 17:00–03:00 Berlin (23:00–09:00 SGT). During this window, eligible `glm-5.3-flash` tasks through `zcodex` consume zero quota under the verified campaign.
   - **Standard Window (Current):** 03:00–17:00 Berlin. Outside the promotional window, tasks draw from the standard paid quota.
2. **Current Routing Actions (06:52 Berlin):**
   - New independent research, testing, and implementation tasks should prioritize OpenCode (Space Bunny Free / Go) and Gemini (Antigravity).
   - Existing active ZCode sessions (`zcode-independent [64049aa2]`) remain productive on owned tasks; their usage is tracked and paid, not assumed free.
   - Under no circumstances should banked resets be redeemed or new purchases made.
3. **October 7 Boundary:** Reliance on the zero-quota entitlement will conservatively cease at the October 7 SGT boundary unless officially reconfirmed.
