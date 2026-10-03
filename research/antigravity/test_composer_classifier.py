#!/usr/bin/env python3
"""Offline unit and fixture tests for the OpenCode and Shell/Codex composer classifier."""
import os
import re
import sys

def composer_classifier(screen, tag="continuation-receiver"):
    """Full empty composer classification for OpenCode bordered UI and shell/codex prompts."""
    if not screen:
        return "unknown"
    s_lower = screen.lower()

    # 1. Busy check: if model is actively generating or executing a tool with interrupt enabled
    if "working (" in s_lower or "esc to interrupt" in s_lower or "esc interrupt" in s_lower:
        return "busy"

    # 2. Check for menu / choice overlay
    if re.search(r"How is Claude doing|Choose|Select|feedback", screen, re.I):
        return "menu-or-draft"

    # 3. OpenCode Bordered Composer Detection
    lines = screen.splitlines()
    opencode_input_lines = [l for l in lines if re.match(r"^\s*┃", l)]
    if "ctrl+p" in s_lower and opencode_input_lines:
        last_line = opencode_input_lines[-1]
        cleaned = re.sub(r"^\s*┃\s*", "", last_line).strip()
        if not cleaned or re.match(r"^Build (?:auto|prompt)(?:\s*·.*)?$", cleaned, re.I):
            return "empty"
        return "draft"

    # 4. Standard shell / codex › or ❯ prompt check
    starts = [(i, re.sub(r"^\s*[›❯]\s*", "", line).strip())
              for i, line in enumerate(lines) if re.match(r"^\s*[›❯]", line)]
    if starts:
        index, content = starts[-1]
        if any(line.strip() and not re.match(r"^\s*[─━]|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|usage|workspace|warning)", line)
               for line in lines[index + 1:]):
            return "unknown"
        if content and not (tag == "codex-principal" and content == "Ask Codex to do anything"):
            return "draft"
        return "empty"

    return "unknown"


def main():
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    empty_fixture = os.path.join(fixtures_dir, "opencode_screen_empty.txt")
    draft_fixture = os.path.join(fixtures_dir, "opencode_screen_draft.txt")
    busy_fixture = os.path.join(fixtures_dir, "opencode_screen_busy.txt")

    with open(empty_fixture) as f:
        s_empty = f.read()
    with open(draft_fixture) as f:
        s_draft = f.read()
    with open(busy_fixture) as f:
        s_busy = f.read()

    res_empty = composer_classifier(s_empty)
    res_draft = composer_classifier(s_draft)
    res_busy = composer_classifier(s_busy)

    print(f"Empty Fixture:  {res_empty}")
    print(f"Draft Fixture:  {res_draft}")
    print(f"Busy Fixture:   {res_busy}")

    assert res_empty == "empty", f"Expected empty, got {res_empty}"
    assert res_draft == "draft", f"Expected draft, got {res_draft}"
    assert res_busy == "busy", f"Expected busy, got {res_busy}"

    # Shell prompt tests
    shell_empty = "› \n"
    shell_draft = "› git status\n"
    assert composer_classifier(shell_empty) == "empty"
    assert composer_classifier(shell_draft) == "draft"

    # Loading screen test
    loading = "Connecting to language server...\n"
    assert composer_classifier(loading) == "unknown"

    print("\nALL COMPOSER CLASSIFIER TESTS PASSED (6/6 checks).")


if __name__ == "__main__":
    main()
