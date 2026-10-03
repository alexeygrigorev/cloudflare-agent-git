#!/usr/bin/env python3
"""Build the public journal. Python standard library only; no private inputs."""
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
LOGO_SVG = '<svg width="44" height="44" viewBox="0 0 52 52" role="img" aria-label="Agent"><line x1="21.5" y1="31.7" x2="19" y2="49.9" stroke="#1C2027" stroke-width="2.1" stroke-linecap="round"/><line x1="30.5" y1="31.7" x2="31.9" y2="49.9" stroke="#1C2027" stroke-width="2.1" stroke-linecap="round"/><circle cx="26" cy="24" r="14" fill="#2455ED"/><circle cx="22.6" cy="23.3" r="1.5" fill="#fff"/><circle cx="29.4" cy="23.3" r="1.5" fill="#fff"/></svg>'
def _legs():
    return '<line x1="21.5" y1="31.7" x2="19" y2="49.9" stroke="#1C2027" stroke-width="2.1" stroke-linecap="round"/><line x1="30.5" y1="31.7" x2="31.9" y2="49.9" stroke="#1C2027" stroke-width="2.1" stroke-linecap="round"/>'
def _eyes(fill):
    return '<circle cx="22.6" cy="23.3" r="1.5" fill="'+fill+'"/><circle cx="29.4" cy="23.3" r="1.5" fill="'+fill+'"/>'
CARD_MARKS = {
    'A01': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="circle marker">'+_legs()+'<circle cx="26" cy="24" r="14" fill="#2455ED"/>'+_eyes('#fff')+'</svg>',
    'A16': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="square marker">'+_legs()+'<rect x="14" y="12" width="24" height="24" fill="#2455ED"/>'+_eyes('#fff')+'</svg>',
    'A05': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="triangle marker">'+_legs()+'<polygon points="26,6.5 39.3,32.4 12.7,32.4" fill="#2455ED"/>'+_eyes('#fff')+'</svg>',
    'A06': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="diamond marker">'+_legs()+'<polygon points="26,7.9 42.1,24 26,40.1 9.9,24" fill="#2455ED"/>'+_eyes('#fff')+'</svg>',
    'A10': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="pentagon marker">'+_legs()+'<polygon points="26,8.9 40.4,19.3 34.9,36.2 17.1,36.2 11.6,19.3" fill="#2455ED"/>'+_eyes('#fff')+'</svg>',
    'SLOT6': '<svg width="56" height="56" viewBox="0 0 52 52" role="img" aria-label="open star marker">'+_legs()+'<polygon points="26,6 30.5,19 44,19 33,27.5 37,41 26,33 15,41 19,27.5 8,19 21.5,19" fill="#FCFCF8" stroke="#1C2027" stroke-width="2" stroke-dasharray="4 3"/>'+_eyes('#1C2027')+'</svg>',
}
STATUS_SVG = {
    'withdrawn': '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="#1C2027" stroke-width="2"/><path d="M2.5 13.5 L13.5 2.5" stroke="#1C2027" stroke-width="2"/></svg>',
    'pending': '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" fill="none" stroke="#2455ED" stroke-width="2.4"/></svg>',
    'open': '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" fill="none" stroke="#1C2027" stroke-width="1.8" stroke-dasharray="2.5 2.5"/></svg>',
    'unknown': '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="2" width="12" height="12" fill="none" stroke="#1C2027" stroke-width="1.8" stroke-dasharray="2.5 2.5"/><circle cx="8" cy="8" r="1.8" fill="#1C2027"/></svg>',
}
def status_mark_for(proj):
    s = str(proj.get('status','')).lower()
    if 'withdrawn' in s:
        return STATUS_SVG['withdrawn']
    if 'parked' in s:
        return STATUS_SVG['withdrawn']
    if 'internal use' in s:
        return STATUS_SVG['pending']
    return STATUS_SVG['pending']

BUILD_TIME = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
BUILD_SHA = os.environ.get('GITHUB_SHA', '')
if not re.fullmatch(r'[0-9a-f]{40}', BUILD_SHA):
    try:
        BUILD_SHA = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=5).strip()
    except (subprocess.SubprocessError, OSError):
        BUILD_SHA = ''

def public_source(path):
    return REPO + '/blob/main/' + quote(str(path), safe='/')

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
    image = '<img loading="lazy" src="'+E(image_url, quote=True)+'" alt="'+E(alt, quote=True)+'">'
    if image_url == BASE+'/assets/team-workflow.svg':
        image = '<picture><source media="(max-width: 600px)" srcset="'+BASE+'/assets/team-workflow-mobile.svg">'+image+'</picture>'
    return '<figure>'+image+'<figcaption>'+E(alt)+'</figcaption></figure>'

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
    out, paragraph, listing, code = [], [], None, None
    def flush():
        if paragraph:
            out.append('<p>'+inline(' '.join(paragraph), source)+'</p>')
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
            level = min(6, len(heading[1])+1)
            out.append(f'<h{level}>'+inline(heading[2], source)+f'</h{level}>')
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


