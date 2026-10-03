#!/usr/bin/env python3
"""Build the public journal. Python standard library only; no private inputs.

Layout and type follow the Claude Design reference (design-reference file
Agent-Git-Lab.dc.html; the site is now named Agent Branches): one 1180 px content column for header, main, signup and footer,
mono cobalt eyebrows, Georgia display type, 2 px ink section rules and 1 px hairline rows.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASE = '/cloudflare-agent-git'
REPO = 'https://github.com/alexeygrigorev/cloudflare-agent-git'
ORIGIN = 'https://alexeygrigorev.com'
E = html.escape
SIGNUP = json.loads((ROOT/'website/signup.json').read_text())
PROJECTS = json.loads((ROOT/'website/projects.json').read_text())
ACTIVE_COUNT = sum(not p['status'].lower().startswith('parked') for p in PROJECTS)
OPEN_PLACES = max(0, 6 - ACTIVE_COUNT)
PARKED_COUNT = len(PROJECTS) - ACTIVE_COUNT
ASSETS = ROOT/'website/assets'
ARROW = '<span class="arr" aria-hidden="true">\u2192</span>'
EXT = '<span class="arr" aria-hidden="true">\u2197</span>'
BACK = '<span class="arr-l" aria-hidden="true">\u2190</span>'

def _mark(shape):
    return (ASSETS/'marks'/(shape+'.svg')).read_text().strip()
SHAPE = {'A01': 'circle', 'A16': 'square', 'A05': 'triangle', 'A06': 'diamond', 'A10': 'pentagon', 'SLOT6': 'star'}
CARD_MARKS = {k: _mark(v) for k, v in SHAPE.items()}
LOGO_SVG = CARD_MARKS['A01'].replace('aria-label="circle"', 'aria-hidden="true"').replace('role="img" ', '')

def smark(kind, size=16):
    """Status vocabulary from the reference: shape plus a text label, never colour alone."""
    s = size; c = s/2; r = s/2-2
    f = lambda v: ('%.2f' % v).rstrip('0').rstrip('.')
    g = {
        'done': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r)}" fill="#1C2027"/>',
        'supports': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r)}" fill="#1C2027"/>',
        'pending': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r-.5)}" fill="none" stroke="#2455ED" stroke-width="2.4"/>',
        'failed': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r)}" fill="#EF7134"/><path d="M{f(c-r*.45)} {f(c-r*.45)} L{f(c+r*.45)} {f(c+r*.45)} M{f(c+r*.45)} {f(c-r*.45)} L{f(c-r*.45)} {f(c+r*.45)}" stroke="#1C2027" stroke-width="2" stroke-linecap="round"/>',
        'withdrawn': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r-.5)}" fill="none" stroke="#1C2027" stroke-width="2"/><path d="M{f(c-r)} {f(c+r)} L{f(c+r)} {f(c-r)}" stroke="#1C2027" stroke-width="2"/>',
        'open': f'<circle cx="{f(c)}" cy="{f(c)}" r="{f(r-.5)}" fill="none" stroke="#1C2027" stroke-width="1.8" stroke-dasharray="2.5 2.5"/>',
        'unknown': f'<rect x="2" y="2" width="{s-4}" height="{s-4}" fill="none" stroke="#1C2027" stroke-width="1.8" stroke-dasharray="2.5 2.5"/><circle cx="{f(c)}" cy="{f(c)}" r="1.8" fill="#1C2027"/>',
        'against': f'<rect x="2" y="2" width="{s-4}" height="{s-4}" fill="#EF7134"/>',
        'limits': f'<polygon points="{f(c)},2 {s-2},{s-2} 2,{s-2}" fill="none" stroke="#2455ED" stroke-width="2"/>',
    }[kind]
    return f'<svg width="{s}" height="{s}" viewBox="0 0 {s} {s}" aria-hidden="true" focusable="false">{g}</svg>'

def status_kind(proj):
    s = str(proj.get('status', '')).lower()
    if 'withdrawn' in s or 'parked' in s:
        return 'withdrawn'
    return 'pending'

BUILD_TIME = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
BUILD_SHA = os.environ.get('GITHUB_SHA', '')
if not re.fullmatch(r'[0-9a-f]{40}', BUILD_SHA):
    try:
        BUILD_SHA = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=5).strip()
    except (subprocess.SubprocessError, OSError):
        BUILD_SHA = ''

def git_last(path):
    try:
        out = subprocess.check_output(['git', 'log', '-1', '--format=%h %cI', '--', str(path)], cwd=ROOT, text=True, timeout=5).strip()
        sha, stamp = out.split(' ', 1)
        return sha, datetime.fromisoformat(stamp).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except (subprocess.SubprocessError, OSError, ValueError):
        return '', ''

def public_source(path):
    return REPO + ('/tree/main/' if str(path).endswith('/') else '/blob/main/') + quote(str(path), safe='/')

def exists(rel):
    return (ROOT/rel.rstrip('/')).exists()

def safe_url(url, source=None):
    url = html.unescape(url.strip())
    if url.startswith('../../assets/'):
        return BASE + '/assets/' + url.split('../../assets/', 1)[1]
    if url.startswith('/cloudflare-agent-git/') or url.startswith('#'):
        return url
    parsed = urlparse(url)
    if parsed.scheme:
        return url if parsed.scheme in ('https', 'http', 'mailto') else '#'
    if source:
        path = (source.parent / url).resolve()
        try:
            rel = path.relative_to(ROOT)
            if rel.parts[0] in ('research', 'experiment', 'coordination', 'website'):
                return public_source(rel)
        except ValueError:
            pass
    return '#'

def image_markup(alt, url, source=None):
    image_url = safe_url(url, source)
    portrait = image_url == BASE+'/assets/team-workflow.svg'
    if portrait:
        # The landscape diagram's labels drop below 12 px inside the 640 px article measure;
        # the portrait version keeps every label at 12 px or more at every width.
        image_url = BASE+'/assets/team-workflow-mobile.svg'
    image = '<img loading="lazy" src="'+E(image_url, quote=True)+'" alt="'+E(alt, quote=True)+'">'
    return '<figure'+(' class="portrait-fig"' if portrait else '')+'>'+image+'<figcaption>'+E(alt)+'</figcaption></figure>'

def inline(text, source=None):
    tokens = []
    def token(value):
        tokens.append(value)
        return '\x00' + str(len(tokens)-1) + '\x00'
    text = re.sub(r'`([^`]+)`', lambda m: token('<code>'+E(m[1])+'</code>'), text)
    text = re.sub(r'!\[([^\]]*)\]\(([^\s)]+)\)', lambda m: token(image_markup(m[1], m[2], source)), text)
    text = re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', lambda m: token('<a href="'+E(safe_url(m[2], source), quote=True)+'">'+E(m[1])+'</a>'), text)
    text = E(text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], text)

def markdown(text, source=None):
    """Small Markdown subset. The document title (#) is rendered by the page, so ## maps to h2."""
    out, paragraph, listing, code = [], [], None, None
    def flush():
        if paragraph:
            rendered = inline(' '.join(paragraph), source)
            out.append(rendered if rendered.startswith('<figure>') and rendered.endswith('</figure>') else '<p>'+rendered+'</p>')
            paragraph.clear()
    def close_list():
        nonlocal listing
        if listing:
            out.append('</'+listing+'>')
            listing = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith('```'):
            flush(); close_list()
            if code is None:
                code = []
            else:
                out.append('<pre><code>'+E('\n'.join(code))+'</code></pre>')
                code = None
            continue
        if code is not None:
            code.append(line); continue
        if not line.strip():
            flush(); close_list(); continue
        if line.startswith('|') and i < len(lines) and re.match(r'^\|[\s:|\-]+\|?$', lines[i]):
            flush(); close_list()
            headers = [x.strip() for x in line.strip('|').split('|')]
            i += 1
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([x.strip() for x in lines[i].strip('|').split('|')]); i += 1
            out.append('<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+inline(x, source)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x, source)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.*)', line)
        bullet = re.match(r'^\s*(?:[-*]|\d+\.)\s+(.*)', line)
        if heading:
            flush(); close_list()
            level = min(6, max(2, len(heading[1])))
            out.append(f'<h{level}>'+inline(tidy(heading[2]), source)+f'</h{level}>')
        elif bullet:
            flush()
            kind = 'ol' if re.match(r'^\s*\d+\.', line) else 'ul'
            if listing != kind:
                close_list(); listing = kind; out.append('<'+kind+'>')
            out.append('<li>'+inline(bullet[1], source)+'</li>')
        elif line.startswith('> '):
            flush(); close_list(); out.append('<blockquote>'+inline(line[2:], source)+'</blockquote>')
        elif re.fullmatch(r'\s*[-*_]{3,}\s*', line):
            flush(); close_list(); out.append('<hr>')
        else:
            close_list(); paragraph.append(line.strip())
    flush(); close_list()
    if code is not None:
        out.append('<pre><code>'+E('\n'.join(code))+'</code></pre>')
    return '\n'.join(out)

def tidy(text):
    """Restore spaces lost around dates and times in some note headings ("3 October2026,07:41")."""
    text = re.sub(r'([A-Za-z])(\d{4})\b', r'\1 \2', text)
    text = re.sub(r'([A-Za-z])(\d{1,2}:\d\d)', r'\1 \2', text)
    text = re.sub(r'(\d\d:\d\d)(UTC|Berlin)', r'\1 \2', text)
    text = re.sub(r',(\d{1,2}:\d\d)', r', \1', text)
    text = re.sub(r'\u2014(\S)', '\u2014 \\1', text)
    return text

# ---------------------------------------------------------------- shared data
def load_daily():
    daily = []
    for meta in sorted((ROOT/'website/content/daily').glob('*.json'), reverse=True):
        data = json.loads(meta.read_text())
        if data.get('published') is not True:
            continue
        data['path'] = meta.with_suffix('.md')
        data['route'] = 'daily/'+meta.stem+'/'
        data.setdefault('date', meta.stem)
        daily.append(data)
    return daily
DAILY = load_daily()
REPORTS = sorted((ROOT/'research/orchestrator').glob('heartbeat-*.md'), reverse=True)

def parse_utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

def utc_text(value):
    stamp = parse_utc(value)
    return stamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if stamp else str(value)

def readable_cutoff(value):
    stamp = parse_utc(value)
    if not stamp:
        return str(value)
    utc = stamp.astimezone(timezone.utc).strftime('%d %b %Y, %H:%M UTC')
    berlin = stamp.astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M %Z, Europe/Berlin')
    return utc+' / '+berlin

def note_stamp(path):
    return datetime.strptime(path.stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').replace(tzinfo=timezone.utc)

LATEST = DAILY[0] if DAILY else None
LATEST_CUTOFF = parse_utc(LATEST.get('source_cutoff')) if LATEST else None
LATEST_NOTE = note_stamp(REPORTS[0]) if REPORTS else None

# Field-note headlines and summaries. Four come from the design reference; the newer three
# are written from the notes themselves. Every other note uses its own section headings.
NOTE_TEXT = {
    '20261003T0541': ('Task handoff idea parked after plain Git recovery worked; a misreading is withdrawn', 'Both principals provisionally parked A10 in draft 9 after ordinary Git and file recovery succeeded in two actual tasks. Root withdrew its 05:11 reading of restored Bunny output as new execution.', 'decision'),
    '20261003T0511': ('A new shortlist draft parks the disk-saving idea; a monitoring fix is verified', 'Draft 8 retains A01, A05, A06 and A10, parks A16 and leaves two product places open. A scoped supervisor repair passed 35 tests, rerun by root.', 'decision'),
    '20261003T0441': ('Disk-saving idea parked; a change story left the review verdict unchanged', 'A16 was parked after three failed D1 gates. A06\u2019s first real review kept the same APPROVE verdict with and without the story card. Exactly-once task execution remains unproved.', 'decision'),
    '20261003T0224': ('A repair test failed; free disk dropped 16 GiB', 'Expected one outer side effect, observed zero. Root free disk 132 \u2192 116 GiB; shared Rust target measured at 39.65 GiB. Nothing killed or deleted; compilation held.', 'failed'),
    '20261002T2124': ('The conflict-warning idea loses its lead', 'Equal-policy actual pair shows null separation. Claude proposes retain-conditional, lose-primary; Codex accepts the correction.', 'decision'),
    '20261002T2024': ('The coordinating agent corrects the disk number', 'The ~80% dependency share mixed a per-directory sum with a physical union. Corrected to 62.1%.', 'decision'),
    '20261002T1950': ('Private test site idea folded into the collision radar; sixth place reopens', 'Codex draft 4 folds runtime verification into A01 after Bunny\u2019s selection challenge.', 'decision'),
}

def note_info(path):
    key = path.stem.removeprefix('heartbeat-')
    if key in NOTE_TEXT:
        title, summary, kind = NOTE_TEXT[key]
        return title, summary, kind
    heads = [tidy(h).strip() for h in re.findall(r'^##\s+(.+)$', path.read_text(), re.MULTILINE)]
    title = heads[0] if heads else 'Orchestrator check-in'
    summary = ' \u00b7 '.join(heads[1:]) if len(heads) > 1 else 'Read the full note for the details.'
    return title, summary, 'routine'

def note_time(path):
    return note_stamp(path).strftime('%H:%M UTC')

def note_day(path):
    return note_stamp(path).strftime('%a %-d %b').upper()

def report_title(path):
    heading = re.search(r'^#\s+(.+)$', path.read_text(), re.MULTILINE)
    return tidy(heading[1]) if heading else 'Orchestrator check-in'

# ---------------------------------------------------------------- page frame
NAV = [('Journal', ''), ('Hypotheses', 'projects/'), ('Checklist', 'checklist/'), ('Daily report', 'daily/'), ('Field notes', 'reports/'), ('Library', 'research/'), ('About', 'experiment/')]

def nav_html(route):
    out = []
    for label, path in NAV:
        current = (route == '') if path == '' else route.startswith(path)
        href = BASE+'/'+(LATEST['route'] if path == 'daily/' and LATEST else path)
        out.append('<a '+('aria-current="page" ' if current else '')+'href="'+href+'">'+label+'</a>')
    return ''.join(out)

def long_date(value):
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime('%-d %B %Y')
    except ValueError:
        return str(value)

def intro(title, deck, extra=''):
    return '<header class="page-intro"><h1>'+E(title)+'</h1>'+('<p class="intro-deck">'+deck+'</p>' if deck else '')+extra+'</header>'

def signup_section(dedicated=False):
    enabled = SIGNUP.get('enabled') is True
    endpoint = str(SIGNUP.get('relay_list', ''))
    if endpoint != 'https://relay.datatalks.club/api/public/lists/agent-git-lab':
        raise ValueError('Unexpected Relay public-list endpoint; review configuration before publishing.')
    unavailable = '<p class="signup-setup-note">Email signup is being connected. You can follow the <a href="'+BASE+'/feed.xml">RSS feed</a> meanwhile.</p>' if not enabled else ''
    disabled = '' if enabled else ' disabled'
    return ('<section class="email-signup'+(' dedicated-signup' if dedicated else '')+'" aria-labelledby="signup-title"><div class="signup-copy"><h2 id="signup-title">Get experiment updates</h2><p>New findings, failures, and what we build next. Confirm your address before joining the list.</p><p class="signup-detail">Sign up for occasional experiment updates. Read the daily reports in the journal.</p></div>'
            '<form id="journal-signup" class="signup-form" action="javascript:void(0);" onsubmit="return false;" data-relay-list="'+E(endpoint, quote=True)+'" data-enabled="'+('true' if enabled else 'false')+'" aria-busy="false"><label for="signup-email">Your email address</label><input id="signup-email" name="email" type="email" autocomplete="email" inputmode="email" maxlength="254" placeholder="you@example.com" required'+disabled+'><label class="signup-consent" for="signup-consent"><input id="signup-consent" name="consent" type="checkbox" required'+disabled+'><span>I agree to receive occasional Agent Branches experiment updates by email.</span></label><div class="signup-controls"><button id="signup-submit" class="button" type="submit"'+disabled+'>Keep me posted'+ARROW+'</button></div><p class="signup-detail">Your address is processed by DataTalks.Club Relay for this list. Unsubscribe through the link in an update email. <a href="'+BASE+'/privacy/">Email privacy</a>.</p>'+unavailable+'<p id="signup-status" class="signup-status" role="status" aria-live="polite" aria-atomic="true" tabindex="-1" hidden></p><noscript><p class="signup-status is-error" style="display:block;margin-top:12px">Email signup requires JavaScript for the confirmation flow. You can follow the <a href="'+BASE+'/feed.xml">RSS feed</a> without JavaScript.</p></noscript></form></section>')

def footer_html():
    # Build provenance stays out of the visible page; it is kept as an HTML comment for checks.
    stamp = 'built from main @ '+(BUILD_SHA or 'unknown')+' \u00b7 site built '+BUILD_TIME
    if LATEST_CUTOFF:
        stamp += ' \u00b7 evidence up to '+LATEST_CUTOFF.strftime('%Y-%m-%d %H:%M')+' UTC'
    if LATEST_NOTE:
        stamp += ' \u00b7 latest field note '+LATEST_NOTE.strftime('%Y-%m-%d %H:%M')+' UTC'
    return ('<footer class="site-footer"><!-- '+E(stamp)+' --><div class="footer-inner"><nav class="footer-links" aria-label="Footer">'
            '<a href="'+REPO+'">GitHub repository'+EXT+'</a><a href="'+BASE+'/research/">Research library</a><a href="'+BASE+'/feed.xml">RSS feed</a><a href="'+BASE+'/privacy/">Email privacy</a></nav></div></footer>')

GRAIN = '<div class="grain" aria-hidden="true"></div>'

def page(title, body, route='', description='A public experiment in Git, coding agents, and the work between them.', kind='wide'):
    header = ('<header class="site-header"><div class="header-top"><a class="header-brand" href="'+BASE+'/"><span class="header-logo" aria-hidden="true">'+LOGO_SVG+'</span><span class="header-title">Agent Branches</span></a>'
              '</div><nav class="site-nav" aria-label="Main navigation">'+nav_html(route)+'</nav></header>')
    signup = '' if route == 'subscribe/' else '<div class="column signup-wrap">'+signup_section()+'</div>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+' \u00b7 Agent Branches</title><meta name="description" content="'+E(description, quote=True)+'"><meta name="theme-color" content="#2455ed">'+('<meta name="build-commit" content="'+BUILD_SHA+'">' if BUILD_SHA else '')+'<link rel="stylesheet" href="'+BASE+'/assets/site.css"><link rel="alternate" type="application/rss+xml" title="Agent Branches journal" href="'+BASE+'/feed.xml"><link rel="canonical" href="'+ORIGIN+BASE+'/'+route+'"><script src="'+BASE+'/assets/signup.js" defer></script></head>'
            '<body>'+GRAIN+'<div class="frame"><a class="skip" href="#main">Skip to content</a>'
            +header+'<main id="main" class="page page-'+kind+'">'+body+'</main>'+signup+footer_html()+'</div></body></html>')

# ---------------------------------------------------------------- components
def card(p, with_next=False):
    tag = 'PROVISIONAL'
    nxt = ''
    if with_next:
        first = re.split(r'(?<=[.;])\s', p['test'].strip(), maxsplit=1)[0]
        nxt = '<p class="card-next">Next test: '+E(first)+'</p>'
    return ('<a class="hyp-card" href="'+BASE+'/projects/'+p['slug']+'/"><span class="card-top"><span class="card-mark" aria-hidden="true">'+CARD_MARKS.get(p['id'], CARD_MARKS['A01'])+'</span><span class="badge">'+tag+'</span></span>'
            '<span class="card-head"><span class="card-name">'+E(p['name'])+'</span></span>'
            '<span class="status-line">'+smark(status_kind(p))+'<span>'+E(p['status'])+'</span></span><span class="card-short">'+E(p['summary'])+'</span>'+nxt+'</a>')

def open_card(with_next=False):
    return ('<div class="hyp-card is-open"><span class="card-top"><span class="card-mark" aria-hidden="true">'+CARD_MARKS['SLOT6']+'</span><span class="badge">OPEN</span></span>'
            '<span class="card-head"><span class="card-name">Open place \u2014 nothing selected</span></span>'
            '<span class="status-line">'+smark('open')+'<span>Reopened \u00b7 no candidate approved</span></span><span class="card-short">The private test site idea was folded into the collision radar. Nothing has earned the sixth place yet.</span>'+('<p class="card-next">Next test: Open</p>' if with_next else '')+'</div>')

def cards(with_next=False):
    return '<div class="card-grid">'+''.join(card(p, with_next) for p in PROJECTS)+open_card(with_next)+'</div>'

def num_html(n):
    m = re.fullmatch(r'([\d.,/]+)\s*(\D.*)?', n)
    if m and m[2]:
        return E(m[1])+'<small>'+E(m[2])+'</small>'
    return E(n)

PAIN_STATS = [('472', 'linked worktrees'), ('25', 'repositories'), ('111.7', 'GiB on disk'), ('62.1%', 'dependencies and build output')]

# Extra per-project reference detail (who it is for, source files). Facts about current
# status come from projects.json only; these lists are filtered to files that exist.
PROJECT_EXTRA = {
    'A01': ('an operator running 3\u201320 different agent tasks at once.', ['research/shortlist-6.md', 'research/grok/a01-fair-results.md', 'research/codex/a01-live-independent-replay.json', 'research/codex/local-validation.md', 'research/debate/codex-a01-pilot-review.md']),
    'A16': ('Alexey, and operators constrained by local disk.', ['research/claude/u7-real-worktree-measurement.md', 'research/orchestrator/worktree-storage-pain.md', 'research/codex/storage-validation.md', 'research/codex/package-storage-validation.md', 'research/codex/retained-lanes-review-2324.md', 'research/antigravity/r8-physical-storage-isolation.md']),
    'A05': ('people who already run best-of-N agent attempts.', ['research/shortlist-6.md', 'research/claude/hn-evidence.md', 'research/claude/workflows-competitors.md']),
    'A06': ('an accountable reviewer on a team that accepts AI-written changes.', ['research/claude/maintainer-review-evidence.md', 'research/grok/a06-adoption-decision.md', 'research/grok/a06-evidence-card-plan.md', 'research/shortlist-6.md']),
    'A10': ('an operator restarting or replacing an agent mid-task.', ['research/shortlist-6.md', 'research/codex/evidence.md', 'research/claude/workflows-competitors.md', 'research/codex/pro-integration-round-1.md']),
}
# Earlier evidence rows with their stance, from the design reference's research summary.
PROJECT_EVIDENCE = {
    'A01': [('supports', 'Our clean-merge fixture reproduces individually green, combined-red behaviour. Synthetic only.', 'research/codex/local-validation.md'),
            ('limits', 'The retrospective study (E-X018) is textual and observational. It says nothing about live uptake.', 'research/shortlist-6.md'),
            ('against', 'Equal-policy pair with actual concurrent agents (D-G25): compatible first commits in both arms, zero source repairs, no notices. Null separation.', 'research/grok/a01-fair-results.md')],
    'A16': [('supports', 'Read-only scan of the real host: 111.7 GiB physical union; Python .venv 57.3 GiB across 215 dirs, sharing nothing.', 'research/claude/u7-real-worktree-measurement.md'),
            ('against', '264 worktrees sit on commits already in origin/main. Cleanup, not a platform, may be the bigger lever.', 'research/claude/u7-real-worktree-measurement.md'),
            ('against', 'An ordinary pnpm union is already ~49.97% below summed individual trees. Strong incumbent baseline.', 'research/codex/package-storage-validation.md')],
    'A05': [('supports', 'Best-of-N integration gap reported (E-C320, E-C323) and review workload (E-C326, E-C364).', 'research/claude/hn-evidence.md'),
            ('limits', 'This is not evidence that most developers want N attempts.', 'research/shortlist-6.md'),
            ('against', 'Cursor best-of-N, Agent HQ and Codex Cloud attempts exist. Their current capability must be refreshed before claiming a gap.', 'research/claude/workflows-competitors.md')],
    'A06': [('supports', 'Maintainer synthesis E-C201\u2013252: review burden is the recurring pain.', 'research/claude/maintainer-review-evidence.md'),
            ('limits', 'Anti-AI projects are non-buyers. HN E-X014 says review is needed, not that summaries help.', 'research/shortlist-6.md'),
            ('against', 'CodeRabbit navigation and snapshot controls overlap our generic UI claims (E-X028).', 'research/grok/a06-adoption-decision.md')],
    'A10': [('supports', 'Stale worktree PSA (E-X003) and stale-base workflow (E-X008).', 'research/codex/evidence.md'),
            ('limits', 'E-X003 is an incidental tool issue. Contextual recovery needs first-hand corroboration.', 'research/shortlist-6.md'),
            ('against', 'Entire already offers checkpoint refs and resume. Metadata storage alone is not novel.', 'research/claude/workflows-competitors.md')],
}
FIGS = {
    'A01': 'FIG. A01 \u2014 TWO WIP FORKS CHECKED AGAINST EACH OTHER BEFORE EITHER IS DONE',
    'A16': 'FIG. A16 \u2014 THE PILE IS MOSTLY DEPENDENCY SHEETS, NOT SOURCE',
    'A05': 'FIG. A05 \u2014 THREE FORKS, ONE LANDS, LOSERS KEPT WITH REASONS',
    'A06': 'FIG. A06 \u2014 TWO CHANGES FOLDED INTO ONE REVIEW SHEET',
    'A10': 'FIG. A10 \u2014 ONE AGENT HANDS OFF; THE BASE HAS MOVED',
}
STANCE = {'supports': 'SUPPORTS', 'against': 'AGAINST', 'limits': 'LIMITS', 'latest': 'LATEST'}

def src_link(rel, cls='src'):
    return '<a class="'+cls+'" href="'+public_source(rel)+'">'+E(rel)+'</a>'

def project_page(i, p):
    who, sources = PROJECT_EXTRA.get(p['id'], ('', []))
    sources = [s for s in sources if exists(s)]
    sha, when = git_last('website/projects.json')
    prev, nxt = PROJECTS[(i-1) % len(PROJECTS)], PROJECTS[(i+1) % len(PROJECTS)]
    ev_rows = [('latest', p['evidence'], 'website/projects.json')] + [e for e in PROJECT_EVIDENCE.get(p['id'], []) if exists(e[2])]
    def ev(stance, text, rel):
        mark = smark(status_kind(p), 12) if stance == 'latest' else smark(stance, 12)
        when = '' if stance == 'latest' else '<span class="ev-when">BEFORE 3 OCT</span>'
        return '<div class="ev-row"><span class="ev-stance"><span class="ev-label">'+mark+'<span>'+STANCE[stance]+'</span></span>'+when+'</span><span class="ev-body"><span class="ev-text">'+E(text)+'</span>'+src_link(rel)+'</span></div>'
    prov = '<span>Provisional idea; no final shortlist has been approved.</span>'+('<span>Status as of '+E(when)+'.</span>' if when else '')
    return ('<nav class="crumbs" aria-label="Breadcrumb"><a href="'+BASE+'/projects/">Hypotheses</a><span aria-hidden="true">/</span><span>'+E(p['name'])+'</span></nav>'
            '<div class="proj-head"><div class="proj-title"><h1>'+E(p['name'])+'</h1>'
            '<div class="proj-status">'+smark(status_kind(p), 18)+'<span>'+E(p['status'])+'</span></div><div class="mono-meta">'+prov+'</div></div>'
            '<figure class="proj-figure"><img src="'+BASE+'/assets/scenes/'+p['slug']+'.svg" width="640" height="320" alt="'+E(p['name'], quote=True)+': conceptual diagram of the hypothesis, not a measured result"><figcaption>'+E(FIGS.get(p['id'], 'FIG. '+p['id']))+'</figcaption></figure></div>'
            '<article class="proj-body">'
            '<section class="proj-sec"><h2 class="proj-num">01 \u00b7 PROBLEM</h2><p class="proj-problem">'+E(p['problem'])+'</p>'+('<p class="proj-who">Who: '+E(who)+'</p>' if who else '')+'</section>'
            '<section class="proj-sec"><h2 class="proj-num">02 \u00b7 HYPOTHESIS</h2><p class="proj-lead">'+E(p['idea'])+'</p></section>'
            '<section class="proj-sec"><h2 class="proj-num">03 \u00b7 EVIDENCE SO FAR</h2>'+ev(*ev_rows[0])+('<p class="ev-earlier">Earlier research, from before 3 October 2026, 02:24 UTC. Kept for context; it is not the current status.</p>'+''.join(ev(*e) for e in ev_rows[1:]) if len(ev_rows) > 1 else '')+'</section>'
            '<section class="proj-sec test-box"><h2 class="proj-num">04 \u00b7 NEXT FALSIFICATION TEST</h2><p>'+E(p['test'])+'</p><div class="test-grid"><div><span class="field-label">Status</span><span class="test-strong">'+E(p['status'])+'</span></div><div><span class="field-label">We would drop or park it if</span><span>'+E(p['falsifier'])+'</span></div></div></section>'
            '<section class="proj-sec"><h2 class="proj-num">05 \u00b7 PUBLIC SOURCES</h2>'+''.join(src_link(s, 'src-row') for s in sources)+'</section>'
            '<div class="prev-next"><a href="'+BASE+'/projects/'+prev['slug']+'/">'+BACK+E(prev['id']+' \u00b7 '+prev['name'])+'</a><a href="'+BASE+'/projects/'+nxt['slug']+'/">'+E(nxt['id']+' \u00b7 '+nxt['name'])+ARROW+'</a></div>'
            '</article>')

def checklist_page():
    daily = DAILY
    def item(state, title, note, date, rel):
        return (state, title, note, date, rel)
    groups = [
        ('Research and publication', [
            item('done', 'Explore twenty distinct approaches', 'The research inventory is public. Scores and the original shortlist are historical, not final approval.', '2 Oct', 'research/approaches-20.md'),
            item('done', 'Challenge assumptions from both sides', 'Independent principals challenge outputs, methods, and the human brief. A01 lost its primary recommendation.', '2 Oct', 'research/debate/'),
            item('done' if daily else 'pending', 'Publish evidence-checked daily stories', 'First report published and the daily 09:30 Europe/Berlin workflow configured. Ongoing daily continuity remains to be verified.' if daily else 'Claude Opus writes with stylint; factual claims, diagrams, and illustrations are checked before publishing.', (parse_utc(daily[0].get('published_at')).strftime('%-d %b') if daily and parse_utc(daily[0].get('published_at')) else '\u2014'), ('website/content/daily/'+daily[0]['path'].name) if daily else 'website/README.md'),
        ]),
        ('Hypothesis gates', [
            item('withdrawn', 'A01 primary recommendation withdrawn', 'Decision at the 03 October 2026, 02:24 UTC evidence cutoff: both principals withdrew primary status after the fair live comparison showed no separation. This does not prove warnings can never help.', 'cutoff 3 Oct, 02:24 UTC', 'research/shortlist-6.md'),
            item('failed', 'Storage test below its registered gate', 'At that cutoff, clean-identical-cache N2 whole-footprint savings were 48.17%, below the registered greater-than-50% gate. This is a limited fixture, not safe savings from existing worktrees.', 'cutoff 3 Oct, 02:24 UTC', 'research/codex/retained-lanes-review-2324.md'),
            item('failed', 'Runtime regression still failed', 'The 02:24 UTC field note records zero passing tests and one failure: COUNT 0 where COUNT 1 was expected. Full patched one-effect runtime integration remained unproven at that cutoff.', '3 Oct, 02:24 UTC', 'research/orchestrator/heartbeat-20261003T0224.md'),
            item('done', 'A16 parked in draft8', 'Repeated whole-footprint gates failed and the incumbent arm was near-equal. Storage advice survives; the parked competition product does not occupy a selected place.', '3 Oct', 'research/shortlist-6.md'),
            item('done', 'Current runtime evidence is scoped', 'At 03 October 2026, 05:11 UTC, independent review confirms one outer call/one effect in the constrained patched probe, but two successful outer writes in the unconstrained task. Exactly-once retry/resume and reliable between-turn handoffs remain open. Historical test failures above retain their original cutoff.', '3 Oct, 05:11 UTC', 'research/orchestrator/heartbeat-20261003T0511.md'),
        ]),
        ('Selection, use and handoff', [
            item('open', 'Agree on six viable approaches', 'The current draft retains '+str(ACTIVE_COUNT)+' hypotheses and parks '+str(PARKED_COUNT)+' candidates. '+str(OPEN_PLACES)+' product places remain open; identical-digest approval from both principals is still required.', '\u2014', 'research/shortlist-6.md'),
            item('pending', 'Demonstrate actual agent use', 'Show a useful task, real agent actions, and accepted outcomes. A scripted fixture alone does not pass.', '\u2014', 'research/shortlist-6.md'),
            item('pending', 'Prove an advantage over ordinary tools', 'Compare equal tasks, information, and acceptance checks. Preserve ties, failures, and negative results.', '\u2014', 'research/shortlist-6.md'),
            item('pending', 'Keep development recoverable', 'Ordinary Git recovery stays independent of the prototype. A source-only restore is limited evidence.', '\u2014', 'experiment/EXPERIMENT.md'),
            item('pending', 'Hand off five productive project teams', 'Verify meaningful deliverables, independent ownership, and an actual next task; a live process is insufficient.', '\u2014', 'experiment/EXPERIMENT.md'),
        ]),
    ]
    label = {'done': 'DONE', 'pending': 'PENDING', 'failed': 'FAILED', 'withdrawn': 'WITHDRAWN', 'open': 'OPEN'}
    counts = {}
    for _, items in groups:
        for it in items:
            counts[it[0]] = counts.get(it[0], 0)+1
    legend = '<div class="legend" aria-label="Gate states">'+''.join('<span class="legend-item">'+smark(k)+'<span class="legend-label">'+label[k]+'</span><span class="legend-count">'+str(counts.get(k, 0))+'</span></span>' for k in label)+'</div>'
    def row(state, title, note, date, rel):
        return ('<div class="gate'+(' is-failed' if state == 'failed' else '')+'"><div class="gate-main"><span class="gate-mark">'+smark(state)+'</span><div class="gate-text"><span class="gate-title">'+E(title)+'</span><span class="gate-note">'+E(note)+'</span></div></div>'
                '<div class="gate-meta"><span class="gate-state">'+label[state]+' \u00b7 '+E(date)+'</span>'+(src_link(rel) if exists(rel) else '')+'</div></div>')
    body = ''.join('<section class="gate-group"><h2>'+E(t)+'</h2>'+''.join(row(*it) for it in items)+'</section>' for t, items in groups)
    latest_cutoff = LATEST_NOTE.strftime('%d %b %Y, %H:%M UTC') if LATEST_NOTE else 'no field note published'
    closing = ('<p class="closing-note">Status comes from the published selection draft and orchestrator reports. Snapshot built '+BUILD_TIME+'; latest field-note cutoff '+E(latest_cutoff)+'. Daily publication: '+('first report recorded; continuing daily reliability unproven' if daily else 'first report pending')+'. '
               +('<a href="'+BASE+'/'+daily[0]['route']+'">First daily story'+ARROW+'</a> \u00b7 ' if daily else '')+'<a href="'+public_source('research/shortlist-6.md')+'">Inspect the selection gates'+EXT+'</a></p>')
    return '<div class="narrow">'+intro('Gates, with dates', 'A public view of the gates, not a score for how many agents we can launch. A gate passes, fails, or waits. Project teams test their hypotheses while selection continues.')+legend+body+closing+'</div>'

def library_page():
    curated = [
        ('Decisions', 'What we currently believe, and what nobody has signed.', [('Shortlist draft (unsigned)', 'research/shortlist-6.md'), ('Consensus record \u2014 pending', 'research/consensus.md'), ('All 20 approaches', 'research/approaches-20.md'), ('Prototype plan', 'research/prototype-plan.md')]),
        ('Measurements', 'Numbers from fixtures and one real host.', [('Worktree disk on the real host', 'research/claude/u7-real-worktree-measurement.md'), ('Storage fixture validation', 'research/codex/storage-validation.md'), ('Package storage validation', 'research/codex/package-storage-validation.md'), ('Physical storage isolation', 'research/antigravity/r8-physical-storage-isolation.md'), ('A01 fair-pair results', 'research/grok/a01-fair-results.md'), ('A01 live independent replay', 'research/codex/a01-live-independent-replay.json')]),
        ('Evidence', 'Pain reported by developers and maintainers.', [('Evidence ledger', 'research/evidence-ledger.md'), ('Hacker News evidence', 'research/claude/hn-evidence.md'), ('Maintainer review evidence', 'research/claude/maintainer-review-evidence.md'), ('Codex evidence (Reddit, coordination)', 'research/codex/evidence.md'), ('Social evidence', 'research/orchestrator/social-evidence.md')]),
        ('Competitors and feasibility', 'What already exists, and what Artifacts can actually do.', [('Workflows and competitors', 'research/claude/workflows-competitors.md'), ('Engineering feasibility', 'research/codex/engineering-feasibility.md'), ('Pro investigations, integrated', 'research/codex/pro-integration-round-1.md')]),
        ('Debate', 'Rejection arguments and responses.', [('Debate folder', 'research/debate/'), ('Retained lanes review, 23:24', 'research/codex/retained-lanes-review-2324.md'), ('Open disagreements', 'research/debate/codex-open-disagreements.md')]),
        ('How the experiment runs', 'Rules, instructions and resource limits.', [('Brief', 'BRIEF.md'), ('Experiment', 'experiment/EXPERIMENT.md'), ('User instructions', 'experiment/USER-INSTRUCTIONS.md'), ('Resource policy', 'coordination/RESOURCE-POLICY.md')]),
    ]
    def lib_row(title, rel):
        return '<a class="lib-item" href="'+public_source(rel)+'"><span class="lib-title">'+E(title)+'</span><span class="lib-path">'+E(rel)+'</span></a>'
    def group(title, note, rows, collapsible=None):
        inner = ''.join(rows)
        if collapsible:
            inner = '<details class="lib-more"><summary>'+E(collapsible)+'</summary>'+inner+'</details>'
        return '<section class="lib-group"><div class="lib-head"><h2>'+E(title)+'</h2><p>'+E(note)+'</p></div><div class="lib-rows">'+inner+'</div></section>'
    out = [group(t, n, [lib_row(a, b) for a, b in items if exists(b)]) for t, n, items in curated]
    top = sorted((ROOT/'research').glob('*.md'))
    out.append(group('Selection and shared research', 'Every top-level research file, in the order the repository lists them.', [lib_row(p.stem.replace('-', ' ').capitalize(), str(p.relative_to(ROOT))) for p in top]))
    for g in ['orchestrator', 'claude', 'codex', 'grok', 'antigravity', 'zcode', 'space-bunny', 'muse', 'debate']:
        paths = sorted((ROOT/'research'/g).rglob('*.md'))
        paths = [p for p in paths if not any(part.startswith('.') for part in p.relative_to(ROOT).parts)]
        if paths:
            name = g.replace('-', ' ').title()
            out.append(group(name, str(len(paths))+' documents from the '+name+' workspace.', [lib_row(str(p.relative_to(ROOT/'research'/g)), str(p.relative_to(ROOT))) for p in paths], 'Show all '+str(len(paths))+' documents'))
    return '<div class="narrow">'+intro('The evidence, filed', 'Research, challenges, and evidence live in the public repository. Private agent logs and credentials are excluded. Grouped by what a document is for, then by engine.')+''.join(out)+'</div>'

def notes_page():
    entries = []
    for i, rp in enumerate(REPORTS):
        title, summary, kind = note_info(rp)
        entries.append('<li class="tl-item tl-'+kind+('' if i else ' is-first')+'"><span class="tl-rail" aria-hidden="true"><span class="tl-top"></span><span class="tl-dot"></span><span class="tl-line"></span></span>'
                       '<a class="tl-body" href="'+BASE+'/reports/'+rp.stem+'/"><span class="tl-title">'+E(title)+'</span><span class="tl-when">'+E(note_stamp(rp).strftime('%a %-d %b, %H:%M UTC'))+'</span><span class="tl-summary">'+E(summary)+'</span><span class="tl-path">'+E(str(rp.relative_to(ROOT)))+'</span></a></li>')
    legend = '<p class="tl-legend"><span class="tl-key"><span class="tl-dot k-failed"></span>Failure</span><span class="tl-key"><span class="tl-dot k-decision"></span>Decision or correction</span><span class="tl-key"><span class="tl-dot k-routine"></span>Routine check</span></p>'
    return '<div class="narrow">'+intro('Field notes, with receipts', 'Dated remote check-ins, including failures and corrections. Older reports describe what was known then; read later updates before reusing a claim.')+legend+'<ol class="timeline">'+''.join(entries)+'</ol></div>'

def article_head(title, deck, byline_rows):
    return '<header class="article-head"><h1>'+E(title)+'</h1>'+('<p class="article-deck">'+E(deck)+'</p>' if deck else '')+byline_rows+'</header>'

def byline_block(person_line, mono_spans):
    return ('<div class="byline-block"><div class="byline-person"><span class="byline-logo" aria-hidden="true">'+LOGO_SVG+'</span>'+person_line+'</div>'
            '<div class="mono-meta">'+''.join(mono_spans)+'</div></div>')

def source_title(url, titles=None):
    """Readable link text for a source URL; hashes and paths stay in the href only."""
    if titles and url in titles:
        return titles[url]
    m = re.match(r'^https://github\.com/([^/]+)/([^/#?]+)(?:/(blob|tree|commit)/([^/]+)(?:/(.*))?)?', url)
    if m:
        repo, kind, path = m[2], m[3], m[5] or ''
        if not kind:
            return 'The '+repo+' repository'
        if kind == 'commit':
            return 'A change in the '+repo+' repository'
        beat = re.search(r'heartbeat-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})', path)
        if beat:
            return 'Coordinating agent\'s check, '+beat[1]+'-'+beat[2]+'-'+beat[3]+' '+beat[4]+':'+beat[5]+' UTC'
        stem = re.sub(r'\.(md|json|txt)$', '', path.rstrip('/').split('/')[-1])
        return stem.replace('-', ' ').replace('_', ' ').capitalize()+' ('+repo+')'
    host = urlparse(url).netloc.removeprefix('www.')
    last = urlparse(url).path.rstrip('/').split('/')[-1]
    last = re.sub(r'\.(pdf|html?)$', '', last).replace('-', ' ').strip()
    return host+(': '+last if last else '')

def daily_page(d):
    content = d['path'].read_text()
    content = re.sub(r'^#\s+[^\n]+\n?', '', content, count=1)
    prose = markdown(content, d['path'])
    strip = '<div class="stat-strip">'+''.join('<div><span class="stat-n">'+E(n)+'</span><span class="stat-l">'+E(l)+'</span></div>' for n, l in PAIN_STATS)+'</div>'
    prose = re.sub(r'(<p>[^\n]*111\.7 GiB of physical disk[^\n]*</p>)', lambda m: m[1]+strip, prose, count=1)
    spans = ['<span class="ink">EVIDENCE UP TO '+E(utc_text(d.get('source_cutoff', d['date'])))+'</span>']
    if d.get('update_cutoff'):
        spans.append('<span>MORNING UPDATE UP TO '+E(utc_text(d['update_cutoff']))+'</span>')
    spans.append('<span>'+str(len(d.get('sources', [])))+' SOURCES LINKED BELOW</span>')
    person = '<span class="byline-name">'+E(d.get('author', 'Alexey Grigorev'))+'</span><span class="muted">Written with Claude Opus</span><span class="muted">'+E(long_date(d['date']))+'</span>'
    titles = d.get('source_titles', {})
    sources = ''.join('<a class="src" href="'+E(u, quote=True)+'">'+E(source_title(u, titles))+'</a>' for u in d.get('sources', []))
    return ('<article class="article">'+article_head(d['title'], d.get('summary', ''), byline_block(person, spans))
            +'<div class="prose">'+prose+'</div>'
            '<div class="article-sources">'+'<h2 class="sources-h">Sources for this report</h2>'+sources+'<p class="source-line">Writing assistance: Claude Opus. Original Markdown: <a href="'+public_source(d['path'].relative_to(ROOT))+'">read in the repository'+EXT+'</a>. Illustrations are conceptual artwork.</p></div></article>')

def note_page(rp):
    title, summary, kind = note_info(rp)
    spans = ['<span class="ink">EVIDENCE UP TO '+note_stamp(rp).strftime('%Y-%m-%d %H:%M')+' UTC</span>', '<span>'+E(readable_cutoff(note_stamp(rp).isoformat()).split(' / ')[1].upper())+'</span>', '<span>HISTORICAL SNAPSHOT, NOT CURRENT PRODUCT VALIDATION</span>']
    person = '<span class="byline-name">Field note</span><span class="muted">'+E(note_stamp(rp).strftime('%A %-d %B %Y, %H:%M UTC'))+'</span><a href="'+public_source(rp.relative_to(ROOT))+'">Original report and version history'+EXT+'</a>'
    return ('<article class="article field-note">'+article_head(report_title(rp), title+'. '+summary if kind != 'routine' else '', byline_block(person, spans))
            +'<div class="prose">'+markdown(re.sub(r'^#\s+[^\n]+\n?', '', rp.read_text(), count=1), rp)+'</div>'
            '<p class="back-link"><a href="'+BASE+'/reports/">'+BACK+'All field notes</a></p></article>')

def home_page():
    if LATEST:
        cutoff = LATEST_CUTOFF.strftime('%Y-%m-%d %H:%M')+' UTC' if LATEST_CUTOFF else str(LATEST['date'])
        feature = ('<article class="feature"><h1><a href="'+BASE+'/'+LATEST['route']+'">'+E(LATEST['title'])+'</a></h1><p class="feature-deck">'+E(LATEST.get('summary', ''))+'</p>'
                   '<p class="feature-byline"><span class="ink">'+E(LATEST.get('author', 'Alexey Grigorev'))+'</span><span>Written with Claude Opus</span><span>'+E(long_date(LATEST['date']))+'</span><span class="chip">EVIDENCE UP TO '+E(cutoff)+'</span></p>'
                   '<a class="read-more" href="'+BASE+'/'+LATEST['route']+'">Read the daily report'+ARROW+'</a></article>')
    else:
        feature = '<article class="feature"><h1>What we learn belongs here</h1><p class="feature-deck">The opening story is being written and checked against the evidence. Read the dated field notes while it is prepared.</p><a class="read-more" href="'+BASE+'/reports/">Read the field notes'+ARROW+'</a></article>'
    rows = [('20', 'Approaches researched', 'Independent briefs in repo'), (str(ACTIVE_COUNT), 'Ideas still being tested', 'Collision radar (conditional) and change stories'), ('0', 'Agreed final six', 'The two lead agents haven\u2019t agreed'), (str(OPEN_PLACES), 'Product places open', 'No idea selected for them'), ('111.7 GiB', 'Worktree disk measured', 'Across 472 worktrees'), ('62.1%', 'Dependencies & builds', 'Not ordinary Git storage')]
    honest = ('<aside class="honest" aria-labelledby="honest-title"><div class="honest-head"><h2 id="honest-title">Status</h2></div><div class="honest-rows">'
              +''.join('<div class="honest-row"><span class="honest-n">'+num_html(n)+'</span><span class="honest-detail"><span class="honest-label">'+E(l)+'</span><span class="honest-note">'+E(note)+'</span></span></div>' for n, l, note in rows)
              +'</div><a class="honest-link" href="'+BASE+'/checklist/">See every check on the checklist'+ARROW+'</a></aside>')
    hero = ('<section class="hero"><figure class="hero-figure"><img src="'+BASE+'/assets/agent-git-illustration.png" width="1536" height="1024" alt="Geometric blue agents carry folders along branching commit lines into an orange merge"></figure>'
            '<div class="hero-grid">'+feature+honest+'</div></section>')
    hyp = ('<section class="hyp-section" aria-labelledby="hyp-title"><div class="section-head"><h2 id="hyp-title">The hypotheses</h2><p>'+str(ACTIVE_COUNT)+' still being tested. '+str(PARKED_COUNT)+' parked. '+str(OPEN_PLACES)+' places open. None selected.<span class="only-phone"> Every idea is provisional.</span> <a href="'+BASE+'/ideas/">Read what all 20 ideas would do'+ARROW+'</a></p></div>'+cards()+'</section>')
    stats = ''.join('<div class="pain-stat"><span class="pain-n">'+E(n)+'</span><span class="pain-l">'+E(l)+'</span></div>' for n, l in PAIN_STATS)
    pain = ('<section class="pain" aria-labelledby="pain-title"><div class="pain-copy">'+'<h2 id="pain-title">Most of the worktree pile isn\u2019t Git. It\u2019s dependencies.</h2><p>The pain is real and measured. Whether anyone would adopt a product for it is unknown. Package managers that already keep one shared copy of dependencies for many folders may solve it without a new product.</p><a class="read-more-sm" href="'+BASE+'/projects/storage-aware-workspaces/">Read the storage-aware workspaces idea'+ARROW+'</a></div>'
            '<div class="pain-data"><div class="pain-stats">'+stats+'</div><div class="pain-chart"><div class="pain-bar" role="img" aria-label="62.1% of the disk space is dependencies and build output"><span class="pain-fill"></span></div><div class="pain-caps"><span>Dependencies and build output: 69.4 GiB (62.1%)</span><span class="muted">Source code and everything else: about 42 GiB</span></div><div class="status-line pain-unknown">'+smark('unknown')+'<span>Whether this needs a new product: unknown</span></div></div></div></section>')
    fields = ''.join('<a class="row-link field-row" href="'+BASE+'/reports/'+rp.stem+'/"><span class="field-time">'+note_time(rp)+'</span><span class="field-title">'+E(note_info(rp)[0])+'</span></a>' for rp in REPORTS[:4])
    libs = [('Shortlist draft (unsigned)', 'research/shortlist-6.md'), ('Worktree disk on the real host', 'research/claude/u7-real-worktree-measurement.md'), ('Consensus record \u2014 pending', 'research/consensus.md'), ('All 20 approaches', 'research/approaches-20.md')]
    lib_rows = ''.join('<a class="row-link lib-row" href="'+public_source(rel)+'"><span class="lib-title">'+E(t)+'</span><span class="lib-path">'+E(rel)+'</span></a>' for t, rel in libs)
    bottom = ('<section class="home-bottom"><div class="home-col"><div class="col-head"><h2>Field notes</h2><a class="read-more-sm" href="'+BASE+'/reports/">Archive'+ARROW+'</a></div><p class="col-sub">Checks by the coordinating agent, dated. Times in UTC.</p>'+fields+'</div>'
              '<div class="home-col"><div class="col-head"><h2>Research library</h2><a class="read-more-sm" href="'+BASE+'/research/">All sources'+ARROW+'</a></div><p class="col-sub">Everything links to a file in the public repo.</p>'+lib_rows+'</div></section>')
    return hero+hyp+pain+bottom

IDEAS = ROOT/'website/content/ideas.md'

def ideas_page():
    text = IDEAS.read_text()
    title = re.match(r'^#\s+(.+)', text)[1].strip()
    prose = markdown(re.sub(r'^#\s+[^\n]+\n?', '', text, count=1), IDEAS)
    # The ideas are numbered 1-20 across several grouped lists; keep the numbering continuous.
    count = [1]
    def numbered(m):
        start = count[0]
        count[0] += m[1].count('<li>')
        return '<ol start="'+str(start)+'">'+m[1]+'</ol>'
    prose = re.sub(r'<ol>(.*?)</ol>', numbered, prose, flags=re.S)
    # Bold each idea's name (the text before the first colon) so readers can scan the list;
    # the Markdown source stays free of bold markup for stylint.
    prose = re.sub(r'<li>([^<:]+):', r'<li><strong>\1:</strong>', prose)
    return (title, '<article class="article">'+article_head(title, 'What each of the 20 approaches would do for a person who runs many coding agents on the same code.', '')
            +'<div class="prose">'+prose+'</div>'
            '<div class="article-sources"><p class="source-line">Original Markdown: <a href="'+public_source(IDEAS.relative_to(ROOT))+'">read in the repository'+EXT+'</a>.</p></div></article>')

# ---------------------------------------------------------------- build
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    def write(route, title, body, description=None, kind='wide'):
        target = output / route / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(title, body, route, description or 'A public experiment in Git, coding agents, and the work between them.', kind), encoding='utf-8')
    shutil.copytree(ASSETS, output/'assets', dirs_exist_ok=True)
    (output/'.nojekyll').write_text('')
    daily = DAILY
    for d in daily:
        write(d['route'], d['title'], daily_page(d), d.get('summary'), 'article')
    write('', LATEST['title'] if LATEST else 'Agent Branches', home_page(), kind='home')
    rows = ''.join('<a class="journal-row" href="'+BASE+'/'+d['route']+'"><span class="journal-title">'+E(d['title'])+'</span><span class="journal-date">'+E(long_date(d['date']))+' \u00b7 evidence up to '+E(utc_text(d.get('source_cutoff', d['date'])))+'</span><span class="journal-summary">'+E(d.get('summary', ''))+'</span><span class="read-more-sm">Read the story'+ARROW+'</span></a>' for d in daily)
    write('daily/', 'Daily journal', '<div class="narrow">'+intro('The daily journal', 'What we tried, what held up, and what changed our minds. Written with Claude Opus, checked against the experiment.', '<a class="read-more-sm" href="'+BASE+'/feed.xml">Subscribe via RSS'+ARROW+'</a>')+'<div class="journal-list">'+(rows or '<p>The first evidence-checked story is being prepared.</p>')+'</div></div>')
    write('projects/', 'Hypotheses', intro('Ideas with work to do', str(len(PROJECTS))+' directions have pages here: '+str(ACTIVE_COUNT)+' retained for falsification and '+str(PARKED_COUNT)+' parked. Selection and development gates are separate; these are provisional research lanes, not products. Each page states what would change our mind.')+cards(with_next=True))
    for i, p in enumerate(PROJECTS):
        write('projects/'+p['slug']+'/', p['name'], project_page(i, p), p['summary'], 'project')
    write('reports/', 'Field notes', notes_page())
    for rp in REPORTS:
        write('reports/'+rp.stem+'/', report_title(rp), note_page(rp), None, 'article')
    write('research/', 'Research library', library_page())
    ideas_title, ideas_body = ideas_page()
    write('ideas/', ideas_title, ideas_body, 'What each of the 20 approaches collected by the agent team would do.', 'article')
    write('checklist/', 'Experiment checklist', checklist_page())
    team_fig = '<figure class="portrait-fig"><img loading="lazy" src="'+BASE+'/assets/team-workflow-mobile.svg" alt="How the team works: Alexey and the coordinating agent connect to the Claude and Codex lead agents, five research teams, worker agents, evidence, and review."><figcaption>The operating model. Arrows show responsibilities, not proof of continuous activity.</figcaption></figure>'
    about = ('<article class="article">'+article_head('Build it. Test it. Tell the whole story.', 'A new Git platform competition prompted a wider question: where does Git make a team of coding agents harder to run?', '')
             +'<div class="prose"><h2>Start with actual pain</h2><p>Alexey\u2019s worktrees filled disk quickly. A read-only scan found 472 linked worktrees across 25 repositories, occupying a physical union of 111.7 GiB. Dependencies and builds accounted for 69.4 GiB, or 62.1%. These are measurements from one host, not a claim about every developer.</p><h2>Let the agents challenge each other</h2><p>Claude and Codex, the two lead agents, monitor the work and challenge each other\u2019s evidence. Research teams coordinate useful tasks, and worker agents can run in the background. The team is free to improve its working method, while preserving quotas, code recovery, and privacy.</p>'+team_fig+'<h2>Keep the failures visible</h2><p>Research is not product validation. No final six-approach shortlist has been approved. The first live integration comparison showed no separation, so that idea\u2019s primary status was withdrawn. A small storage experiment fell below the savings target set before the test.</p><h2>Use what survives</h2><p>Teams should build the smallest useful prototype and use it in their own development. Accepted outcomes, peer review, and recoverable Git history matter more than a launch count.</p>'
             '<p><a href="'+public_source('experiment/USER-INSTRUCTIONS.md')+'">The original user brief'+EXT+'</a> \u00b7 <a href="'+public_source('AGENTS.md')+'">How the agents are expected to work'+EXT+'</a> \u00b7 <a href="https://blog.cloudflare.com/next-git-platform-on-cloudflare/">The competition that started it'+EXT+'</a></p></div></article>')
    write('experiment/', 'About the experiment', about, None, 'article')
    write('subscribe/', 'Confirm your experiment updates', intro('Stay with the experiment', 'Sign up for Agent Branches updates, or use the confirmation link from your inbox. This list is separate from PocketShell and other newsletters.')+signup_section(dedicated=True))
    privacy = ('<article class="article">'+article_head('Your address stays private', '', '')+'<div class="prose"><h2>What you are signing up for</h2><p>Agent Branches experiment updates: useful findings, project progress, and corrections. A signup does not enroll you in PocketShell or another newsletter. You can read daily reports in the journal; the email list is for occasional experiment updates.</p><h2>Confirmation and storage</h2><p>We use DataTalks.Club Relay, the same public double opt-in flow used by PocketShell. Your email address and pending or confirmed subscription state are stored in a separate Agent Branches audience. Relay sends a confirmation link; you join the confirmed list only after using it.</p><p>The website sends your address directly to the fixed Relay signup endpoint. No client API key is placed in the page. We do not put submitted addresses or confirmation tokens into the public repository, research reports, agent prompts, or browser storage.</p><h2>Leaving the list</h2><p>You can ignore a confirmation you did not request. Unsubscribe through the link in an update email. Repeated requests can be rate limited; that is separate from confirmation.</p><h2>Website and service requests</h2><p>The website is hosted on GitHub Pages and the email flow is handled by Relay. Those services process the requests needed to deliver the page and manage the opt-in, including their ordinary operational records. No visitor analytics or public signup telemetry is added by this form.</p>'
               '<p><a href="'+BASE+'/subscribe/">Back to signup</a> \u00b7 <a href="https://github.com/DataTalksClub/relay">Relay source'+EXT+'</a></p></div></article>')
    write('privacy/', 'Email privacy', privacy, None, 'article')
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    for tag, value in [('title', 'Agent Branches \u2014 Daily journal'), ('link', ORIGIN+BASE+'/'), ('description', 'The experiments, failures, and decisions behind Git for coding agents.')]:
        ET.SubElement(channel, tag).text = value
    for d in daily:
        item = ET.SubElement(channel, 'item')
        for tag, value in [('title', d['title']), ('link', ORIGIN+BASE+'/'+d['route']), ('guid', ORIGIN+BASE+'/'+d['route']), ('description', d.get('summary', ''))]:
            ET.SubElement(item, tag).text = value
    ET.ElementTree(rss).write(output/'feed.xml', encoding='utf-8', xml_declaration=True)
    print(json.dumps({'output': str(output), 'html_pages': len(list(output.rglob('*.html'))), 'published_daily': len(daily), 'field_notes': len(REPORTS), 'projects': len(PROJECTS)}))

if __name__ == '__main__':
    main()
