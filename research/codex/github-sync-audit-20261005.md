# GitHub recovery checkpoint, 5 October 2026

Maintainer requests every project has a GitHub repository and tools stay synced. Version-control product name: AgentBranches. Independent native git ls-remote queries at approximately13:35UTC verified these canonical local HEADs equal actual GitHub main:

| Project | GitHub repository | Exact canonical checkpoint |
|---|---|---|
| AgentBranches | alexeygrigorev/agent-branches |10d9d505e12b227582e8f2e56ad0cfcfe7d5ca7c|
| Agent Dashboard | alexeygrigorev/agent-dashboard |249d086a007ee3d5d0381334a27d56771b959d11|
| Quota Launcher | alexeygrigorev/agent-quota-launcher |c8b0a5000ae060028c4c497b715615ecfce71d6c|
| Agent Bus | PocketShell-io/agent-bus (public requested sibling) |f3295f99e188719f5df9fccb22706d8a0e5bb8f8|
| Agent Coordination | alexeygrigorev/agent-coordination |bb8dcad0979b42763985d9282efc35250dec4827|
| Competition/publication | alexeygrigorev/cloudflare-agent-git |583362de82cbbd5396d1138bd684604b6efec902|

Canonical equality does not include uncommitted files, unpublished isolated branches, or imply independent product acceptance. Launcher main has dirty peerREADME/private configuration/payloads; Bus and Coordination have fresh uncommitted source/reviews; preserve these and publish only sanitized owner-confirmed paths. GitHub links/repository visibility can be separately verified through gh; no organization transfer requested for all older projects.

Head operating contract: at meaningful reviewed milestones commit explicit owned sanitized paths under repository git flock, push exact source/review branch promptly, and verify actual remote ref SHA. Canonical integration requires release and review; publish recoverable work-in-progress on appropriately named branches without claiming acceptance. Never blanket-add private .local/.config/payload/log files or overwrite concurrent work. The normal GitHub checkpoint remains independent of AgentBranches prototype storage. Heads record local source pin, remote ref/pin and outstanding dirty/unpublished work with actual verification time. Failure triggers owned diagnosis/retry/fallback, not a silent unsynced tool.
