"""Regression tests for field notes timeline admission and quality gates.

Enforces human editorial directive (C1661 / C1664) and QUALITY.md rules:
- Only publish concrete source-backed findings, decisions, failures, or milestones.
- Exclude routine/generic check-ins and heartbeats from the public feed.
- Disallow boilerplate ("Read the full note for the details") and heading lists (" · ").
- Disallow unexplained internal jargon (A01, A10, draft numbers, D1 gates, Root/Bunny).
- Visible link text must be descriptive, not raw repository paths.
"""
from pathlib import Path
import re
import pytest

from website.build import (
    ROOT,
    REPORTS,
    NOTE_TEXT,
    note_info,
    note_stamp,
    notes_page,
    home_page,
)

FORBIDDEN_JARGON = [
    'A01', 'A05', 'A06', 'A10', 'A16',
    'draft 4', 'draft 8', 'draft 9',
    'D1 gate', 'D1 gates',
    'Bunny', 'null separation',
]

def test_unadmitted_heartbeats_return_none():
    """Heartbeat check-in files not explicitly curated with concrete findings return None."""
    unadmitted = [
        ROOT / 'research/orchestrator/heartbeat-20261002T1850.md',
        ROOT / 'research/orchestrator/heartbeat-20261004T1410.md',
        ROOT / 'research/orchestrator/heartbeat-20261004T1340.md',
    ]
    for p in unadmitted:
        if p.exists():
            assert note_info(p) is None, f"{p.name} should not be admitted to the public timeline"

def test_admitted_notes_meet_criteria():
    """All curated notes in NOTE_TEXT must satisfy strict quality and plain-language rules."""
    assert len(NOTE_TEXT) > 0
    for key, (title, summary, kind) in NOTE_TEXT.items():
        # Valid categories
        assert kind in ('decision', 'failed', 'milestone', 'result'), f"{key}: invalid kind '{kind}'"
        
        # Plain-language title
        assert title and len(title) > 10, f"{key}: title too short"
        assert title != 'Orchestrator check-in', f"{key}: generic title prohibited"
        assert not title.startswith('Remote check'), f"{key}: remote check prefix prohibited"
        
        # Actionable summary without boilerplate
        assert summary and len(summary) > 20, f"{key}: summary too short"
        assert 'Read the full note for the details' not in summary, f"{key}: boilerplate summary prohibited"
        assert ' · ' not in summary, f"{key}: heading-list summary prohibited"
        
        # Jargon-free check
        for jargon in FORBIDDEN_JARGON:
            assert jargon not in title, f"{key}: title contains internal jargon '{jargon}'"
            assert jargon not in summary, f"{key}: summary contains internal jargon '{jargon}'"

def test_notes_page_rendering():
    """The generated timeline page must display admitted notes and exclude unadmitted/generic text."""
    html = notes_page()
    
    # Legend includes approved categories
    assert 'Failure' in html
    assert 'Decision or correction' in html
    assert 'Milestone or result' in html
    assert 'Routine check' not in html
    
    # Every admitted note title appears in the timeline
    for key, (title, summary, kind) in NOTE_TEXT.items():
        assert title in html, f"Admitted note '{title}' missing from notes_page"
        assert summary in html, f"Admitted summary missing for '{title}'"
    
    # No generic check-in titles in timeline items
    assert 'Orchestrator check-in' not in html
    assert 'Remote check \u2014' not in html
    assert 'Read the full note for the details' not in html
    
    # Visible link text is descriptive, not a raw repository path
    assert 'Read full field note' in html
    assert 'research/orchestrator/heartbeat-' not in html

def test_home_page_field_notes_section():
    """The home page field notes column must show only admitted notes and describe findings, not checks."""
    html = home_page()
    
    # Column subtext describes findings, not checks
    assert 'Tested findings, decisions, and failures from the experiment' in html
    assert 'Checks by the coordinating agent' not in html
    
    # Admitted notes appear
    admitted = [rp for rp in REPORTS if note_info(rp) is not None]
    for rp in admitted[:4]:
        title = note_info(rp)[0]
        assert title in html, f"Home page missing newest field note '{title}'"

def test_site_css_supports_all_timeline_kinds():
    """CSS must define styling for all admitted timeline dot kinds."""
    css = (ROOT / 'website/assets/site.css').read_text()
    assert '.tl-failed' in css
    assert '.tl-decision' in css
    assert '.tl-milestone' in css or '.tl-result' in css
