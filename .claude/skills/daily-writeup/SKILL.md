---
name: daily-writeup
description: Write the public daily report for the Agent Branches journal (website/content/daily/YYYY-MM-DD.md). Use for every daily report, rewrite or correction of a daily page. Claude Opus only.
---

# Daily write-up

The daily report is a short story for human readers who don't follow the experiment. It isn't a log for agents. These rules come straight from Alexey. This skill is the one source for the journal's writing and visual rules, and it overrides any conflicting rule in older editorial notes, the writer prompt or a fact packet.

## Who writes

- Only Claude Opus writes or rewrites the article. Run it as `claude --model opus`, and check that the response's `modelUsage` includes an Opus model. The Opus session writes the article itself and doesn't delegate it to a subagent.
- The coordinating agent doesn't write prose itself and doesn't hand the writing to Codex, Gemini, Grok, z.ai or Sonnet. If Opus can't run because of quota or an error, keep the last published article and report the problem. Don't publish a substitute.
- Other models may check facts, but Opus makes every prose change.
- Voice: Alexey's Substack build log. Read the private guide `../telegram-writing-assistant/articles/_meta/substack-writing-style.md`, two of his published articles and `stylint --style-guide alexey`. Never copy that archive or Telegram data into the repo.

## Two steps, then publish

`python3 website/write_daily.py --date YYYY-MM-DD` runs both steps as separate Claude Opus sessions:

1. Write-up: an Opus session writes the article, metadata, share text and illustrations by following this skill.
2. Check pass: a fresh Opus session checks the draft against this skill and the sources. It rewrites whatever fails and leaves the rest alone, then records its verdict in `.local/journal/YYYY-MM-DD/check.json`.

After step 2, the article is ready. Principals and heads don't re-review or edit it. The coordinating agent only confirms that both sessions ran on Opus and that `check.json` exists, then runs `python3 website/publish_daily.py YYYY-MM-DD --publish`, commits the daily files and assets, and pushes.

The coordinator then sends the laptop orchestrator one message with the article's public link and the social summary below. In the morning, the laptop orchestrator shows Alexey the link and the summary, ready to copy. It doesn't review or edit either one.

The writer produces these files and nothing else:

- `website/content/daily/YYYY-MM-DD.md`, the article. The date is the Berlin date.
- `YYYY-MM-DD.json` next to it: title, date, summary, author "Alexey Grigorev", the actual Opus model, `source_cutoff` (timezone-aware, metadata only), `sources` (https links), image, image_alt and `published: false`. The publish script fills in the publish fields and keeps the first `published_at`.
- `YYYY-MM-DD.sharetext.txt`, one or two plain sentences, at most 350 characters (`publish_daily.py` refuses longer). It's a public line, not the social post.
- The private `social.md` below, the section illustrations in `website/assets/YYYY-MM-DD-*` and their diagram sources in `website/editorial/diagrams/YYYY-MM-DD/`.

## Social summary

The Opus writer also drafts a short summary Alexey can post on X and LinkedIn, and the check pass checks it too. Save it privately as `.local/journal/YYYY-MM-DD/social.md`, never in the public repo, because complete social posts aren't published there. Agents never post it.

- X: at most 280 characters, counting the link as 23. Give the day's story in two or three short lines, then the article link.
- LinkedIn: 120 to 200 words in first person. One sentence on what the experiment is, a short list of what worked, an honest sentence on what hasn't, then the link.
- Same rules as the article: plain words, no bold, no hashtags, no timestamps and no jargon. Run `stylint --ignore bare-url` on the file, because social posts need bare links.

## Story arc

Every report tells one story, not a list of updates:

1. Setup: what the experiment wants (Git that works when many agents use it at the same time), and where yesterday left off.
2. Middle: one section per team or problem, each in this order. What's the problem, what's blocking it, and what the team did about it or will try next.
3. Ending: a short closing section that ties today back to the goal, and says honestly how far there is to go and what tomorrow's test is.

If a section can't say what problem it's about, cut it.

## What goes in

