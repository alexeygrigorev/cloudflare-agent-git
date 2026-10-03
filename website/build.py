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
    links = [('Journal', 'daily/'), ('Projects', 'projects/'), ('Field notes', 'reports/'), ('Checklist', 'checklist/'), ('About', 'experiment/')]
    footer_metadata = '<p class="build-metadata">Site built '+BUILD_TIME+(' · <a href="'+REPO+'/commit/'+BUILD_SHA+'">Source revision '+BUILD_SHA[:12]+' ↗</a>' if BUILD_SHA else ' · Source revision unavailable')+'</p>'
    cutoff_files = sorted((ROOT/'research/orchestrator').glob('heartbeat-*.md'), reverse=True)
    if cutoff_files:
        stamp = datetime.strptime(cutoff_files[0].stem.removeprefix('heartbeat-'), '%Y%m%dT%H%M').replace(tzinfo=timezone.utc)
        footer_metadata += '<p class="build-metadata">Latest field-note cutoff: '+E(readable_cutoff(stamp.isoformat()))+'. Evidence is dated; build time is not a live agent status.</p>'
    nav = ''.join('<a '+('aria-current="page" ' if route.startswith(path) else '')+'href="'+BASE+'/'+path+'">'+label+'</a>' for label,path in links)
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+' · Agent Git Lab</title><meta name="description" content="'+E(description, quote=True)+'"><meta name="theme-color" content="#2455ed"><link rel="stylesheet" href="'+BASE+'/assets/site.css"><link rel="alternate" type="application/rss+xml" title="Agent Git Lab journal" href="'+BASE+'/feed.xml"><link rel="canonical" href="'+ORIGIN+BASE+'/'+route+'"><script src="'+BASE+'/assets/signup.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><div class="research-banner">Research in progress <span>Five hypotheses · no final shortlist approval</span></div><header class="site-header"><a class="brand" href="'+BASE+'/"><span class="brand-mark" aria-hidden="true">●</span> Agent Git Lab<span class="brand-caption">an experiment in public</span></a><nav aria-label="Main navigation">'+nav+'</nav></header><main id="main">'+body+'</main>'+('' if route=='subscribe/' else signup_section())+'<footer><div><a class="brand" href="'+BASE+'/">Agent Git Lab</a><p>Alexey Grigorev · Building, testing, and changing our minds in public.</p></div><div class="footer-links"><a href="'+REPO+'">Source & evidence ↗</a><a href="'+BASE+'/research/">Research library</a><a href="'+BASE+'/feed.xml">RSS feed</a><a href="'+BASE+'/privacy/">Email privacy</a></div><p class="footer-note">Published reports are dated snapshots. Research hypotheses are not validated products. Corrections stay with the evidence.</p>'+footer_metadata+'</footer></body></html>'

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
    projects = json.loads((ROOT/'website/projects.json').read_text())
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
        return ''.join('<a class="project-card" href="'+BASE+'/projects/'+p['slug']+'/"><span class="eyebrow">'+p['id']+' / research hypothesis</span><h3>'+E(p['name'])+'</h3><p>'+E(p['summary'])+'</p><span class="card-bottom">'+E(p['status'])+' <span aria-hidden="true">↗</span></span></a>' for p in projects)
    def report_list(items):
        return ''.join('<a class="list-row" href="'+BASE+'/reports/'+p.stem+'/"><span class="eyebrow">'+E(report_stamp(p))+'</span><span>'+E(report_title(p))+'</span><span aria-hidden="true">↗</span></a>' for p in items)
    latest = daily[0] if daily else None
    story = '<a class="feature-story" href="'+BASE+'/'+latest['route']+'"><span class="eyebrow">Latest daily journal / '+E(str(latest.get('date', '')))+'</span><h2>'+E(latest['title'])+'</h2><p>'+E(latest.get('summary', ''))+'</p><span class="text-link">Read the story ↗</span></a>' if latest else '<div class="feature-story"><span class="eyebrow">The first daily journal</span><h2>What we learn belongs here.</h2><p>The opening story is being written and checked against the evidence. Read the dated field notes while it is prepared.</p><a class="text-link" href="'+BASE+'/reports/">Read the field notes ↗</a></div>'
    hero = '<section class="hero"><div class="hero-copy"><p class="eyebrow">Git × coding agents × real work</p><h1>More agents.<br>Better work?</h1><p class="deck">We’re exploring what Git should feel like when a team includes coding agents. The ideas, experiments, dead ends, and decisions are all here.</p><a class="button" href="'+BASE+'/daily/">Follow the experiment <span aria-hidden="true">↗</span></a><a class="quiet-link" href="'+BASE+'/experiment/">How we work</a></div><figure class="hero-art"><img src="'+BASE+'/assets/agent-git-illustration.png" alt="Conceptual illustration: blue agent markers, Git branches, copied folders, and a shared graph."><figcaption>Isolation has a cost. Coordination does too.</figcaption></figure></section>'
    storage = '<section class="storage-note"><div><p class="eyebrow">One measured starting point / U7 host scan</p><h2>Where the disk went.</h2><p>The original pain was real: worktrees filled the disk. Most measured bytes came from dependencies and builds, which challenges the idea that a new Git platform is the first remedy.</p><a class="text-link" href="'+BASE+'/projects/storage-aware-workspaces/">Follow the storage research ↗</a></div><div class="storage-measures"><div><span class="measure-number">111.7 <small>GiB</small></span><span>Physical union across 472 worktrees</span></div><div><span class="measure-number">62.1 <small>%</small></span><span>Dependencies and builds: 69.4 GiB</span></div><p>One host, 25 repositories. Physical union includes deduplication; these figures are not reclaimable-byte promises.</p></div></section>'
    write('', 'More agents. Better work?', hero+'<section class="latest-section">'+story+'<aside class="margin-note"><span class="eyebrow">Selection is still open</span><p class="big-number">20 → 5 + ?</p><p>Twenty approaches explored. Five hypotheses retained. A sixth slot remains open; no final shortlist has been signed.</p><a href="'+BASE+'/checklist/">See the gates ↗</a><p class="cutoff">Latest field note<br>'+E(latest_cutoff)+'<br>Dated evidence, not live status.</p></aside></section><section><div class="section-heading"><div><p class="eyebrow">The project notebook</p><h2>Five ideas worth testing.</h2></div><p>Each gets its own problem, evidence, and next test. None has earned a product claim yet.</p></div><div class="projects-grid">'+cards()+'<div class="project-card open-slot"><span class="eyebrow">Sixth slot / open</span><h3>A useful idea beats a filled slot.</h3><p>We will add another approach when the evidence supports it.</p><a href="'+public_source('research/shortlist-6.md')+'">Read the selection draft ↗</a></div></div></section>'+storage+'<section class="notes-section"><div class="section-heading"><div><p class="eyebrow">Behind the daily story</p><h2>The regular check-ins.</h2></div><a href="'+BASE+'/reports/">All field notes ↗</a></div>'+report_list(reports[:4])+'</section>')
    daily_rows = ''.join('<a class="journal-entry" href="'+BASE+'/'+d['route']+'"><span class="eyebrow">'+E(str(d.get('date', '')))+'</span><h2>'+E(d['title'])+'</h2><p>'+E(d.get('summary', ''))+'</p><span class="text-link">Read the story ↗</span></a>' for d in daily)
    write('daily/', 'Daily journal', '<section class="page-intro"><p class="eyebrow">A story each day</p><h1>The daily journal.</h1><p class="deck">What we tried, what held up, and what changed our minds. Written with Claude Opus, checked against the experiment.</p><a href="'+BASE+'/feed.xml">Subscribe via RSS ↗</a></section><section class="journal-list">'+(daily_rows or '<p>The first evidence-checked story is being prepared.</p>')+'</section>')
    write('projects/', 'Projects', '<section class="page-intro"><p class="eyebrow">Retained research hypotheses</p><h1>Ideas with work to do.</h1><p class="deck">Five directions are under investigation. Selection and development gates are separate; these are provisional research lanes.</p></section><section class="projects-grid">'+cards()+'</section>')
    for p in projects:
        body = '<article class="project-landing"><p class="eyebrow">'+p['id']+' / '+E(p['status'])+'</p><h1>'+E(p['name'])+'</h1><p class="deck">'+E(p['summary'])+'</p><div class="status-strip">Provisional hypothesis · No final shortlist approval</div><figure class="hypothesis-diagram"><img src="'+BASE+'/assets/'+p['slug']+'-workflow.svg" alt="'+E(p['name'], quote=True)+' proposed workflow: '+E(p['idea'], quote=True)+'"><figcaption>Proposed workflow — not validated. Arrows describe the hypothesis, not measured uptake or a finished product.</figcaption></figure><div class="project-detail"><section><h2>The problem</h2><p>'+E(p['problem'])+'</p><h2>The working idea</h2><p>'+E(p['idea'])+'</p><h2>What the evidence says</h2><p>'+E(p['evidence'])+'</p><h2>The next useful test</h2><p>'+E(p['test'])+'</p><h2>What would change our mind</h2><p>'+E(p['falsifier'])+'</p></section><aside class="project-sidebar"><span class="eyebrow">Experiment record</span><p>Read the original research before treating an illustration, fixture, or proposal as a working product.</p><a href="'+public_source('research/shortlist-6.md')+'">Current selection draft ↗</a><a href="'+public_source('research/approaches-20.md')+'">All twenty approaches ↗</a><a href="'+BASE+'/checklist/">Shared validation checklist ↗</a></aside></div><a class="text-link" href="'+BASE+'/projects/">← All projects</a></article>'
        write('projects/'+p['slug']+'/', p['name'], body, p['summary'])
    write('reports/', 'Field notes', '<section class="page-intro"><p class="eyebrow">The regular reports</p><h1>Field notes, with receipts.</h1><p class="deck">Dated remote check-ins, including failures and corrections. Older reports describe what was known then; read later updates before reusing a claim.</p></section><section class="report-list">'+report_list(reports)+'</section>')
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
    checks = [('recorded','Explore twenty distinct approaches','The research inventory is public. Scores and the original shortlist are historical, not final approval.'),('recorded','Challenge assumptions from both sides','Independent principals challenge outputs, methods, and the human brief. A01 lost its primary recommendation.'),('open','Agree on six viable approaches','Five hypotheses are retained; slot six is open. Identical-digest approval from both principals is still required.'),('open','Demonstrate actual agent use','Show a useful task, real agent actions, and accepted outcomes. A scripted fixture alone does not pass.'),('open','Prove an advantage over ordinary tools','Compare equal tasks, information, and acceptance checks. Preserve ties, failures, and negative results.'),('open','Keep development recoverable','Ordinary Git recovery stays independent of the prototype. A source-only restore is limited evidence.'),('open','Hand off five productive project teams','Verify meaningful deliverables, independent ownership, and an actual next task; a live process is insufficient.'),('recorded' if daily else 'open','Publish evidence-checked daily stories','First report published and the daily 09:30 Europe/Berlin workflow configured. Ongoing daily continuity remains to be verified.' if daily else 'Claude Opus writes with stylint; factual claims, diagrams, and illustrations are checked before publishing.')]
    checks += [('recorded','A01 primary recommendation withdrawn','Decision at the 03 October 2026, 02:24 UTC evidence cutoff: both principals withdrew primary status after the fair live comparison showed no separation. This does not prove warnings can never help.'),('failed','Storage test below its registered gate','At that cutoff, clean-identical-cache N2 whole-footprint savings were 48.17%, below the registered greater-than-50% gate. This is a limited fixture, not safe savings from existing worktrees.'),('failed','Runtime regression still failed','The 02:24 UTC field note records zero passing tests and one failure: COUNT 0 where COUNT 1 was expected. Full patched one-effect runtime integration remained unproven at that cutoff.')]
    write('checklist/', 'Experiment checklist', '<section class="page-intro"><p class="eyebrow">What earns a claim</p><h1>The checklist.</h1><p class="deck">A public view of the gates, not a score for how many agents we can launch. Project teams test their hypotheses while selection continues.</p></section><p class="source-note">Snapshot built '+BUILD_TIME+'. Latest field-note cutoff: '+E(latest_cutoff)+'. Daily publication: '+('first report recorded; continuing daily reliability unproven' if daily else 'first report pending')+'.</p><section class="checklist">'+''.join('<div class="check-item"><span class="check-symbol '+state+'" aria-hidden="true">'+({'recorded':'●','failed':'×'}.get(state,'○'))+'</span><div><span class="eyebrow">'+({'recorded':'Work recorded','failed':'Gate not passed'}.get(state,'Evidence still needed'))+'</span><h2>'+E(title)+'</h2><p>'+E(desc)+'</p></div></div>' for state,title,desc in checks)+'</section><p class="source-note">Status comes from the published selection draft and orchestrator reports. '+('<a href="'+BASE+'/'+daily[0]['route']+'">First daily story ↗</a> · ' if daily else '')+'<a href="'+public_source('research/shortlist-6.md')+'">Inspect the selection gates ↗</a></p>')
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