def signup_section(dedicated=False):
    enabled = SIGNUP.get('enabled') is True
    endpoint = str(SIGNUP.get('relay_list', ''))
    if endpoint != 'https://relay.datatalks.club/api/public/lists/agent-git-lab':
        raise ValueError('Unexpected Relay public-list endpoint; review configuration before publishing.')
    unavailable = '<p class="signup-setup-note">Email signup is being connected. You can follow the <a href="'+BASE+'/feed.xml">RSS feed</a> meanwhile.</p>' if not enabled else ''
    disabled = '' if enabled else ' disabled'
    return '<section class="email-signup '+('dedicated-signup' if dedicated else '')+'" aria-labelledby="signup-title"><div class="signup-copy"><p class="eyebrow">Follow the useful results</p><h2 id="signup-title">Get experiment updates.</h2><p>New findings, honest failures, and what we build next. Confirm your address before joining the list.</p><p class="signup-detail">Sign up for occasional experiment updates. Read the daily reports in the journal.</p></div><form id="journal-signup" class="signup-form" data-relay-list="'+E(endpoint,quote=True)+'" data-enabled="'+('true' if enabled else 'false')+'" aria-busy="false"><label for="signup-email">Your email address</label><div class="signup-controls"><input id="signup-email" name="email" type="email" autocomplete="email" inputmode="email" maxlength="254" placeholder="you@example.com" required'+disabled+'><button id="signup-submit" class="button" type="submit"'+disabled+'>Keep me posted <span aria-hidden="true">↗</span></button></div><label class="signup-consent" for="signup-consent"><input id="signup-consent" name="consent" type="checkbox" required'+disabled+'><span>I agree to receive occasional Agent Git Lab experiment updates by email.</span></label><p class="signup-detail">Your address is processed by DataTalks.Club Relay for this list. Unsubscribe through the link in an update email. <a href="'+BASE+'/privacy/">Email privacy</a>.</p>'+unavailable+'<p id="signup-status" class="signup-status" role="status" aria-live="polite" aria-atomic="true" tabindex="-1" hidden></p><noscript><p>Email signup needs JavaScript for the confirmation flow. The <a href="'+BASE+'/feed.xml">RSS feed</a> works without it.</p></noscript></form></section>'

