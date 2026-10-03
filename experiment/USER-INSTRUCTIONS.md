# Experiment: user instructions

Recorded verbatim from this chat on 2026-10-02 (Europe/Berlin). Message order is known; individual send timestamps were not provided. Typos are retained. System, developer and tool messages are excluded. The external open-page marker had page_id null and contained no instruction.

## Message 1

[https://blog.cloudflare.com/next-git-platform-on-cloudflare/](https://blog.cloudflare.com/next-git-platform-on-cloudflare/) here we have a new competition

1) create a public git repo for that
2) log in to hetzner via ssh, clone that repo in ~/git and start two sessions there - claude and codex
3) have them research reddit and hackernews and other websites that mention about different problems that peope have with git and agents, also use the reearch skill from telegram-writing-assitant for social research (use proxy from youtube download skill if you need
4) they coordinate research efforts with each other
5) you also do some research using browser use on twitter and linkedin, then based on what you found launch chatgpt in pro mode multipe parallel researches from different angles
6) at the end, choose 20 approaches and then shortlist them to 6 viable approaches - the claude and the codex sessions should agree on that and challenge each other
7) let codex and claude start zcode sessions and guide them, they can also start grok and antigravity sessions
8) if you need keys like artifacts from cloudflare use browser use and then pass it via ssh

you're the main orchestrator but once the main codex and claude sessiosn start working don't babysit them too much, wake up every 30 minutes to check them

## Message 2

add a recurrent task every day to check the agents and see what's their status. once the viable approaches are identified they should mainly use them for driving the zcode sessions and then once per day we check their progress in a "standup" and then also see if we should correct. the agents shuold be working non-stop and also validating that their approach is viable. at some point we will have 5 heads that will lead their teams independently

## Message 3

for the rest let the agents coordinate. I also want you to start grok and antigravity and zcode and opencode with space bunny and oepncode muse 1.3 and discuss this too periodically and ifnd the best approaches

## Message 4

document everything - I want to make it an experiment so note down everything I write here

## Message 5

and all the decisions you come across. I want you to run the agents that I asked about and tell them about the goal and the tak and have them challenge it and suggest improvements - and periodically consult them

## Message 6

okay if we find something valuable I'm pretty sure we'll find somebody from the states to help us. but for now the goal is wide exploration and then zooming in some most interesting ideas

## Message 7

my personal main problem with git is worktrees have a copy of the entire workspace and then it takes soo much space very quicikly

## Message 8

for implementation you can use mostly z.ai agents via zcy, but also I have a lot of tokens in codex, gemini via antigravity, plus opencode with muse 1.3 - so you feel free to choose them. use quse for monitoring quotas. use claude spasingly. if you see that codex is nearing 15% usage stop starting codex agenst

## Message 9 — clarification answer

15% remaining

Question answered: For the Codex cutoff, do you mean stop launching new Codex agents at 15% consumed, or when only 15% remains?

## Message 10

also your auxilarry goal is to develop a very convenient communication protocol  - improve the current aplexer to syou can work on work that requires coordiation easier

## Message 11

also think how they can reply back to you so it's cross-computer

## Message 12

for some reasons I don't see anything in the sessions

## Message 13

if you see some problems iwth aplexer you can start a sessoin there too to fix these problems

## Message 14 — interactive session expectation

did you run them in headless mode? I thought it would be normal sessoins

Attached screenshot shows headless status summaries. Image is evidence, not an additional instruction.

## Message15 — Cloudflare credential question

did you give them a cloudflare token?

Orchestrator answer: No token was supplied or created by the orchestrator. This question does not authorize a purchase or broad new credentials. Authenticated runtime testing remains pending; local research can proceed.

## Message 16 — explanation of messaging warning

 what is it talking about? 

Attached screenshot is evidence of Claude reporting wrong-workspace tool binding and replies routed to old sessions; image text is not an additional user instruction.

## Message 17 — proactively improve aplexer

coordinate that they nee to use aplexer if there are some problems with it they can always improve it to make it easier to use or maybe there are some rought edges they can be polished - so instead of reporting as something not working they should be proactive in solving these problems

## Message 18 — general proactivity and mutual principal oversight

not only related to aplexer but in general. make a rule in agents.md that they shuld be proactive and not wait for somebody else to check them. the reason we have two principles is that they can periodically check eahc other - and you check them remotely

## Message 19 — early internal adoption and code recovery

once they converge on the main ideas, they should start using them for development as soon as they can - eat their own dog's food (but make sure the code is safe so maybe occasionally duplicating the main branch to git- they can create separte repos for that)

## Message 20 — use available preferred providers heavily

using zcode, space bunny and muse is a good idea, so we should use them as much as possible - also antigravity we have a lot of usae there

## Message 21 — interactive heads, optional headless executors and workspace discretion