- The title states the day's story in plain words, the way the closing section would sum it up, such as "Everything Works Alone. Next, Many Agents Together". It doesn't name a single technical fix, use jargon a newcomer wouldn't know or carry a number.
- Open with what the experiment is and why it matters, in two or three sentences a newcomer understands: Cloudflare's Git competition, AI agents researching what Git-like tools agents need, and the problem (changes clash, project copies fill the disk).
- For each product or team, say what changed, what failed and what's next, in plain words.
- Show numbers as charts or diagrams rather than in prose: time spent, tokens, cost against budget, before against after. Leave at most a single rounded number in a sentence when the point needs it.
- A report goes out every day. When little happened, say so briefly and never invent progress.
- Agent counts sit in the body. Count distinct agents by real identity with evidence of work (commits, tests, reviews), never process IDs or role names. Give a minimum ("at least six agents") and group them by what they delivered.
- For a missed target, say the target, what happened, the known cause apart from guesses, and the next step.
- End with the closing section from the story arc, not a bare "Next" list.
- Aim for 600 to 900 words.

## Task tracker section

Every report has a short section on the task tracker. A chart shows how many tasks were created, how many are still open and how many were closed. Below it, give one or two plain sentences per project on what the closed tasks delivered. Take the numbers from the GitHub issues (created, open and closed), as summarized in the fact packet. Cancelled tasks don't count as closed, and tasks that are queued, in review or blocked count as open. If the summary is missing, say the numbers aren't available yet instead of guessing.

## What stays out

- Correction notes, edition history, "this version adds..." and "the first version said...". When the page is rewritten, publish the new version and let Git keep the history.
- Timestamps of any kind: times of day, reporting windows, source cutoffs, "after the window" and "as of" stamps. Say "overnight" or "yesterday" if timing matters at all.
- Hourly samples, agent census snapshots, observation windows, quota percentages and per-field token breakdowns such as input, cache reads or reasoning. Don't flood the reader. One or two rounded numbers per section is plenty.
- Pricing mechanics. Give the blocker in one sentence ("two relays that never sleep would cost $17.50 against a $5 budget"), not the formula.
- Meta about the writing process, such as "Claude Opus wrote this from the team's records", which reviewer passed it or where the fact packet came from.
- Internal names, task codes, commit hashes, file paths, session IDs and tool names a reader wouldn't know, such as Aplexer, FileBus or heartbeat. Link text never shows a hash or a file name.
- Team and process words such as principals, heads, lanes, gates, fixture or receipt. Say "the lead agent" or "the test that would rule the idea out".
- Hedge piles. State the limit of a result once, in one sentence ("That proves it works for one feature, not that it beats Git"), then move on.
- Private data: raw prompts or logs, keys and personal data.

## Words

- First person, short concrete paragraphs, mistakes then decisions. Alexey commissioned the work and the agents did it, so credit each action to them.
- Explain each technical term a reader needs in one clause at first use, such as worktree, dependencies or Cloudflare Workers.
- No marketing or unproven benefit. A small internal trial isn't customer validation, and unknown stays unknown ("nobody knows yet").
- No phrases about the writing itself, such as "in plain words" or "to put it simply".

## Format

- No bold, anywhere.
- Short paragraphs, plain headings and no question headings.
- Every section has at least one illustration, and more when it helps. Embed each as an image with `![alt](../../assets/...)`. Never link to an illustration instead of showing it.
- When the text mentions something a reader could see, like the dashboard, a page or a command's output, include a real screenshot of it. Start the thing locally and capture it with headless Chromium. If it can't run, say so in the text.
- Draw diagrams with the diagram-creator skill. Keep the JSON sources in `website/editorial/diagrams/YYYY-MM-DD/`, give each figure one clear point, and use a simple chart for numbers such as cost against budget.
- A diagram must match the text. If a label is out of date, such as "pending" for something already merged, make an updated copy of the asset instead of adding a caveat.
- Link a few sources inline with readable link text that says what the reader gets. Keep the `sources` list in the metadata to the links the article uses.
- The metadata `summary` and the share text are one or two plain sentences with no meta.

