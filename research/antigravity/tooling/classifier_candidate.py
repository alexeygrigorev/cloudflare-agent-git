#!/usr/bin/env python3
"""
Supervision Classifier Candidate & Offline Repro Harness
(Codex Principal C1444 / C1448 / C1454)

Provides:
- Baseline classifier reproducing native aplexer Rust behaviour in message_deferred.rs
- Candidate classifier repairing:
  1. Codex status bar false-draft (GPT-*, Context %, weekly limit, workspace paths, warnings)
  2. Dashboard / TUI periodic redraw false contradiction of resting idle state
- Real draft preservation (fails closed on unsubmitted human/agent draft)
- Active work / busy preservation (fails closed on Working (...) / running tasks)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# PromptState and ReadinessVerdict Enums / Models
# =============================================================================

class PromptState:
    EMPTY = "empty"
    DRAFT = "draft"
    BUSY = "busy"
    UNKNOWN = "unknown"

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        self.detail = detail

    @classmethod
    def empty(cls) -> "PromptState":
        return cls(cls.EMPTY)

    @classmethod
    def draft(cls, text: str) -> "PromptState":
        return cls(cls.DRAFT, text)

    @classmethod
    def busy(cls, reason: str = "") -> "PromptState":
        return cls(cls.BUSY, reason)

    @classmethod
    def unknown(cls, reason: str = "") -> "PromptState":
        return cls(cls.UNKNOWN, reason)

    @property
    def is_empty(self) -> bool:
        return self.kind == self.EMPTY

    @property
    def is_draft(self) -> bool:
        return self.kind == self.DRAFT

    @property
    def is_busy(self) -> bool:
        return self.kind == self.BUSY

    @property
    def is_unknown(self) -> bool:
        return self.kind == self.UNKNOWN

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PromptState):
            if self.kind != other.kind:
                return False
            if self.detail and other.detail:
                return self.detail == other.detail
            return True
        if isinstance(other, str):
            return self.kind == other
        return False

    def __repr__(self) -> str:
        if self.detail:
            return f"PromptState.{self.kind.upper()}({self.detail!r})"
        return f"PromptState.{self.kind.upper()}"


class ReadinessVerdict:
    READY = "ready"
    REJECT = "reject"

    def __init__(self, status: str, detail: str = ""):
        self.status = status
        self.detail = detail

    @classmethod
    def ready(cls) -> "ReadinessVerdict":
        return cls(cls.READY)

    @classmethod
    def reject(cls, detail: str) -> "ReadinessVerdict":
        return cls(cls.REJECT, detail)

    @property
    def is_ready(self) -> bool:
        return self.status == self.READY

    @property
    def is_reject(self) -> bool:
        return self.status == self.REJECT

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ReadinessVerdict):
            if self.status != other.status:
                return False
            if self.detail and other.detail:
                return self.detail == other.detail
            return True
        if isinstance(other, str):
            return self.status == other
        return False

    def __repr__(self) -> str:
        if self.detail:
            return f"ReadinessVerdict.{self.status.upper()}({self.detail!r})"
        return f"ReadinessVerdict.{self.status.upper()}"


# =============================================================================
# Baseline Classifier (Faithful reproduction of cloudflare-aplexer-protocol)
# =============================================================================

def is_footer_or_status_baseline(line: str) -> bool:
    """
    Baseline footer filter from message_deferred.rs:156-173.
    Notice it misses: 'GPT-', 'Context', 'weekly', 'warning', directory paths, etc.
    """
    t = line.strip()
    if not t:
        return False
    return (
        "ctrl+" in t
        or "Ctrl+" in t
        or "^C" in t
        or "ESC" in t
        or "commands" in t
        or "shortcuts" in t
        or "Shift+Tab" in t
        or "Normal interactive session requested" in t
        or t.startswith("tokens:")
        or t.startswith("model:")
        or t.startswith("? help")
        or t.startswith("? for shortcuts")
    )


def classify_composer_prompt_baseline(screen_text: str, engine: str) -> PromptState:
    """
    Direct Python port of aplexer classify_composer_prompt from message_deferred.rs:146-347.
    Exhibits the exact defect where Codex status bar is treated as Draft.
    """
    if "[draft in progress]" in screen_text:
        return PromptState.draft("unsubmitted user draft detected")

    all_lines = screen_text.splitlines()
    if not all_lines:
        return PromptState.unknown("screen capture is empty")

    end_idx = len(all_lines)
    while end_idx > 0:
        line = all_lines[end_idx - 1].strip()
        if not line or is_footer_or_status_baseline(line):
            end_idx -= 1
        else:
            break

    if end_idx == 0:
        return PromptState.unknown("screen only contains footers or empty lines")

    active_slice = all_lines[:end_idx]

    if engine == "opencode":
        box_lines = []
        saw_bottom_border = False
        for line in reversed(active_slice):
            trimmed = line.strip()
            if any(trimmed.startswith(c) for c in ("╹", "▀", "└", "╰")):
                saw_bottom_border = True
                continue
            if trimmed.startswith("┃") or trimmed.startswith("│"):
                box_lines.append(line)
            elif any(trimmed.startswith(c) for c in ("┌", "╭", "+")):
                break
            elif box_lines:
                break

        if not box_lines and not saw_bottom_border:
            return PromptState.unknown("opencode composer box not recognized")

        for line in reversed(box_lines):
            trimmed = line.strip()
            inner = trimmed.strip("┃│┌┐└┘─╹▀ ").strip()
            if (
                not inner
                or inner == "Ask a question..."
                or inner == "Type a message..."
                or inner.startswith("Build auto")
                or "ctrl+p" in inner
                or "commands" in inner
            ):
                continue
            return PromptState.draft(inner)
        return PromptState.empty()

    elif engine in ("codex", "zcodex"):
        prompt_idx = None
        for idx in range(len(active_slice) - 1, -1, -1):
            trimmed = active_slice[idx].strip()
            if "›" in trimmed or "❯" in trimmed:
                prompt_idx = idx
                break

        if prompt_idx is None:
            return PromptState.unknown("codex prompt marker not found")

        prompt_line = active_slice[prompt_idx].strip()
        prompt_char = "›" if "›" in prompt_line else "❯"
        pos = prompt_line.find(prompt_char)
        prompt_text = prompt_line[pos + len(prompt_char):].strip()

        if prompt_text and prompt_text != "Ask Codex to do anything":
            return PromptState.draft(prompt_text)

        # Baseline defect: checks subsequent lines, but misses GPT-, Context, weekly limit, etc.
        for line in active_slice[prompt_idx + 1:]:
            trimmed = line.strip()
            if (
                not trimmed
                or is_footer_or_status_baseline(trimmed)
                or "glm-" in trimmed
                or "Normal interactive session" in trimmed
            ):
                continue
            return PromptState.draft(trimmed)

        return PromptState.empty()

    elif engine == "grok":
        prompt_idx = None
        for idx in range(len(active_slice) - 1, -1, -1):
            trimmed = active_slice[idx].strip()
            if "❯" in trimmed:
                prompt_idx = idx
                break

        if prompt_idx is None:
            return PromptState.unknown("grok prompt marker not found")

        prompt_line = active_slice[prompt_idx].strip()
        pos = prompt_line.find("❯")
        after = prompt_line[pos + 1:].strip().rstrip("│").strip()
        if after:
            return PromptState.draft(after)

        for line in active_slice[prompt_idx + 1:]:
            trimmed = line.strip()
            if (
                not trimmed
                or is_footer_or_status_baseline(trimmed)
                or trimmed.startswith("╰")
                or "Grok" in trimmed
                or "always-approve" in trimmed
            ):
                continue
            inner = trimmed.rstrip("│").strip()
            if inner:
                return PromptState.draft(inner)

        return PromptState.empty()

    elif engine == "shell":
        prompt_found = False
        if active_slice:
            last_line = active_slice[-1].strip()
            for prompt_char in ("$", "#", "%", "❯", ">"):
                pos = last_line.rfind(prompt_char)
                if pos != -1:
                    prompt_found = True
                    after = last_line[pos + len(prompt_char):].strip()
                    if after:
                        return PromptState.draft(after)
        if prompt_found:
            return PromptState.empty()
        return PromptState.unknown("shell prompt marker not found")

    else:
        # Generic fallback
        for idx in range(len(active_slice) - 1, -1, -1):
            trimmed = active_slice[idx].strip()
            for prompt_char in ("›", "❯", "$", ">"):
                if prompt_char in trimmed:
                    pos = trimmed.find(prompt_char)
                    after = trimmed[pos + len(prompt_char):].strip()
                    if after:
                        return PromptState.draft(after)
                    return PromptState.empty()
        return PromptState.unknown("generic prompt marker not found")


def idle_was_contradicted_baseline(
    record: Dict[str, Any],
    at: int,
    has_lifecycle_hooks: bool = True
) -> bool:
    """
    Baseline implementation from aplexer::watch::idle_was_contradicted_with_hooks
    (src/watch/state.rs:141-161).
    Exhibits defect where only antigravity was exempted, so dashboard periodic redraws
    cause idle to be falsely contradicted.
    """
    last_activity = record.get("last_activity_ms")
    if last_activity is None:
        return False
    if last_activity <= at + 2000:  # IDLE_ACTIVITY_GRACE_MS
        return False
    if not has_lifecycle_hooks:
        return True
    # Baseline line 160: only antigravity exempted!
    return record.get("engine") != "antigravity"


def evaluate_readiness_verdict_baseline(
    prompt_state: PromptState,
    record: Dict[str, Any],
    now: int
) -> ReadinessVerdict:
    """
    Baseline implementation from message_deferred.rs:73-129.
    """
    if prompt_state.is_draft:
        return ReadinessVerdict.reject(
            f"recipient composer has an unsubmitted draft in progress ({prompt_state.detail}); delivery fail-closed"
        )
    if prompt_state.is_unknown:
        return ReadinessVerdict.reject(
            f"recipient composer prompt state is unknown ({prompt_state.detail}); delivery fail-closed"
        )

    # State check
    reported = record.get("reported_state")
    if reported == "running":
        return ReadinessVerdict.reject("recipient is running; delivery fail-closed")

    has_hooks = record.get("has_lifecycle_hooks", True)
    at = record.get("reported_state_at_ms")

    if reported == "idle" and at is not None:
        if idle_was_contradicted_baseline(record, at, has_hooks):
            return ReadinessVerdict.reject(
                f"recipient reported idle at {at}ms, but subsequent PTY activity contradicted resting state; delivery fail-closed"
            )

    if reported in ("idle", "waiting"):
        return ReadinessVerdict.ready()

    return ReadinessVerdict.reject("unrecognized resting state; delivery fail-closed")


# =============================================================================
# Candidate Classifier Implementation
# =============================================================================

# Anchored footer patterns across engines (Codex, Grok, OpenCode, Claude, Shell)
# CRITICAL: We NEVER match loose word substrings (e.g. "agents", "Context", "workspace", "~/git/")
# because user prompt drafts frequently contain these exact words!
CODEX_STATUS_MODEL_CONTEXT_RE = re.compile(
    r"^(?:GPT-[\w.-]+|glm-[\w.-]+)\b.*?(?:·\s*Context|\s*Context\s+\d+%\s*(?:left|used)|·.*weekly\s+limit)",
    re.I
)
CODEX_SHORTCUTS_WARNINGS_RE = re.compile(
    r"^(?:\?\s+for shortcuts\b|⚠\s+\d+\s+warning|f2\s+to\s+view\b|Tip:\s+Use\s+/|\(esc to interrupt\))",
    re.I
)
BORDER_DECORATION_RE = re.compile(r"^[\s─━═┌┐└┘│┃╹▀╭╰─┼]+$")
SHORTCUTS_LINE_RE = re.compile(
    r"^(?:Shift\+Tab|Ctrl\+[a-z.]|ctrl\+[a-z]|esc\s+to\s+interrupt|\?\s+help)\b",
    re.I
)
GROK_BOX_BOTTOM_RE = re.compile(
    r"^[╰└][─━═].*?Grok\b",
    re.I
)


def is_footer_or_status_candidate(line: str) -> bool:
    """
    Enhanced, geometrically anchored footer and status bar recognizer.
    Recognizes:
    1. Box borders and decorative separators
    2. Codex / zcodex status bar:
       - Model + Context metrics + weekly limits (GPT-... · Context ... · weekly ...)
       - Shortcuts and warnings (? for shortcuts ... ⚠ 1 warning · f2 to view)
       - Scrollback tips (└ Tip: Use /...)
    3. Grok box bottom border:
       - ╰──── Grok 4.7 (medium) · always-approve ─╯
    4. Claude / Grok / OpenCode / Shell bottom shortcut lines:
       - Shift+Tab:mode │ Ctrl+.:shortcuts
       - ? help · ctrl+c to cancel

    CRITICAL INVARIANT (Codex Principal C1500):
    Loose word substrings (such as 'agents', 'Context', 'workspace', 'tokens', '~/git/')
    MUST NEVER be used to identify footers, as user drafts routinely mention them!
    Any line not matching an anchored status bar format is preserved as an active draft.
    """
    t = line.strip()
    if not t:
        return False

    # 1. Border / box decoration lines
    if BORDER_DECORATION_RE.match(t):
        return True

    # 2. Tip lines
    if re.match(r"^(?:└\s*)?Tip:\s+Use\s+/", t, re.I):
        return True

    # 3. Anchored Codex / zcodex status bar line 1 (Model + Context + Weekly limit)
    if CODEX_STATUS_MODEL_CONTEXT_RE.match(t):
        return True

    # 4. Anchored Codex / zcodex status bar line 2 (Shortcuts, warnings, f2)
    if CODEX_SHORTCUTS_WARNINGS_RE.match(t):
        return True

    # 5. Grok box bottom border
    if GROK_BOX_BOTTOM_RE.match(t):
        return True

    # 6. Shortcuts line (Grok, Claude, OpenCode, Shell)
    if SHORTCUTS_LINE_RE.match(t):
        return True

    # 7. Specific OpenCode footer hints (e.g. bordered bottom hints)
    if t.startswith("Build auto") or t == "Ask a question...":
        return True

    return False


def is_active_busy_screen(screen_text: str, engine: str) -> Optional[str]:
    """
    Determines if screen shows active ongoing execution (busy state).
    Distinguishes active working state from historical scrollback:
    If a resting composer prompt marker (›, ❯, $) or bordered composer appears AFTER
    the 'Working (' line, then 'Working (' was from prior execution.
    If 'Working (' is present without a resting prompt following it, session is BUSY.
    """
    lines = screen_text.splitlines()

    # Find the last occurrence of Working indicator
    last_working_idx = None
    working_match_text = None
    for idx, line in enumerate(lines):
        if re.search(r"•\s*Working\s*\(|Working\s*\(.*esc to interrupt\)|•\s*Running\b", line, re.I):
            last_working_idx = idx
            working_match_text = line.strip()

    # Check for Claude active execution phrases
    if last_working_idx is None:
        for idx, line in enumerate(lines):
            if re.search(r"Claude is thinking|Reading file\.\.\.|Running command\.\.\.", line, re.I):
                last_working_idx = idx
                working_match_text = line.strip()

    if last_working_idx is None:
        return None

    # Check if a resting prompt marker appears on or after last_working_idx
    for idx in range(last_working_idx + 1, len(lines)):
        trimmed = lines[idx].strip()
        # Look for standard prompt markers
        if re.match(r"^\s*[›❯$#%]\s*", trimmed):
            # Prompt appeared after the working indicator!
            return None
        # Look for OpenCode bordered composer bottom
        if any(trimmed.startswith(c) for c in ("╹", "▀", "└", "╰")):
            return None

    return working_match_text or "active ongoing execution"


def classify_composer_prompt_candidate(screen_text: str, engine: str) -> PromptState:
    """
    Repaired composer prompt classifier.
    Correctly recognizes Codex status bar (GPT-*, Context %, weekly limit, warnings),
    Dashboard TUI states, Grok, OpenCode, Claude, and Shell prompts, while strictly
    preserving draft detection (fail-closed on user text) and active work (busy).
    """
    if not screen_text or not screen_text.strip():
        return PromptState.unknown("screen capture is empty")

    all_lines = screen_text.splitlines()

    # 1. Unsubmitted user draft marker
    if "[draft in progress]" in screen_text:
        return PromptState.draft("unsubmitted user draft detected")

    # 2. Choice / feedback menu overlay check (Claude / general modal)
    # CRITICAL: Inspect ONLY the active modal / bottom dialogue lines, NOT historical
    # scrollback (which may contain text like "Earlier report: Select approach 6")!
    bottom_dialogue = "\n".join(all_lines[-10:])
    if re.search(
        r"^(?:How is Claude doing\?|Select an option:|Choose [1-9]:|Choose an option:|Press enter to select)",
        bottom_dialogue,
        re.I | re.M
    ):
        return PromptState.draft("menu or feedback overlay")
        return PromptState.draft("menu or feedback overlay")

    # 3. Active execution / busy check
    busy_reason = is_active_busy_screen(screen_text, engine)
    if busy_reason:
        return PromptState.busy(busy_reason)

    all_lines = screen_text.splitlines()

    # Strip trailing footer lines from screen bottom
    end_idx = len(all_lines)
    while end_idx > 0:
        line = all_lines[end_idx - 1].strip()
        if not line or is_footer_or_status_candidate(line):
            end_idx -= 1
        else:
            break

    if end_idx == 0:
        # Screen contains only footers/status lines
        # Check if a prompt marker was present in those lines
        has_prompt = any("›" in l or "❯" in l or "$" in l for l in all_lines)
        if has_prompt:
            return PromptState.empty()
        return PromptState.unknown("screen only contains footers or empty lines")

    active_slice = all_lines[:end_idx]

    # --- Engine: Codex / zcodex ---
    if engine in ("codex", "zcodex"):
        prompt_idx = None
        for idx in range(len(all_lines) - 1, -1, -1):
            trimmed = all_lines[idx].strip()
            if "›" in trimmed or "❯" in trimmed:
                prompt_idx = idx
                break

        if prompt_idx is None:
            return PromptState.unknown("codex prompt marker not found")

        prompt_line = all_lines[prompt_idx].strip()
        prompt_char = "›" if "›" in prompt_line else "❯"
        pos = prompt_line.find(prompt_char)
        prompt_text = prompt_line[pos + len(prompt_char):].strip()

        # If user typed text on prompt line that isn't placeholder
        if prompt_text and prompt_text != "Ask Codex to do anything":
            return PromptState.draft(prompt_text)

        # Inspect lines following prompt
        for line in all_lines[prompt_idx + 1:]:
            trimmed = line.strip()
            if not trimmed or is_footer_or_status_candidate(trimmed):
                continue
            # Non-empty, non-footer line following prompt is a user draft!
            return PromptState.draft(trimmed)

        return PromptState.empty()

    # --- Engine: OpenCode ---
    elif engine == "opencode":
        box_lines = []
        saw_bottom_border = False
        for line in reversed(active_slice):
            trimmed = line.strip()
            if any(trimmed.startswith(c) for c in ("╹", "▀", "└", "╰")):
                saw_bottom_border = True
                continue
            if trimmed.startswith("┃") or trimmed.startswith("│"):
                box_lines.append(line)
            elif any(trimmed.startswith(c) for c in ("┌", "╭", "+")):
                break
            elif box_lines:
                break

        if not box_lines and not saw_bottom_border:
            return PromptState.unknown("opencode composer box not recognized")

        for line in reversed(box_lines):
            trimmed = line.strip()
            inner = trimmed.strip("┃│┌┐└┘─╹▀ ").strip()
            if (
                not inner
                or inner == "Ask a question..."
                or inner == "Type a message..."
                or inner.startswith("Build auto")
                or "ctrl+p" in inner
                or "commands" in inner
                or is_footer_or_status_candidate(inner)
            ):
                continue
            return PromptState.draft(inner)
        return PromptState.empty()

    # --- Engine: Grok ---
    elif engine == "grok":
        prompt_idx = None
        for idx in range(len(all_lines) - 1, -1, -1):
            trimmed = all_lines[idx].strip()
            if "❯" in trimmed:
                prompt_idx = idx
                break

        if prompt_idx is None:
            return PromptState.unknown("grok prompt marker not found")

        prompt_line = all_lines[prompt_idx].strip()
        pos = prompt_line.find("❯")
        after = prompt_line[pos + 1:].strip().rstrip("│").strip()
        if after:
            return PromptState.draft(after)

        for line in all_lines[prompt_idx + 1:]:
            trimmed = line.strip()
            if not trimmed or is_footer_or_status_candidate(trimmed):
                continue
            inner = trimmed.rstrip("│").strip()
            if inner:
                return PromptState.draft(inner)

        return PromptState.empty()

    # --- Engine: Claude ---
    elif engine == "claude":
        prompt_idx = None
        for idx in range(len(all_lines) - 1, -1, -1):
            trimmed = all_lines[idx].strip()
            if trimmed.startswith("❯") or " ❯" in trimmed:
                prompt_idx = idx
                break

        if prompt_idx is None:
            return PromptState.unknown("claude prompt marker not found")

        prompt_line = all_lines[prompt_idx].strip()
        pos = prompt_line.find("❯")
        after = prompt_line[pos + 1:].strip()
        if after:
            return PromptState.draft(after)

        for line in all_lines[prompt_idx + 1:]:
            trimmed = line.strip()
            if not trimmed or is_footer_or_status_candidate(trimmed):
                continue
            return PromptState.draft(trimmed)

        return PromptState.empty()

    # --- Engine: Dashboard / agent-dashboard ---
    elif engine in ("dashboard", "agent-dashboard"):
        # Dashboard TUI inspection:
        # If active execution / task in progress banner is visible
        if re.search(r"\[Status:\s*RUNNING\]|Running\s+task|Executing\b", screen_text, re.I):
            return PromptState.busy("dashboard active task execution")
        # Check command bar draft if present
        for line in all_lines:
            m = re.match(r"^\s*(?:Command|Input|›|❯):\s*(\S.*)$", line)
            if m:
                cmd_text = m.group(1).strip()
                if cmd_text and not is_footer_or_status_candidate(cmd_text):
                    return PromptState.draft(cmd_text)
        return PromptState.empty()

    # --- Engine: Shell ---
    elif engine == "shell":
        prompt_found = False
        if all_lines:
            for line in reversed(all_lines):
                trimmed = line.strip()
                if not trimmed:
                    continue
                for prompt_char in ("$", "#", "%", "❯", ">"):
                    pos = trimmed.rfind(prompt_char)
                    if pos != -1:
                        prompt_found = True
                        after = trimmed[pos + len(prompt_char):].strip()
                        if after:
                            return PromptState.draft(after)
                        return PromptState.empty()
                if prompt_found:
                    break
        if prompt_found:
            return PromptState.empty()
        return PromptState.unknown("shell prompt marker not found")

    # --- Fallback / Unknown engine ---
    else:
        for idx in range(len(all_lines) - 1, -1, -1):
            trimmed = all_lines[idx].strip()
            for prompt_char in ("›", "❯", "$", ">"):
                if prompt_char in trimmed:
                    pos = trimmed.find(prompt_char)
                    after = trimmed[pos + len(prompt_char):].strip()
                    if after and not is_footer_or_status_candidate(after):
                        return PromptState.draft(after)
                    return PromptState.empty()
        return PromptState.unknown("generic prompt marker not found")


def idle_was_contradicted_candidate(
    record: Dict[str, Any],
    screen_text: Optional[str],
    at: int,
    now: Optional[int] = None
) -> bool:
    """
    Candidate implementation distinguishing harmless TUI redraws / cursor refreshes
    from actual active execution or unsubmitted user drafts.

    Returns:
      True  -> resting state WAS contradicted by genuine workload / draft (reject delivery)
      False -> resting state preserved; PTY activity was harmless TUI redraw (allow delivery)
    """
    last_activity = record.get("last_activity_ms")
    if last_activity is None:
        return False
    if last_activity <= at + 2000:  # IDLE_ACTIVITY_GRACE_MS
        return False

    has_hooks = record.get("has_lifecycle_hooks", True)
    if not has_hooks:
        # Without lifecycle hooks, cannot verify resting state safely
        return True

    engine = record.get("engine", "")

    # When screen_text is provided, verify screen state
    if screen_text is not None:
        p_state = classify_composer_prompt_candidate(screen_text, engine)
        if p_state.is_busy or p_state.is_draft or p_state.is_unknown:
            # PTY activity corresponds to active work or draft -> contradicted!
            return True
        # Composer is empty and screen is not busy -> harmless redraw!
        return False

    # When screen_text is not directly provided:
    # Engines with recognized harmless periodic TUI redraws
    if engine in ("antigravity", "dashboard", "agent-dashboard"):
        return False

    # Other engines without screen evidence fail closed
    return True


def evaluate_readiness_verdict_candidate(
    prompt_state: PromptState,
    record: Dict[str, Any],
    now: int,
    screen_text: Optional[str] = None
) -> ReadinessVerdict:
    """
    Candidate evaluate_readiness_verdict matching repaired Rust logic.
    """
    # 1. Draft protection (strict fail-closed)
    if prompt_state.is_draft:
        return ReadinessVerdict.reject(
            f"recipient composer has an unsubmitted draft in progress ({prompt_state.detail}); delivery fail-closed"
        )

    # 2. Busy screen protection (strict fail-closed)
    if prompt_state.is_busy:
        return ReadinessVerdict.reject(
            f"recipient is actively busy ({prompt_state.detail}); delivery fail-closed"
        )

    # 3. Unknown screen state (strict fail-closed)
    if prompt_state.is_unknown:
        return ReadinessVerdict.reject(
            f"recipient composer prompt state is unknown ({prompt_state.detail}); delivery fail-closed"
        )

    # 4. Active reported running state
    reported = record.get("reported_state")
    if reported == "running":
        return ReadinessVerdict.reject("recipient is running; delivery fail-closed")

    at = record.get("reported_state_at_ms")

    # 5. Contradicted resting state check
    if reported == "idle" and at is not None:
        if idle_was_contradicted_candidate(record, screen_text, at, now):
            return ReadinessVerdict.reject(
                f"recipient reported idle at {at}ms, but subsequent PTY activity contradicted resting state; delivery fail-closed"
            )

    if reported == "waiting" and at is not None:
        engine = record.get("engine", "")
        if engine not in ("antigravity", "dashboard", "agent-dashboard"):
            last_act = record.get("last_activity_ms")
            if last_act and last_act > at + 2000:
                return ReadinessVerdict.reject(
                    f"recipient reported waiting at {at}ms, but subsequent PTY activity occurred at {last_act}ms; resting state contradicted, delivery fail-closed"
                )

    # 6. Authentic fresh resting report
    if reported in ("idle", "waiting"):
        return ReadinessVerdict.ready()

    return ReadinessVerdict.reject("unrecognized resting state; delivery fail-closed")