def page(title, body, route='', description='A public experiment in Git, coding agents, and the work between them.'):
    links = [('Journal', ''), ('Hypotheses', 'projects/'), ('Checklist', 'checklist/'), ('Daily report', 'daily/'), ('Field notes', 'reports/'), ('Library', 'research/'), ('System', 'experiment/')]
    footer_metadata = '<p class="build-metadata">Site built '+BUILD_TIME+(' · <a href="'+REPO+'/commit/'+BUILD_SHA+'">Source revision '+BUILD_SHA[:12]+' ↗</a>' if BUILD_SHA else ' · Source revision unavailable')+'</p>'
    cutoff_files = sorted((ROOT/'research/orchestrator').glob('heartbeat-*.md'), reverse=True)
    if cutoff_files:
        stamp = datetime.strptime(cutoff_files[0].stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').replace(tzinfo=timezone.utc)
        footer_metadata += '<p class="build-metadata">Latest field-note cutoff: '+E(readable_cutoff(stamp.isoformat()))+'. Evidence is dated; build time is not a live agent status.</p>'
    nav = ''.join('<a '+('aria-current="page" ' if (route == path or (path and route.startswith(path))) else '')+'href="'+BASE+'/'+path+'">'+label+'</a>' for label,path in links)
    header = '<header class="site-header"><div class="header-top"><a class="header-brand" href="'+BASE+'''/'"><span class="header-logo" aria-hidden="true">'''+LOGO_SVG+'''</span><span><span class="header-title">Agent Git Lab</span><span class="header-subtitle">Alexey Grigorev\'s build-in-public experiment on Git and coding agents</span></span></a><div class="header-meta"><span>LATEST DAILY 2026-10-03</span><span class="header-cutoff">EVIDENCE CUTOFF 02:24 UTC</span></div></div><nav class="site-nav" aria-label="Main navigation">'''+nav+'</nav></header>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+' · Agent Git Lab</title><meta name="description" content="'+E(description, quote=True)+'"><meta name="theme-color" content="#2455ed"><link rel="stylesheet" href="'+BASE+'/assets/site.css"><link rel="alternate" type="application/rss+xml" title="Agent Git Lab journal" href="'+BASE+'/feed.xml"><link rel="canonical" href="'+ORIGIN+BASE+'/'+route+'"><script src="'+BASE+'/assets/signup.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><div class="research-banner"><span class="banner-title">RESEARCH IN PROGRESS</span><span>All project labels are provisional · no final six · nothing here is a validated product</span></div>'+header+'<main id="main">'+body+'</main>'+('' if route=='subscribe/' else signup_section())+'<footer><div><a class="brand" href="'+BASE+'/">Agent Git Lab</a><p>Alexey Grigorev · Building, testing, and changing our minds in public.</p></div><div class="footer-links"><a href="'+REPO+'">Source & evidence ↗</a><a href="'+BASE+'/research/">Research library</a><a href="'+BASE+'/feed.xml">RSS feed</a><a href="'+BASE+'/privacy/">Email privacy</a></div><p class="footer-note">Published reports are dated snapshots. Research hypotheses are not validated products. Corrections stay with the evidence.</p>'+footer_metadata+'</footer></body></html>'

def readable_cutoff(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        utc = stamp.astimezone(timezone.utc).strftime('%d %b %Y, %H:%M UTC')
        berlin = stamp.astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M %Z, Europe/Berlin')
        return utc+' / '+berlin
    except (ValueError, TypeError):
        return str(value)

def report_title(path):
    heading = re.search(r'^#\s+(.+)$', path.read_text(), re.MULTILINE)
    return heading[1] if heading else 'Orchestrator check-in'

def report_stamp(path):
    stamp = datetime.strptime(path.stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').replace(tzinfo=timezone.utc)
    return readable_cutoff(stamp.isoformat())

WHO = {
    'A01': 'an operator running parallel agent tasks at once',
    'A16': 'Alexey, and operators constrained by local disk',
    'A05': 'people who already run best-of-N agent attempts',
    'A06': 'an accountable reviewer on a team that accepts AI-written changes',
    'A10': 'an operator restarting or replacing an agent mid-task',
}

def project_tag(p):
    return 'PARKED' if str(p.get('status', '')).lower().startswith('parked') else 'PROVISIONAL'

def note_summary(path, limit=240):
    try:
        text = path.read_text()
    except OSError:
        return 'Not summarised here yet. Read the source file.'
    text = re.sub(r'^#\s+[^\n]+\n?', '', text, count=1)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('|') or line.startswith('```') or line.startswith('>'):
            continue
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
        line = re.sub(r'[*_`]+', '', line)
        if len(line) > limit:
            line = line[:limit].rsplit(' ', 1)[0] + '…'
        return line
    return 'Not summarised here yet. Read the source file.'

def note_time_day(path):
    try:
        stamp = datetime.strptime(path.stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').replace(tzinfo=timezone.utc)
    except ValueError:
        return path.stem, ''
    day = 'SAT 3 OCT' if (stamp.day == 3 and stamp.month == 10) else stamp.strftime('%a %-d %b').upper()
    return stamp.strftime('%H:%M UTC'), day

def note_dot(path, first=False):
    try:
        text = path.read_text().lower()
    except OSError:
        text = ''
    if 'fail' in path.name.lower() or 'fail' in text[:2000]:
        return '#EF7134'
    if first:
        return '#2455ED'
    return '#FCFCF8'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    def write(route, title, body, description=None):
        target = output / route / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(title, body, route, description or 'A public experiment in Git, coding agents, and the work between them.'), encoding='utf-8')
    shutil.copytree(ROOT/'website/assets', output/'assets', dirs_exist_ok=True)
    (output/'.nojekyll').write_text('')
    projects = PROJECTS
    daily = []
    for meta in sorted((ROOT/'website/content/daily').glob('*.json'), reverse=True):
        data = json.loads(meta.read_text())
        if data.get('published') is not True:
            continue
        data['path'] = meta.with_suffix('.md')
        data['route'] = 'daily/'+meta.stem+'/'
        daily.append(data)
        content = data['path'].read_text()
        content = re.sub(r'^#\s+[^\n]+\n?', '', content, count=1)
        byline = '<p class="eyebrow">Daily journal / '+E(str(data.get('date', meta.stem)))+'</p><h1>'+E(data['title'])+'</h1><p class="deck">'+E(data.get('summary', ''))+'</p><p class="byline">Alexey Grigorev · Written with Claude Opus · Evidence cutoff '+E(readable_cutoff(data.get('source_cutoff', data.get('date', meta.stem))))+'</p>'
        write(data['route'], data['title'], '<article class="article">'+byline+'<div class="prose">'+markdown(content, data['path'])+'</div><aside class="source-note">Writing assistance: Claude Opus. Sources and original Markdown: <a href="'+public_source(data['path'].relative_to(ROOT))+'">read in the repository ↗</a>. Illustration is conceptual artwork.</aside></article>', data.get('summary'))
    reports = sorted((ROOT/'research/orchestrator').glob('heartbeat-*.md'), reverse=True)
    latest_cutoff = datetime.strptime(reports[0].stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').strftime('%d %b %Y, %H:%M UTC') if reports else 'No field note published'
    def cards():
        out = []
        for p in projects:
            mark = CARD_MARKS.get(p['id'], CARD_MARKS['A01'])
            out.append('<a class="project-card hypothesis-card" href="'+BASE+'/projects/'+p['slug']+'/"><div class="card-top"><span class="card-mark" aria-hidden="true">'+mark+'</span><span class="card-tag">PROVISIONAL</span></div><div><span class="card-id">'+E(p['id'])+'</span><span class="card-name">'+E(p['name'])+'</span></div><div class="card-status"><span aria-hidden="true">'+status_mark_for(p)+'</span><span>'+E(p['status'])+'</span></div><p class="card-short">'+E(p['summary'])+'</p></a>')
        out.append('<div class="project-card hypothesis-card open-slot"><div class="card-top"><span class="card-mark" aria-hidden="true">'+CARD_MARKS['SLOT6']+'</span><span class="card-tag">OPEN</span></div><div><span class="card-id">SLOT 6</span><span class="card-name">Open slot \u2014 no replacement selected</span></div><div class="card-status"><span aria-hidden="true">'+STATUS_SVG['open']+'</span><span>Reopened \u00b7 no candidate approved</span></div><p class="card-short">A14 was folded into A01. Nothing has earned the sixth place yet.</p></div>')
        return ''.join(out)
    def report_list(items):
        return ''.join('<a class="list-row" href="'+BASE+'/reports/'+p.stem+'/"><span class="eyebrow">'+E(report_stamp(p))+'</span><span>'+E(report_title(p))+'</span><span aria-hidden="true">↗</span></a>' for p in items)
    latest = daily[0] if daily else None
    if latest:
        feature = '<article class="feature-story"><span class="eyebrow">Latest daily journal / '+E(str(latest.get('date', '')))+'</span><h1>'+E(latest['title'])+'</h1><p class="deck">'+E(latest.get('summary', ''))+'</p><p class="byline">Alexey Grigorev · Written with Claude Opus · Cutoff 2026-10-03 02:24 UTC</p><a class="text-link" href="'+BASE+'/'+latest['route']+'">Read the daily report <span aria-hidden="true">↗</span></a></article>'
    else:
        feature = '<article class="feature-story"><span class="eyebrow">The first daily journal</span><h1>What we learn belongs here.</h1><p class="deck">The opening story is being written and checked against the evidence. Read the dated field notes while it is prepared.</p><a class="text-link" href="'+BASE+'/reports/">Read the field notes <span aria-hidden="true">↗</span></a></article>'
    status_rows = [('20', 'Approaches researched', 'Independent briefs in repo'), ('2', 'Retained hypotheses', 'Provisional, for falsification (A01 conditional, A06)'), ('0', 'Agreed final six', 'Principals have not converged'), ('4', 'Product places open', 'Unfilled candidates'), ('111.7 GiB', 'Worktree disk measured', 'Across 472 worktrees'), ('62.1%', 'Dependencies & builds', 'Not ordinary Git storage')]
    honest = '<aside class="honest-status"><div class="honest-head"><span class="honest-title">Honest status</span><span class="honest-cutoff">Cutoff 2026-10-03 02:24 UTC</span></div>' + ''.join('<div class="honest-row"><span class="honest-number">'+E(n)+'</span><div class="honest-detail"><span class="honest-label">'+E(label)+'</span><span class="honest-note">'+E(note)+'</span></div></div>' for n, label, note in status_rows) + '<a class="text-link" href="'+BASE+'/checklist/">See every gate on the checklist <span aria-hidden="true">↗</span></a></aside>'
    hero = '<figure class="hero-figure"><img src="'+BASE+'/assets/agent-git-illustration.png" alt="Geometric blue agents carry folders along branching commit lines into an orange merge"><figcaption>FIG. 0 — MANY AGENTS, ONE CANONICAL HISTORY</figcaption></figure><section class="latest-section">'+feature+honest+'</section>'
    home_title = latest['title'] if latest else 'Agent Git Lab'
    storage = '<section class="pain-section"><div><span class="pain-eyebrow">MEASURED PAIN \u00b7 ONE HOST \u00b7 READ-ONLY SCAN</span><h2 class="pain-title">Most of the worktree pile isn\u2019t Git. It\u2019s dependencies.</h2><p class="pain-text">The pain is real and measured. Whether anyone would adopt a product for it is unknown. Ordinary shared stores may already be enough.</p><a class="pain-link" href="'+BASE+'/projects/storage-aware-workspaces/">A16 \u00b7 Storage-aware workspaces \u2192</a></div><div><div class="pain-stats"><div class="pain-stat"><span class="pain-stat-n">472</span><span class="pain-stat-l">linked worktrees</span></div><div class="pain-stat"><span class="pain-stat-n">25</span><span class="pain-stat-l">repositories</span></div><div class="pain-stat"><span class="pain-stat-n">111.7</span><span class="pain-stat-l">GiB physical union</span></div><div class="pain-stat"><span class="pain-stat-n">62.1%</span><span class="pain-stat-l">dependencies + build</span></div></div><div><div class="pain-bar"><div class="pain-bar-fill"></div><div class="pain-bar-rest"></div></div><div class="pain-caps"><span>62.1% DEPENDENCY + BUILD (69.4 GIB)</span><span class="dim">SOURCE + OTHER ~42 GIB</span></div><div class="pain-unknown"><span aria-hidden="true">'+STATUS_SVG['unknown']+'</span><span>Product viability: unknown</span></div></div></div></section>'
    home_fields = ''.join('<a class="field-row" href="'+BASE+'/reports/'+rp.stem+'/"><span class="field-time">'+E(rp.stem.removeprefix('heartbeat-')[9:11]+':'+rp.stem.removeprefix('heartbeat-')[11:13]+' UTC')+'</span><span class="field-title">'+E(report_title(rp))+'</span></a>' for rp in reports[:4])
    home_libs = [('Shortlist draft 7 (unsigned)', 'research/shortlist-6.md'), ('Worktree disk on the real host', 'research/claude/u7-real-worktree-measurement.md'), ('Consensus record \u2014 pending', 'research/consensus.md'), ('All 20 approaches', 'research/approaches-20.md')]
    home_lib_rows = ''.join('<a class="lib-row" href="'+public_source(rel)+'"><span class="lib-title">'+E(t)+'</span><span class="lib-path">'+E(rel)+'</span></a>' for t, rel in home_libs)
    home_bottom = '<section class="home-bottom"><div class="home-col"><div class="home-col-head"><h2>Field notes</h2><a class="pain-link" href="'+BASE+'/reports/">Archive \u2192</a></div><span class="home-col-sub">Orchestrator checks every 30 minutes. Times in UTC.</span>'+home_fields+'</div><div class="home-col"><div class="home-col-head"><h2>Research library</h2><a class="pain-link" href="'+BASE+'/research/">All sources \u2192</a></div><span class="home-col-sub">Everything links to a file in the public repo.</span>'+home_lib_rows+'</div></section>'
    home_html = hero+'<section><div class="section-heading"><div><p class="eyebrow">The project notebook</p><h2>'+str(ACTIVE_COUNT)+' active ideas. '+str(PARKED_COUNT)+' parked candidates.</h2></div><p>Each gets its own problem, evidence, and next test. None has earned a product claim yet.</p></div><div class="projects-grid">'+cards()+'</div></section>'+storage+home_bottom
    write('', home_title, home_html)
    daily_rows = ''.join('<a class="journal-entry" href="'+BASE+'/'+d['route']+'"><span class="eyebrow">'+E(str(d.get('date', '')))+'</span><h2>'+E(d['title'])+'</h2><p>'+E(d.get('summary', ''))+'</p><span class="text-link">Read the story ↗</span></a>' for d in daily)
    write('daily/', 'Daily journal', '<section class="page-intro"><p class="eyebrow">A story each day</p><h1>The daily journal.</h1><p class="deck">What we tried, what held up, and what changed our minds. Written with Claude Opus, checked against the experiment.</p><a href="'+BASE+'/feed.xml">Subscribe via RSS ↗</a></section><section class="journal-list">'+(daily_rows or '<p>The first evidence-checked story is being prepared.</p>')+'</section>')
    write('projects/', 'Projects', '<section class="page-intro"><p class="eyebrow">Retained research hypotheses</p><h1>Ideas with work to do.</h1><p class="deck">Five directions are under investigation. Selection and development gates are separate; these are provisional research lanes.</p></section><section class="projects-grid">'+cards()+'</section>')
    short_sha = BUILD_SHA[:7] if BUILD_SHA else '1c6c7db'
    for i, p in enumerate(projects):
        prev = projects[(i - 1) % len(projects)]
        nxt = projects[(i + 1) % len(projects)]
        tag = project_tag(p)
        who = WHO.get(p['id'], 'the operator named in the research')
        body = (
            '<article class="hypo-detail"><div class="hypo-crumb"><a href="'+BASE+'/projects/">Hypotheses</a><span>/</span><span class="hypo-crumb-id">'+E(p['id'])+'</span></div>'
            '<div class="hypo-top"><div class="hypo-left">'
            '<div class="badge-row"><span class="hypo-id">'+E(p['id'])+'</span><span class="hypo-tag">'+E(tag)+'</span></div>'
            '<h1 class="hypo-title">'+E(p['name'])+'</h1>'
            '<div class="hypo-status"><span class="hypo-mark" aria-hidden="true">'+status_mark_for(p)+'</span><span>'+E(p['status'])+'</span></div>'
            '<div class="hypo-meta"><span>PROVISIONAL · NO FINAL SHORTLIST APPROVAL</span><span>STATUS AS OF 2026-10-03 02:24 UTC</span><span>SOURCE projects.json @ '+E(short_sha)+'</span></div>'
            '</div>'
            '<figure class="hypo-fig"><div class="hypo-scene"><img src="'+BASE+'/assets/'+E(p['slug'], quote=True)+'-workflow.svg" alt="'+E(p['name'], quote=True)+' proposed workflow"></div>'
            '<figcaption>FIG. '+E(p['id'])+' — PROPOSED WORKFLOW, NOT VALIDATED</figcaption></figure></div>'
            '<div class="hypo-body">'
            '<section class="hypo-sec"><span class="hypo-secnum">01 · PROBLEM</span><p class="hypo-problem">'+E(p['problem'])+'</p><span class="hypo-who">Who: '+E(who)+'</span></section>'
            '<section class="hypo-sec"><span class="hypo-secnum">02 · HYPOTHESIS</span><p class="hypo-text">'+E(p['idea'])+'</p></section>'
            '<section class="hypo-sec"><span class="hypo-secnum">03 · EVIDENCE SO FAR</span>'
            '<div class="ev-row"><div class="ev-mark"><span aria-hidden="true">'+status_mark_for(p)+'</span><span class="ev-label">EVIDENCE</span></div>'
            '<div class="ev-detail"><span class="ev-text">'+E(p['evidence'])+'</span><a class="ev-src" href="'+public_source('research/shortlist-6.md')+'">research/shortlist-6.md</a></div></div>'
            '</section>'
            '<section class="hypo-sec test-box"><span class="hypo-secnum">04 · NEXT FALSIFICATION TEST</span><p class="hypo-text">'+E(p['test'])+'</p>'
            '<div class="test-grid"><div class="test-cell"><span class="test-k">DUE</span><span class="test-v">See selection draft; dates on the checklist</span></div>'
            '<div class="test-cell"><span class="test-k">KILL / PARK IF</span><span class="test-v">'+E(p['falsifier'])+'</span></div></div></section>'
            '<section class="hypo-sec"><span class="hypo-secnum">05 · PUBLIC SOURCES</span><div class="src-list">'
            '<a href="'+public_source('research/shortlist-6.md')+'">research/shortlist-6.md</a>'
            '<a href="'+public_source('research/approaches-20.md')+'">research/approaches-20.md</a>'
            '<a href="'+BASE+'/checklist/">checklist/ · shared validation gates</a>'
            '</div></section>'
            '<div class="hypo-nav"><a href="'+BASE+'/projects/'+E(prev['slug'], quote=True)+'/">← '+E(prev['id']+' · '+prev['name'])+'</a>'
            '<a href="'+BASE+'/projects/'+E(nxt['slug'], quote=True)+'">'+E(nxt['id']+' · '+nxt['name'])+' →</a></div>'
            '</div></article>'
        )
        write('projects/'+p['slug']+'/', p['name'], body, p['summary'])
    notes_entries = []
    for idx, rp in enumerate(reports):
        t, day = note_time_day(rp)
        dot = note_dot(rp, first=(idx == 0))
        top = 'transparent' if idx == 0 else '#1C2027'
        notes_entries.append(
            '<div class="note-entry"><div class="note-rail" aria-hidden="true">'
            '<div class="note-line-top" style="background:'+top+'"></div>'
            '<div class="note-dot" style="background:'+dot+'"></div>'
            '<div class="note-line"></div></div>'
            '<a class="note-body" href="'+public_source(rp.relative_to(ROOT))+'">'
            '<div class="note-when"><span class="note-time">'+E(t)+'</span><span class="note-day">'+E(day)+'</span></div>'
            '<span class="note-title">'+E(report_title(rp))+'</span>'
            '<span class="note-summary">'+E(note_summary(rp))+'</span>'
            '<span class="note-path">'+E(str(rp.relative_to(ROOT)))+'</span>'
            '</a></div>'
        )
    write('reports/', 'Field notes', '<section class="notes-head"><p class="hypo-secnum">FIELD NOTES · EVERY 30 MINUTES · UTC</p><h1 class="notes-title">The heartbeat log</h1><p class="deck">The orchestrator checks evidence, quotas and disk every half hour and writes it down. Notes without a summary here have one in the source file.</p></section><section class="notes-list">'+''.join(notes_entries)+'</section>')
    for report in reports:
        write('reports/'+report.stem+'/', report_title(report)+' — '+report_stamp(report), '<article class="article field-report"><p class="eyebrow">Historical field note / '+E(report_stamp(report))+'</p><h1>'+E(report_title(report))+'</h1><aside class="source-note">This is a dated evidence snapshot, not current product validation. <a href="'+public_source(report.relative_to(ROOT))+'">Original report and version history ↗</a></aside><div class="prose">'+markdown(re.sub(r'^#\s+[^\n]+\n?', '', report.read_text(), count=1), report)+'</div></article>')
    groups = []
    for group in ['orchestrator', 'claude', 'codex', 'grok', 'antigravity', 'zcode', 'space-bunny', 'muse', 'debate']:
        paths = sorted((ROOT/'research'/group).rglob('*.md'))
        paths = [p for p in paths if not any(part.startswith('.') for part in p.relative_to(ROOT).parts)]
        if paths:
            groups.append('<details><summary>'+E(group.replace('-', ' ').title())+' <span>'+str(len(paths))+' documents</span></summary><ul>'+''.join('<li><a href="'+public_source(p.relative_to(ROOT))+'">'+E(str(p.relative_to(ROOT/'research'/group)))+'</a></li>' for p in paths)+'</ul></details>')
    top = sorted((ROOT/'research').glob('*.md'))
    write('research/', 'Research library', '<section class="page-intro"><p class="eyebrow">The public source material</p><h1>Open the notebooks.</h1><p class="deck">Research, challenges, and evidence live in the public repository. Private agent logs and credentials are excluded.</p></section><section class="library"><h2>Selection and shared research</h2><ul>'+''.join('<li><a href="'+public_source(p.relative_to(ROOT))+'">'+E(p.stem.replace('-', ' '))+'</a></li>' for p in top)+'</ul>'+''.join(groups)+'</section>')
    STATE_LABEL = {'recorded': 'DONE', 'done': 'DONE', 'failed': 'FAILED', 'open': 'OPEN', 'withdrawn': 'WITHDRAWN', 'pending': 'PENDING'}
    STATE_MARK = {'recorded': STATUS_SVG['pending'], 'done': STATUS_SVG['pending'], 'failed': '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="#EF7134"/><path d="M5.5 5.5 L10.5 10.5 M10.5 5.5 L5.5 10.5" stroke="#1C2027" stroke-width="2" stroke-linecap="round"/></svg>', 'open': STATUS_SVG['open'], 'withdrawn': STATUS_SVG['withdrawn'], 'pending': STATUS_SVG['pending']}
    gate_groups = [
        ('Research gates', [
            ('recorded', '20 approaches written', 'The research inventory is public. Scores and the original shortlist are historical, not final approval.', '2 Oct', 'research/approaches-20.md'),
            ('recorded', 'Two bilateral debate rounds', 'Both principals recorded challenges and responses.', '2 Oct', 'research/debate/'),
            ('recorded', 'Five ChatGPT Pro investigations arrived and mapped', 'First primary-source checks done.', '2 Oct', 'research/codex/pro-integration-round-1.md'),
            ('recorded', 'A14 folded into A01 verification', 'Codex proposal, Claude accept; local isolation tied ordinary control. Folded into A01 verification.', '2 Oct', 'research/consensus.md'),
            ('recorded', 'Worktree pain measured on the real host', 'Read-only scan: 472 trees, 111.7 GiB; corrected 80% to 62.1%.', '2 Oct', 'research/claude/u7-real-worktree-measurement.md'),
            ('withdrawn', 'A18 Contract Packs demand scout', 'Demand scout completed; A18 jointly provisionally parked as a competition-resource decision (01a10083-4069 / 01a10084-182f; TASKS a18-demand-scout CLOSED-PARK) — a recommendation, not a validated kill; no slot filled.', '3 Oct', 'coordination/TASKS.json'),
            ('recorded', 'A09 publication receipts refinement', 'Duplicate-exec existence verified (codex#27283, claude-code#10319); Bunny incumbent check reported narrow GAP; parked with kill test pending.', '3 Oct', 'research/approaches-20.md'),
            ('pending', 'Remaining citation and competitor checks', 'Pending per consensus record.', '—', 'research/consensus.md'),
        ]),
        ('Hypothesis gates', [
            ('withdrawn', 'A01 as primary recommendation', 'Null separation in the equal-policy live pair (D-G25); zero hazard, zero repair in both arms. Mutual correction.', '2 Oct', 'research/shortlist-6.md'),
            ('failed', 'A16 tiny-task N2 footprint reduction >50%', 'Measured 48.17% against the registered gate; limited fixture.', '2 Oct', 'research/codex/retained-lanes-review-2324.md'),
            ('withdrawn', 'A16 parked as competition product', 'Corrected cache-inclusive N=2 benchmark reached 47.76% vs >50% gate (clone 47.38%). Joint principal park; host advice survives.', '3 Oct', 'research/antigravity/r8-worktree-d1-benchmark.md'),
            ('withdrawn', 'A10 provisionally parked as product candidate', 'Joint principal decision (01a1003c/01a1003d); cold consumers recovered easily from ordinary Git/files (Muse 27s; Muse R4 on Bunny task 39/39 tests). Reopen requires first-hand Git-bound gap.', '3 Oct', 'research/shortlist-6.md'),
            ('withdrawn', 'A05 provisionally parked as product candidate', 'Joint principal portfolio decision (01a1005f/01a10064); same-task attempts showed no selection advantage. Independent adjudication completed 3 Oct: bounded static TIE, no winner (01a10080-8e21 / 01a100aa-a681); provisionally parked (CLOSED-PARK).', '3 Oct', 'coordination/TASKS.json'),
            ('failed', 'Duplicate-execution runtime regression', 'Expected one side effect, saw zero; 0 passed / 1 failed. Not a fix.', '3 Oct 02:24 UTC', 'research/orchestrator/heartbeat-20261003T0224.md'),
            ('pending', 'A01 local live-agent warning uptake', 'Registered v0.3 plan superseded by the frozen R12/v2.2 protocol (9412520), conditionally approved by both principals for 3 unscored pairs only; all A01 trials remain HOLD pending a non-author known-good BASE positive; real warning-consumption and Workers/Artifacts gates pending.', 'due 5 Oct', 'research/codex/oversight-human31.md'),
            ('pending', 'A01 remote full-loop attempt', 'Full Workers/Artifacts loop with live agents.', 'due 7 Oct', 'research/shortlist-6.md'),
            ('pending', 'A06 review comparison with controlled raw access', 'First real N=1 decision showed no verdict change; calibration experiment returned REJECT in both arms. Controlled comparative trial pending.', 'due 8 Oct', 'research/shortlist-6.md'),
        ]),
        ('Platform & model gates', [
            ('pending', 'Real concurrent-agent Workers/Artifacts gate', '0 of 2 retained hypotheses (A01, A06) have passed a real concurrent-agent demo.', '—', 'research/shortlist-6.md'),
            ('open', 'Four unfilled shortlist places', 'Four places open after A16, A10, A05 parks and A14 fold; no replacement approved.', '3 Oct', 'research/shortlist-6.md'),
            ('pending', 'Both principals sign off identical shortlist digest', 'Current draft unsigned by both principals.', '—', 'research/shortlist-6.md'),
            ('pending', 'Submission: 5–10 minute demo + run instructions', 'Permissive source with run instructions and video.', 'due 14 Oct', 'BRIEF.md'),
        ]),
    ]
    counts = {}
    for _, items in gate_groups:
        for state, *_ in items:
            key = 'done' if state == 'recorded' else state
            counts[key] = counts.get(key, 0) + 1
    legend_order = [('done', 'DONE'), ('pending', 'PENDING'), ('failed', 'FAILED'), ('withdrawn', 'WITHDRAWN'), ('open', 'OPEN')]
    legend = ''.join(
        '<div class="legend-item"><span aria-hidden="true">'+STATE_MARK['pending' if k == 'done' else k]+'</span><span class="legend-label">'+label+'</span><span class="legend-count">'+str(counts.get(k, 0))+'</span></div>'
        for k, label in legend_order
    )
    group_html = ''
    for gtitle, items in gate_groups:
        rows = []
        for state, title, note, date, src in items:
            label = STATE_LABEL.get(state, state.upper())
            tint = ' gate-tinted' if state in ('failed', 'withdrawn') else ''
            src_url = public_source(src)
            rows.append(
                '<div class="gate-row'+tint+'"><div class="gate-main"><span class="gate-mark" aria-hidden="true">'+STATE_MARK.get(state, STATUS_SVG['pending'])+'</span>'
                '<div class="gate-text"><span class="gate-title">'+E(title)+'</span><span class="gate-note">'+E(note)+'</span></div></div>'
                '<div class="gate-meta"><span class="gate-state">'+E(label)+' · '+E(date)+'</span><a class="gate-src" href="'+E(src_url, quote=True)+'">'+E(src)+'</a></div></div>'
            )
        group_html += '<section class="gate-group"><h2 class="gate-group-title">'+E(gtitle)+'</h2>'+''.join(rows)+'</section>'
    write('checklist/', 'Experiment checklist', '<section class="check-head"><p class="hypo-secnum">CHECKLIST · READ-ONLY · CHANGES ONLY BY COMMIT</p><h1 class="notes-title">Gates, with dates</h1><p class="deck">A gate is a test we registered before running it. It passes, fails, or waits. Nothing on this page is a progress bar.</p></section><div class="legend-strip">'+legend+'</div>'+group_html+'<p class="source-note">Snapshot built '+BUILD_TIME+'. Latest field-note cutoff: '+E(latest_cutoff)+'. Status comes from the published selection draft and orchestrator reports. <a href="'+public_source('research/shortlist-6.md')+'">Inspect the selection gates ↗</a></p>')
    write('experiment/', 'About the experiment', '<article class="article"><p class="eyebrow">Why this exists</p><h1>Build it. Test it.<br>Tell the whole story.</h1><p class="deck">A new Git platform competition prompted a wider question: where does Git make a team of coding agents harder to run?</p><div class="prose"><h2>Start with actual pain</h2><p>Alexey’s worktrees filled disk quickly. A read-only scan found 472 linked worktrees across 25 repositories, occupying a physical union of 111.7 GiB. Dependencies and builds accounted for 69.4 GiB, or 62.1%. These are measurements from one host, not a claim about every developer.</p><h2>Let the agents challenge each other</h2><p>Claude and Codex principals monitor and challenge evidence. Project heads coordinate useful tasks, and task executors can work headless. The team is free to improve its working method, while preserving quotas, code recovery, and privacy.</p><figure><picture><source media="(max-width: 600px)" srcset="'+BASE+'/assets/team-workflow-mobile.svg"><img src="'+BASE+'/assets/team-workflow.svg" alt="Team workflow: Alexey and remote oversight connect to Claude and Codex principals, project heads, task executors, evidence, and review."></picture><figcaption>The operating model. Arrows show responsibilities, not proof of continuous activity.</figcaption></figure><h2>Keep the failures visible</h2><p>Research is not product validation. No final six-approach shortlist has been approved. The first live integration comparison showed no separation, so that idea’s primary status was withdrawn. A small storage experiment fell below its registered savings gate.</p><h2>Use what survives</h2><p>Teams should build the smallest useful prototype and use it in their own development. Accepted outcomes, peer review, and recoverable Git history matter more than a launch count.</p><p><a href="'+public_source('experiment/USER-INSTRUCTIONS.md')+'">The original user brief ↗</a> · <a href="'+public_source('AGENTS.md')+'">How the agents are expected to work ↗</a> · <a href="https://blog.cloudflare.com/next-git-platform-on-cloudflare/">The competition that started it ↗</a></p></div></article>')
    write('subscribe/', 'Confirm your experiment updates', '<section class="page-intro"><p class="eyebrow">A separate, confirmed opt-in</p><h1>Stay with the experiment.</h1><p class="deck">Sign up for Agent Git Lab updates, or use the confirmation link from your inbox. This list is separate from PocketShell and other newsletters.</p></section>'+signup_section(dedicated=True))
    write('privacy/', 'Email privacy', '<article class="article"><p class="eyebrow">Email opt-in</p><h1>Your address stays private.</h1><div class="prose"><h2>What you are signing up for</h2><p>Agent Git Lab experiment updates: useful findings, project progress, and corrections. A signup does not enroll you in PocketShell or another newsletter. You can read daily reports in the journal; the email list is for occasional experiment updates.</p><h2>Confirmation and storage</h2><p>We use DataTalks.Club Relay, the same public double opt-in flow used by PocketShell. Your email address and pending or confirmed subscription state are stored in a separate Agent Git Lab audience. Relay sends a confirmation link; you join the confirmed list only after using it.</p><p>The website sends your address directly to the fixed Relay signup endpoint. No client API key is placed in the page. We do not put submitted addresses or confirmation tokens into the public repository, research reports, agent prompts, or browser storage.</p><h2>Leaving the list</h2><p>You can ignore a confirmation you did not request. Unsubscribe through the link in an update email. Repeated requests can be rate limited; that is separate from confirmation.</p><h2>Website and service requests</h2><p>The website is hosted on GitHub Pages and the email flow is handled by Relay. Those services process the requests needed to deliver the page and manage the opt-in, including their ordinary operational records. No visitor analytics or public signup telemetry is added by this form.</p><p><a href="'+BASE+'/subscribe/">Back to signup</a> · <a href="https://github.com/DataTalksClub/relay">Relay source</a></p></div></article>')
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    for tag, value in [('title','Agent Git Lab — Daily journal'),('link',ORIGIN+BASE+'/'),('description','The experiments, failures, and decisions behind Git for coding agents.')]:
        ET.SubElement(channel, tag).text = value
    for d in daily:
        item = ET.SubElement(channel, 'item')
        for tag,value in [('title',d['title']),('link',ORIGIN+BASE+'/'+d['route']),('guid',ORIGIN+BASE+'/'+d['route']),('description',d.get('summary',''))]:
            ET.SubElement(item, tag).text = value
    ET.ElementTree(rss).write(output/'feed.xml', encoding='utf-8', xml_declaration=True)
    print(json.dumps({'output':str(output),'html_pages':len(list(output.rglob('*.html'))),'published_daily':len(daily),'field_notes':len(reports),'projects':len(projects)}))

if __name__ == '__main__':
    main()
