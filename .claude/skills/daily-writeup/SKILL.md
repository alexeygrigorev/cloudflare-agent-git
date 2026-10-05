---
name: daily-writeup
description: Write the public daily report for the Agent Branches journal (website/content/daily/YYYY-MM-DD.md). Use for every daily report, rewrite or correction of a daily page. Claude Opus only.
---

# Daily write-up

The daily report is a short story for human readers who don't follow the experiment. It isn't a log for agents. These rules come straight from Alexey and override any conflicting rule in WORKFLOW.md, the writer prompt or a fact packet.

## Who writes

- Only Claude Opus writes or rewrites the article. Run it as `claude --model opus`, and check that the response's `modelUsage` includes an Opus model. The Opus session writes the article itself and doesn't delegate it to a subagent.
- The coordinating agent doesn't write prose itself and doesn't hand the writing to Codex, Gemini, Grok, z.ai or Sonnet. If Opus can't run because of quota or an error, keep the last published article and report the problem. Don't publish a substitute.
- Other models may check facts, but Opus makes every prose change.

## Two steps, then publish

`python3 website/write_daily.py --date YYYY-MM-DD` runs both steps as separate Claude Opus sessions:

1. Write-up: an Opus session writes the article, metadata, share text and illustrations by following this skill.
2. Check pass: a fresh Opus session checks the draft against this skill and the sources. It rewrites whatever fails and leaves the rest alone, then records its verdict in `.local/journal/YYYY-MM-DD/check.json`.

After step 2, the article is ready. Principals and heads don't re-review or edit it. The coordinating agent only confirms that both sessions ran on Opus and that `check.json` exists, then runs `python3 website/publish_daily.py YYYY-MM-DD --publish`, commits the daily files and assets, and pushes.

The coordinator then sends the laptop orchestrator one message saying the article is ready, with its public link. The laptop orchestrator only shows it to Alexey. It doesn't review, edit or summarise it.

## Story arc

Every report tells one story, not a list of updates:

1. Setup: what the experiment wants (Git that works when many agents use it at the same time), and where yesterday left off.
2. Middle: one section per team or problem, each in this order. What's the problem, what's blocking it, and what the team did about it or will try next.
3. Ending: a short closing section that ties today back to the goal, and says honestly how far there is to go and what tomorrow's test is.

If a section can't say what problem it's about, cut it.

## What goes in
- The title states the day's story in plain words, the way the closing section would sum it up, such as "Everything Works Alone. Next, Many Agents Together". It doesn't name a single technical fix or use jargon a newcomer wouldn't know.

- Open with what the experiment is and why it matters, in two or three sentences a newcomer understands.
- For each product or team, say what changed, what failed and what's next, in plain words.
- Show numbers as charts or diagrams rather than in prose: time spent, tokens, cost against budget, before against after. Leave at most a single rounded number in a sentence when the point needs it.
- End with the closing section from the story arc, not a bare "Next" list.
- Aim for 600 to 900 words.

## What stays out

- Correction notes, edition history, "this version adds..." and "the first version said...". When the page is rewritten, publish the new version and let Git keep the history.
- Timestamps of any kind: times of day, reporting windows, source cutoffs, "after the window" and "as of" stamps. Say "overnight" or "yesterday" if timing matters at all.
- Hourly samples, agent census snapshots, observation windows, quota percentages and per-field token breakdowns such as input, cache reads or reasoning. Don't flood the reader. One or two rounded numbers per section is plenty.
- Pricing mechanics. Give the blocker in one sentence ("two relays that never sleep would cost $17.50 against a $5 budget"), not the formula.
- Meta about the writing process, such as "Claude Opus wrote this from the team's records", which reviewer passed it or where the fact packet came from.
- Internal names, task codes, commit hashes, file paths, session IDs and tool names a reader wouldn't know, such as Aplexer, FileBus or heartbeat.
- Hedge piles. State the limit of a result once, in one sentence ("That proves it works for one feature, not that it beats Git"), then move on.

## Format

- No bold, anywhere.
- Short paragraphs, plain headings and no question headings.
- Every section has at least one illustration, and more when it helps. Embed each as an image with `![alt](../../assets/...)`. Never link to an illustration instead of showing it.
- When the text mentions something a reader could see, like the dashboard, a page or a command's output, include a real screenshot of it. Start the thing locally and capture it with headless Chromium. If it can't run, say so in the text.
- Draw diagrams with the diagram-creator skill. Keep the JSON sources in `website/editorial/diagrams/YYYY-MM-DD/`, give each figure one clear point, and use a simple chart for numbers such as cost against budget.
- A diagram must match the text. If a label is out of date, such as "pending" for something already merged, make an updated copy of the asset instead of adding a caveat.
- Link a few sources inline with readable link text. Keep the `sources` list in the metadata to the links the article uses.
- The metadata `summary` and the share text are one or two plain sentences with no meta.

## Handoffs and fact packets

Agents' handoffs often ask the report to include observation windows, agent counts per role, receipts, commit hashes or exact timestamps. Use them as facts to choose from, not as an outline. This skill decides what the reader sees.

## Page template

The daily page shows only the title, summary, author and date above the article. Sources sit behind a collapsible "Sources" section at the end, and there's no footer note about the writing model or the original Markdown. Don't add these back.

## Checks before publishing

1. Run `stylint website/content/daily/YYYY-MM-DD.md` with no ignores, and fix the prose until it passes.
2. Make sure `grep -c '\*\*'` on the article returns 0.
3. Build with `python3 website/build.py --output <scratch dir>`, and check that every image renders as an `<img>` on the page. Take a full-page screenshot and look at it.
4. Check that every `##` section contains at least one image.
5. Read it once as a stranger. Cut any sentence that only makes sense to the agents.
