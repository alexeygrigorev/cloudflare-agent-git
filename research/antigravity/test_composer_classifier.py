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
    bottom_indices = [i for i, l in enumerate(lines) if "╹" in l or re.search(r"^\s*╹", l)]
    
    composer_lines = []
    if bottom_indices:
        b_idx = bottom_indices[-1]
        idx = b_idx - 1
        while idx >= 0:
            l = lines[idx]
            if re.match(r"^\s*┃", l):
                composer_lines.insert(0, l)
                idx -= 1
            elif not l.strip():
                idx -= 1
            elif "▣" in l:
                break
            else:
                break
    else:
        build_indices = [i for i, l in enumerate(lines) if "▣" in l and "build" in l.lower()]
        if build_indices:
            start_idx = build_indices[-1]
            composer_lines = [l for l in lines[start_idx:] if re.match(r"^\s*┃", l)]
        elif "ctrl+p" in s_lower:
            all_pipe = [l for l in lines if re.match(r"^\s*┃", l)]
            if all_pipe:
                composer_lines = all_pipe[-5:]

    if "ctrl+p" in s_lower and composer_lines:
        draft_content = []
        for l in composer_lines:
            cleaned = re.sub(r"^\s*┃\s*", "", l).strip()
            if not cleaned:
                continue
            if re.match(r"^Build (?:auto|prompt)(?:\s*·.*)?$", cleaned, re.I):
                continue
            draft_content.append(cleaned)
        
        if draft_content:
            return "draft"
        return "empty"

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

    # Codex C-1129 Multi-line Draft Tests:
    # Case A: User draft on line 1, placeholder on line 4
    multiline_draft_placeholder = """
     ▣  Build · Space Bunny Free
  ┃  first line of user draft
  ┃  second line of user draft
  ┃
  ┃  Build auto · Space Bunny Free OpenCode Go
  ╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
   /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands
"""
    res_ml1 = composer_classifier(multiline_draft_placeholder)
    print(f"Multiline Draft + Placeholder below: {res_ml1}")
    assert res_ml1 == "draft", f"Expected draft, got {res_ml1}"

    # Case B: User draft on line 2, blank lines around it
    multiline_draft_blanks = """
     ▣  Build · Space Bunny Free
  ┃
  ┃  user command in progress
  ┃
  ┃
  ╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
   /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands
"""
    res_ml2 = composer_classifier(multiline_draft_blanks)
    print(f"Multiline Draft + Blanks around: {res_ml2}")
    assert res_ml2 == "draft", f"Expected draft, got {res_ml2}"

    # Case C: All empty lines inside composer box
    all_empty_box = """
     ▣  Build · Space Bunny Free
  ┃
  ┃
  ┃
  ┃
  ╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
   /home/alexey/git/cloudflare-agent-git           83.5K (8%)  ctrl+p commands
"""
    res_empty_box = composer_classifier(all_empty_box)
    print(f"All Empty Composer Box: {res_empty_box}")
    assert res_empty_box == "empty", f"Expected empty, got {res_empty_box}"

    # Shell prompt tests
    shell_empty = "› \n"
    shell_draft = "› git status\n"
    assert composer_classifier(shell_empty) == "empty"
    assert composer_classifier(shell_draft) == "draft"

    # Loading screen test
    loading = "Connecting to language server...\n"
    assert composer_classifier(loading) == "unknown"

    print("\nALL COMPOSER CLASSIFIER TESTS PASSED (9/9 checks).")


if __name__ == "__main__":
    main()