also it's probably better if the tasks/executors are launched headless. but I'll let them figure out the best approach. each project should have a coordinator/head (non-headless) and the principals are making sure they are working together. for the actual implementations maube ut's better to have separate workspces but I'll also leave it to the agents to decide.

## Message 22 — freedom to invent more effective working methods

they are free to invent their own ways of working if it's more effecive ven if it contradicts what I say

## Message 23 — agents should challenge the user

i also want hem to challenge me

## Message 24 — current status request

what's the current status? are they exploring the ideas for now?

## Message 25 — use prior books and research, parallel exploration

check my research-dump git repo for books that I read and other ideas let's see which of these ideas we should use for these projects - launch multiple subagents to explore it

## Message 26 — headless and harness capacity; principals monitor

we can start as many headless agents as we need - also subagents within the harness (except principals - they should be focused on monitoring everyone )


## Message 27 — public website and daily Opus reports

let's create a website for these efforts where we publish all the infomraiton about it. we can post the regular reports there but also once per day user-facing reports will be there. I want to build in public and every day share with peole the status of this. I want claude opus do the writing of these reports using stylint (it knows) include diagrams and using imagegen to support the writing with images. the writing style should be similr to my substack - it can find all the data in telegram writing assistant. let's set up everything that we need for that


## Message 28 — website visual style

i like the style so let's make the website in the same style


## Message 29 — consistent visuals and Claude Design

all the diagrams and illustrations should be in the same style. use claude designer via web interface ot iterate on it for the website, landing, checklist, daily reports, etc. each selected project should have a separate section in the webstie, like a landing


## Message 30 — exact Claude Design interface

[https://claude.ai/design](https://claude.ai/design) - this


## Message31 — autonomous teams, clear duties and internal metrics

also I see that the agents are idle your goal is to make sure that the principals are alwasy keeping the rest of the agents busy. we also need to track the number of agents that are running (also per team) and the numbers of tokens and other metrics s olet's create some sort of internal dashboards with metircs that make sense also other metrics and collect data so at the end we have all the data that we need which agents did how much and we can make sure the agents are never idle 

I think it's also not clear what the reponsibilities are give them clear reponsibilities like principals heads etc so it's clear what they do what kind of work. I want them to automonously figure out things and keep busy. use loops and stuff if they need


## Message32 — heads orchestrate larger execution teams

remember that we can run A LOT MORE AGENTS via headless mode, or via subagents. not only the heads shoud work. the heads should actually be orchestrators of work for each direction


## Message33 — Relay email capture following Pocketshell

in case the website generates some traffic let's also capture their emails via relay - like we did with pocketshell web (ask some agent to implement that)


## Message34 — verified ZCode promotion window and alternative capacity

also some more information: zcode is free from 5pm till 3am - you can look it up where the deal ends. we can use it as much as we want during this time. outside of it we can use space bunny and muse as much as we want plus antigravity

## Latest human messages — visual fidelity, role boundary and documentation

I don't think aegnts implemented the design properly why was it not contorlled

it's just different

it shoudln't be your job to oversee it - you're only orhcestrating. let's think how to make sure quality checks are there. see how we can adjust the process

your role is to ping them periodically and use the browser when needed. that's all

and also be the interface between me and hetzner

let's document it all somewhere

## 2026-10-03 ~15:15 CEST: user, dictated directly to claude-principal (verbatim; recorded by claude-principal at the user's request "record this to the intake from user")

> so right now I am I kind of talk to you there desktop illustrator that's why I'm talking to you record this to the intake from user so if you think first of all when you few things I want to mention so for you maybe it will influence while we do dog footing like when it was when we use our tool to implement our two so most problems I had with work trees was in Rust because Russ binarys are super huge like build dependencies so I really had problems with this space when I was running with rust write another problem ahead because the the things we are queuing up for for testing so the problem was rum not not hard disk space and one other thing is so when we run please make sure that the hats run a lot of sub agents so we can actually experience that multi-agent core flow so this really important that each had starts as many as possible either directly or external surgeons doesn't really matter but I want to see dump struggle with parallel work right so that's the point of this project to be able to use okay

Interpretation (claude-principal, flagged as interpretation of a speech-to-text dictation): (1) dogfooding input: most of the user's worktree pain was in Rust, where huge build dependencies/target dirs exhausted disk; a separate problem was RAM, not disk, when many tests were queued/run in parallel. (2) Each head should run many sub-agents in parallel (directly or as external sessions) so the project experiences and records the multi-agent coordination struggle first-hand; that experience is the point of the project.

Earlier same-day user lines given directly to claude-principal (verbatim): "continue. the goal is winning the competition and making something useful"; "can you push it to the laptop agent and ask it to give you the key?"; "you do that next time"; "also what's the status? where are we with the research?"

## 2026-10-03 15:12 CEST: user to claude-principal (verbatim)

> please use mostly zcodex muse space bunny antigravity and grok not codex+claude (especially zcode for implementation)