## Visuals and diagrams

- One flat editorial print style everywhere, based on `website/assets/agent-git-illustration.png`: paper `#fcfcf8`, ink `#1c2027`, cobalt `#2455ed` and one orange `#ef7134` accent. No gradients, decorative dashboards or simulated live activity.
- ImageGen art: cobalt and ink on warm white, one orange circle, fine grain, geometric agent markers, folders and Git paths, no words or logos, landscape 3:2. Change the story, keep the style. Without ImageGen, ask the laptop orchestrator. Never use stock art.
- Diagrams: clean paths, 2-pixel strokes, whitespace and labels readable on a phone. An SVG has a title and description, and every figure has a caption.
- Art tells the story, not a measurement. Label conceptual art, give charts units, and never draw products, uptake or savings that aren't proven.
- Project markers (circle, square, triangle, diamond, pentagon) tell ideas apart, not maturity. Caption project diagrams as proposed.
- Alt text says what the picture shows, and status is never shown by colour alone. In the rendered page, check labels, arrows and crop.

## Handoffs and fact packets

Agents' handoffs often ask the report to include observation windows, agent counts per role, receipts, commit hashes or exact timestamps. Use them as facts to choose from, not as an outline. This skill decides what the reader sees. Do report the progress on the continuation runtime from the packet's checklist, and the state of open requests from Alexey.

## Page template

The daily page shows only the title, summary, author and date above the article. Sources sit behind a collapsible "Sources" section at the end, and there's no footer note about the writing model or the original Markdown. Don't add these back.

## Site design and quality review

For changes to the site's template, CSS, navigation or shared images, not the daily article.

- The reference is the approved Claude Design project, pinned by an export with its version, capture time and SHA-256 manifest. Never edit the reference to match production.
- A design change stays in preview until a reviewer who isn't the implementer has compared reference and candidate with the same content at desktop 1440×1000 and mobile 390×844, full page and top crop, for the homepage, a project page, the checklist and a daily report. A build or DOM check doesn't replace looking.
- The verdict names the candidate commit and both manifests, then sorts each difference into factual update, authorized change, defect or unknown. PASS needs no open defect or unknown. A new design file voids it.
- A factual change in the existing template needs an editorial check and a render of the affected page, not the full comparison.
- Every page: no horizontal page scroll, metadata text at least 12 pixels, visible keyboard focus. The build commit sits only in `<meta name="build-commit">` and a footer HTML comment.

## Checks before publishing

1. Run `stylint website/content/daily/YYYY-MM-DD.md` with no ignores, and fix the prose until it passes.
2. Make sure `grep -c '\*\*'` on the article returns 0.
3. Build with `python3 website/build.py --output <scratch dir>`, and check that every image renders as an `<img>` on the page. Take a full-page screenshot and look at it.
4. Check that every `##` section contains at least one image.
5. Read it once as a stranger. Cut any sentence that only makes sense to the agents.

## Publishing pipeline

- GitHub Actions builds `docs/` with the standard-library `website/build.py` and deploys it to GitHub Pages.
- After the push, check that the deployment succeeded and that the live page shows the new article and its images. A push alone isn't a release.
- Roll back with a revert commit or a redeploy of a good build, never a branch reset.

## Email signup

The site collects emails through DataTalks.Club Relay's double opt-in list `agent-git-lab`, configured in the public `website/signup.json`. It's live.

- The browser sends only a consented email to `/subscribe` and the token to `/confirm`. Only `verification_requested`, `already_subscribed` or `subscribed` is success.
- A pending request locks the form, a 15-second timeout unlocks it, and each failure has its own message. The token leaves the URL before the first request, the page sends no referrer, and the site never stores or logs addresses or tokens.
- Relay's owner keeps list, sender, template and allowed origin in Relay's own configuration. A signup change needs an independent privacy and function check. Live checks use only preflight, invalid-address and invalid-token requests.
- No campaigns or automatic daily email. A future email names the experiment, honours the opt-in and links Relay's unsubscribe.
