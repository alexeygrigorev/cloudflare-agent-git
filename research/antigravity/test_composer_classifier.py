#!/usr/bin/env python3
"""Offline unit and fixture tests for the OpenCode and Shell/Codex composer classifier."""
import os
import sys

# Import single source of truth from continuation_trial_runner per Muse R22 verdict
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(current_dir))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from research.antigravity.continuation_trial_runner import composer_classifier


def main():
    fixtures_dir = os.path.join(current_dir, "fixtures")
    empty_fixture = os.path.join(fixtures_dir, "opencode_screen_empty.txt")
    draft_fixture = os.path.join(fixtures_dir, "opencode_screen_draft.txt")
    ml_draft_fixture = os.path.join(fixtures_dir, "opencode_screen_multiline_draft.txt")
    busy_fixture = os.path.join(fixtures_dir, "opencode_screen_busy.txt")

    with open(empty_fixture) as f:
        s_empty = f.read()
    with open(draft_fixture) as f:
        s_draft = f.read()
    with open(ml_draft_fixture) as f:
        s_ml_draft = f.read()
    with open(busy_fixture) as f:
        s_busy = f.read()

    res_empty = composer_classifier(s_empty)
    res_draft = composer_classifier(s_draft)
    res_ml_draft = composer_classifier(s_ml_draft)
    res_busy = composer_classifier(s_busy)

    print(f"Empty Fixture:           {res_empty}")
    print(f"Single-line Draft:       {res_draft}")
    print(f"Multiline Draft Fixture: {res_ml_draft}")
    print(f"Busy Fixture:            {res_busy}")

    assert res_empty == "empty", f"Expected empty, got {res_empty}"
    assert res_draft == "draft", f"Expected draft, got {res_draft}"
    assert res_ml_draft == "draft", f"Expected draft, got {res_ml_draft}"
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

    print("\nALL COMPOSER CLASSIFIER TESTS PASSED (10/10 checks).")


if __name__ == "__main__":
    main()
