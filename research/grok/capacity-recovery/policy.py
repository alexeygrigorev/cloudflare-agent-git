"""Offline dry-run policy for Codex/Grok capacity recovery.

Uninstalled candidate. Never talks to a live pane, never forges idle, never
bypasses native NOTREADY. Tests must not be labelled native success.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Optional

CAPACITY_PHRASE = "Selected model is at capacity. Please try a different model."
FIRST_RETRY_S = 180
MAX_RETRIES = 3
BACKOFF_S = (180, 360, 720)
CODEX_MIN_REMAINING = 15.0
# OPERATING-MODEL new-worker disk target. Recovery scratch for THIS task
# (human request) is 8GiB; do not use 8GiB as a worker-launch floor.
NEW_WORKER_ROOT_FLOOR_GIB = 50.0
TASK_SCRATCH_ROOT_FLOOR_GIB = 8.0
ROOT_FLOOR_GIB = TASK_SCRATCH_ROOT_FLOOR_GIB
MEM_FLOOR_GIB = 10.0
BOTTOM_WINDOW_LINES = 12
EMPTY_CODEX_PLACEHOLDER = "Ask Codex to do anything"
ENGINE_EVENT_PROVENANCE = "engine_event"

MENU_RE = re.compile(r"(?:How is Claude doing|\bChoose\b|\bSelect\b|\bfeedback\b)", re.I)
BUSY_RE = re.compile(r"Working \(|esc to interrupt|esc interrupt", re.I)
QUOTA_RE = re.compile(r"limit[_\s-]?reached|quota exceeded|usage limit", re.I)
TRANSPORT_RE = re.compile(r"mailbox is busy|connection reset|temporarily unavailable", re.I)
QUOTE_PREFIX_RE = re.compile(r"^\s*(?:>{1,3}|\|)\s+")


@dataclass(frozen=True)
class QuotaSample:
    """Fresh quota. Unknown or missing relevant windows fail closed.

    remaining is the minimum of present windows, never a substitute for a
    missing 5h/weekly/monthly window.
    """

    provider: str
    status: str
    windows: Mapping[str, Optional[float]]
    limit_reached: bool
    error: Optional[str] = None
    required_windows: tuple[str, ...] = ("weekly",)

    @property
    def remaining(self) -> Optional[float]:
        vals = [v for v in self.windows.values() if v is not None]
        return min(vals) if vals else None

    @property
    def unknown(self) -> bool:
        if self.status != "ok" or self.error is not None:
            return True
        if not self.windows:
            return True
        for name in self.required_windows:
            if name not in self.windows or self.windows[name] is None:
                return True
        return False


@dataclass(frozen=True)
class ResourceSample:
    root_free_gib: float
    mem_available_gib: float
    operation: str = "recovery_scratch"


@dataclass(frozen=True)
class NativeReadiness:
    """What the installed deliver/readiness path actually returned.

    status is one of: ready, not-ready, absent, unknown.
    reason is the native detail string when present.
    """

    status: str
    reason: str = ""
    reported_state: Optional[str] = None
    derived_state: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class Identity:
    session_id: str
    tag: str
    workspace: str
    engine: str
    expected_session_id: str
    expected_tag: str
    expected_workspace: str


@dataclass
class Observation:
    full_screen: str
    bottom_screen: Optional[str] = None
    second_bottom_screen: Optional[str] = None
    quoted_history: str = ""
    now_s: float = 0.0
    last_error_s: Optional[float] = None
    retry_count: int = 0
    identity: Optional[Identity] = None
    quota: Optional[QuotaSample] = None
    resources: Optional[ResourceSample] = None
    native: Optional[NativeReadiness] = None
    conversation_id: str = ""
    sender_owns_message: bool = True
    dry_run: bool = True
    deployed: bool = False
    capacity_provenance: str = "unknown"


@dataclass
class Decision:
    action: str
    reason: str
    wait_s: Optional[int] = None
    retry_count: int = 0
    fingerprint: str = ""
    native_fix_required: bool = False
    would_inject: bool = False
    would_switch_model: bool = False
    deployed: bool = False
    extras: Mapping[str, Any] = field(default_factory=dict)


def bottom_window(screen: str, n: int = BOTTOM_WINDOW_LINES) -> str:
    lines = [ln for ln in screen.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def _in_quoted_lines(text: str, phrase: str) -> bool:
    if phrase not in text:
        return False
    for line in text.splitlines():
        if phrase in line and QUOTE_PREFIX_RE.match(line):
            return True
    return False


def classify_capacity_signal(
    full_screen: str,
    quoted_history: str = "",
    bottom: Optional[str] = None,
    provenance: str = "unknown",
) -> str:
    """Screen phrase is not native error provenance.

    live_capacity requires an engine/native error event plus unquoted bottom
    phrase. Last-N-line text alone is unproven_screen (tool logs, recap).
    """
    live = bottom if bottom is not None else bottom_window(full_screen)
    in_live = CAPACITY_PHRASE in live
    in_quoted = CAPACITY_PHRASE in quoted_history or _in_quoted_lines(full_screen, CAPACITY_PHRASE)
    in_full_only = CAPACITY_PHRASE in full_screen and not in_live
    if in_quoted or in_full_only:
        return "historical_quoted"
    if in_live and not _in_quoted_lines(live, CAPACITY_PHRASE):
        if provenance == ENGINE_EVENT_PROVENANCE:
            return "live_capacity"
        return "unproven_screen"
    return "absent"


def _is_footer(line: str) -> bool:
    t = line.strip()
    if not t:
        return True
    return (
        "ctrl+" in t
        or "Ctrl+" in t
        or t.startswith("? ")
        or t.startswith("tokens:")
        or t.startswith("model:")
        or "GPT-" in t and "medium" in t
        or t.endswith("shortcuts")
    )


def classify_composer(full_screen: str, tag: str = "codex-principal", bottom: Optional[str] = None) -> str:
    """Last-prompt / bottom-window classifier. Whole-screen Select is not used here."""
    window = bottom if bottom is not None else bottom_window(full_screen)
    lines = window.splitlines()
    starts = [
        (i, re.sub(r"^\s*[›❯]\s*", "", line).strip())
        for i, line in enumerate(lines)
        if re.match(r"^\s*[›❯]", line)
    ]
    if not starts:
        return "unknown"
    index, content = starts[-1]
    if re.search(r"How is Claude doing|\bChoose\b|\bfeedback\b", window, re.I) or re.search(
        r"\bSelect\b(?!ed model is at capacity)", window
    ):
        return "menu-or-draft"
    rest = []
    for line in lines[index + 1 :]:
        t = line.strip()
        if _is_footer(t):
            continue
        rest.append(t)
    placeholder = tag == "codex-principal" and content == EMPTY_CODEX_PLACEHOLDER
    if (content and not placeholder) or rest:
        return "draft"
    if BUSY_RE.search(window):
        return "busy"
    return "empty"


def classify_blocker(obs: Observation) -> str:
    bottom = obs.bottom_screen if obs.bottom_screen is not None else bottom_window(obs.full_screen)
    cap = classify_capacity_signal(obs.full_screen, obs.quoted_history, bottom, obs.capacity_provenance)
    composer = classify_composer(obs.full_screen, _tag(obs), bottom)
    if obs.identity and _identity_stale(obs.identity):
        return "stale_identity"
    if composer == "draft":
        return "draft"
    if composer == "busy" or BUSY_RE.search(bottom):
        return "busy_tools"
    if composer == "unknown":
        return "unknown_composer"
    if composer == "menu-or-draft":
        return "menu_or_draft"
    if TRANSPORT_RE.search(bottom):
        return "transport"
    if obs.quota is not None:
        if obs.quota.unknown:
            return "quota_unknown"
        if obs.quota.limit_reached or (
            obs.quota.provider == "codex" and obs.quota.remaining is not None and obs.quota.remaining <= CODEX_MIN_REMAINING
        ):
            return "quota_denied"
    if QUOTA_RE.search(bottom) and cap != "live_capacity":
        return "quota_denied"
    if cap == "historical_quoted":
        return "historical_quoted"
    if cap == "unproven_screen":
        return "unproven_screen"
    if cap == "live_capacity":
        return "live_capacity"
    if obs.native and obs.native.status == "not-ready":
        return "native_not_ready"
    return "clear"


def _tag(obs: Observation) -> str:
    if obs.identity:
        return obs.identity.tag
    return "codex-principal"


def _identity_stale(ident: Identity) -> bool:
    return (
        ident.session_id != ident.expected_session_id
        or ident.tag != ident.expected_tag
        or ident.workspace != ident.expected_workspace
        or not ident.session_id
    )


def resource_floor_gib(operation: str) -> float:
    if operation == "new_worker":
        return NEW_WORKER_ROOT_FLOOR_GIB
    return TASK_SCRATCH_ROOT_FLOOR_GIB


def resource_ok(sample: Optional[ResourceSample]) -> bool:
    if sample is None:
        return False
    floor = resource_floor_gib(sample.operation)
    return sample.root_free_gib >= floor and sample.mem_available_gib >= MEM_FLOOR_GIB


def empty_twice(obs: Observation) -> bool:
    first = classify_composer(obs.full_screen, _tag(obs), obs.bottom_screen)
    second_src = obs.second_bottom_screen
    if second_src is None:
        return False
    second = classify_composer(second_src, _tag(obs), second_src)
    return first == "empty" and second == "empty"


def native_allows_retry(native: Optional[NativeReadiness]) -> tuple[bool, str, bool]:
    """Return (ok, reason, native_fix_required)."""
    if native is None or native.status == "absent":
        return False, "native_readiness_absent", True
    if native.status == "unknown":
        return False, "native_readiness_unknown", True
    if native.status == "not-ready":
        reason = native.reason or "not-ready"
        stale_working = (
            native.reported_state == "working"
            or "recipient reported working" in reason
            or "semantic readiness unavailable" in reason
        )
        return False, reason, stale_working
    if native.status == "ready":
        return True, "ready", False
    return False, f"unsupported_native_status:{native.status}", True


def error_fingerprint(session_id: str, conversation_id: str, phrase: str = CAPACITY_PHRASE) -> str:
    raw = f"{session_id}|{conversation_id}|{phrase}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def next_wait_s(retry_count: int) -> Optional[int]:
    if retry_count >= MAX_RETRIES:
        return None
    return BACKOFF_S[min(retry_count, len(BACKOFF_S) - 1)]


def plan_recovery(obs: Observation, ledger: Optional[MutableMapping[str, Any]] = None) -> Decision:
    """Pure policy. Always dry-run unless explicitly marked deployed (tests keep deployed=False)."""
    fp = error_fingerprint(
        obs.identity.session_id if obs.identity else "",
        obs.conversation_id,
    )
    extras: dict[str, Any] = {"fingerprint": fp, "dry_run": True, "deployed": False}
    if obs.deployed:
        return Decision(
            action="hold_uninstalled",
            reason="candidate_must_remain_uninstalled",
            fingerprint=fp,
            deployed=False,
            extras=extras,
        )
    if not obs.sender_owns_message:
        return Decision(action="block_foreign_sender", reason="must_not_borrow_sender_message", fingerprint=fp, extras=extras)

    blocker = classify_blocker(obs)
    extras["blocker"] = blocker

    if blocker == "stale_identity":
        return Decision(action="block_stale_identity", reason="session_id_or_tag_mismatch", fingerprint=fp, extras=extras)
    if blocker == "draft":
        return Decision(action="block_draft", reason="human_draft_present", fingerprint=fp, extras=extras)
    if blocker == "busy_tools":
        return Decision(action="block_busy", reason="tools_or_working_indicator", fingerprint=fp, extras=extras)
    if blocker == "unknown_composer":
        return Decision(action="block_unknown", reason="composer_unknown", fingerprint=fp, extras=extras)
    if blocker == "menu_or_draft":
        return Decision(action="block_menu", reason="live_menu_or_ambiguous_select", fingerprint=fp, extras=extras)
    if blocker == "quota_unknown":
        return Decision(action="block_quota_unknown", reason="fresh_quota_unknown", fingerprint=fp, extras=extras)
    if blocker == "quota_denied":
        return Decision(action="block_quota", reason="account_or_model_quota", fingerprint=fp, extras=extras)
    if blocker == "historical_quoted":
        return Decision(action="ignore_quoted_history", reason="capacity_phrase_not_in_live_bottom", fingerprint=fp, extras=extras)
    if blocker == "unproven_screen":
        return Decision(
            action="hold_unproven_provenance",
            reason="screen_phrase_is_not_native_error_event",
            fingerprint=fp,
            extras=extras,
        )
    if blocker == "transport":
        return Decision(action="block_transport", reason="do_not_retry_uncertain_mutation", fingerprint=fp, extras=extras)

    if not resource_ok(obs.resources):
        return Decision(action="block_resources", reason="host_floor_unmet_or_unsampled", fingerprint=fp, extras=extras)

    native_ok, native_reason, native_fix = native_allows_retry(obs.native)
    extras["native_reason"] = native_reason

    if blocker == "live_capacity":
        if ledger is not None:
            prev = ledger.get(fp)
            if prev and prev.get("terminal"):
                return Decision(action="dedup_hold", reason="already_capped_or_resolved", fingerprint=fp, retry_count=prev.get("retry_count", 0), extras=extras)
        if obs.last_error_s is None:
            elapsed = FIRST_RETRY_S
        else:
            elapsed = obs.now_s - obs.last_error_s
        wait = next_wait_s(obs.retry_count)
        if wait is None:
            if ledger is not None:
                ledger[fp] = {"retry_count": obs.retry_count, "terminal": True}
            return Decision(
                action="cap_retries",
                reason="max_retries_exhausted",
                retry_count=obs.retry_count,
                fingerprint=fp,
                extras=extras,
            )
        if elapsed < wait:
            return Decision(
                action="wait_capacity",
                reason="first_retry_after_180s_backoff",
                wait_s=int(wait - elapsed) if elapsed >= 0 else wait,
                retry_count=obs.retry_count,
                fingerprint=fp,
                extras=extras,
            )
        if not empty_twice(obs):
            return Decision(action="hold_empty_snapshots", reason="need_two_fresh_empty_bottom_screens", fingerprint=fp, extras=extras)
        if not native_ok:
            return Decision(
                action="need_native_error_event",
                reason=native_reason,
                native_fix_required=True,
                fingerprint=fp,
                extras=extras,
            )
        if ledger is not None:
            ledger[fp] = {"retry_count": obs.retry_count + 1, "terminal": False}
        return Decision(
            action="dry_run_same_conversation_retry",
            reason="capacity_cleared_gates_passed_uninstalled",
            retry_count=obs.retry_count + 1,
            fingerprint=fp,
            extras=extras,
        )

    if not native_ok:
        return Decision(
            action="need_native_error_event" if native_fix else "block_not_ready",
            reason=native_reason,
            native_fix_required=native_fix,
            fingerprint=fp,
            extras=extras,
        )

    if not empty_twice(obs):
        return Decision(action="hold_empty_snapshots", reason="need_two_fresh_empty_bottom_screens", fingerprint=fp, extras=extras)

    return Decision(action="hold_uninstalled", reason="no_live_capacity_and_candidate_not_deployed", fingerprint=fp, extras=extras)


def reset_ledger_entry(ledger: MutableMapping[str, Any], fingerprint: str) -> None:
    ledger.pop(fingerprint, None)


def dump_decision(decision: Decision) -> str:
    payload = {
        "action": decision.action,
        "reason": decision.reason,
        "wait_s": decision.wait_s,
        "retry_count": decision.retry_count,
        "fingerprint": decision.fingerprint,
        "native_fix_required": decision.native_fix_required,
        "would_inject": decision.would_inject,
        "would_switch_model": decision.would_switch_model,
        "deployed": decision.deployed,
        "extras": dict(decision.extras),
    }
    return json.dumps(payload, sort_keys=True)
