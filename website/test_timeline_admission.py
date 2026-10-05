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
    """The generated timeline pages must display admitted notes, pagination controls, and exclude unadmitted/generic text."""
    admitted = [rp for rp in REPORTS if note_info(rp) is not None]
    total_pages = max(1, (len(admitted) + 9) // 10)
    
    html = notes_page(page_num=1, total_pages=total_pages)
    
    # Legend includes approved categories
    assert 'Failure' in html
    assert 'Decision or correction' in html
    assert 'Milestone or result' in html
    assert 'Routine check' not in html

    # Pagination controls appear on page 1
    assert 'tl-pagination' in html
    assert 'Older notes' in html
    assert 'tl-pagination-disabled' in html  # Newer notes disabled on page 1
    
    # Across all paginated pages, every admitted note title and summary appears
    all_pages_html = ''.join(notes_page(page_num=p, total_pages=total_pages) for p in range(1, total_pages + 1))
    for key, (title, summary, kind) in NOTE_TEXT.items():
        assert title in all_pages_html, f"Admitted note '{title}' missing from notes_page"
        assert summary in all_pages_html, f"Admitted summary missing for '{title}'"
    
    # No generic check-in titles in timeline items
    assert 'Orchestrator check-in' not in all_pages_html
    assert 'Remote check \u2014' not in all_pages_html
    assert 'Read the full note for the details' not in all_pages_html
    
    # Visible link text is descriptive, not a raw repository path
    assert 'Read full field note' in all_pages_html
    assert 'research/orchestrator/heartbeat-' not in all_pages_html

def test_notes_page_pagination():
    """Pagination navigation links, bounds, and indicators must be correct across all pages."""
    admitted = [rp for rp in REPORTS if note_info(rp) is not None]
    assert len(admitted) > 10, "Expected more than 10 admitted notes to require pagination"
    total_pages = max(1, (len(admitted) + 9) // 10)
    assert total_pages >= 3

    # Page 1: has Next link, no active Prev link
    p1 = notes_page(page_num=1, total_pages=total_pages)
    assert 'Older notes' in p1
    assert 'page/2/' in p1
    assert 'Newer notes' in p1
    assert 'tl-pagination-disabled' in p1
    assert 'aria-current="page">1</span>' in p1

    # Page 2: has both Prev and Next links
    p2 = notes_page(page_num=2, total_pages=total_pages)
    assert 'Older notes' in p2
    assert 'Newer notes' in p2
    assert 'page/3/' in p2
    assert '/reports/' in p2
    assert 'aria-current="page">2</span>' in p2

    # Page 3: has Prev link, no active Next link
    p3 = notes_page(page_num=total_pages, total_pages=total_pages)
    assert 'Newer notes' in p3
    assert f'page/{total_pages - 1}/' in p3
    assert 'tl-pagination-disabled' in p3
    assert f'aria-current="page">{total_pages}</span>' in p3

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
    """CSS must define styling for all admitted timeline dot kinds and pagination."""
    css = (ROOT / 'website/assets/site.css').read_text()
    assert '.tl-failed' in css
    assert '.tl-decision' in css
    assert '.tl-milestone' in css or '.tl-result' in css
    assert '.tl-pagination' in css
    assert '.tl-pagination-page' in css
