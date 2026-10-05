# Practitioner Research: Multi-Agent Git and Cross-Computer Coordination

## Overview
This document compiles recent practitioner feedback and social research regarding multi-agent Git workflows and cross-computer agent coordination. The focus is on identifying concrete user friction points and structural challenges that emerge when moving from single-agent chat to distributed multi-agent systems (MAS).

## Concrete User Friction Points

### 1. Multi-Agent Git & Repository Management
When multiple autonomous agents operate on the same codebase, practitioners observe significant friction stemming from agents treating Git as a conversational interface rather than a structured system.

*   **Context Collision & Implicit Conflict:** Agents operating in parallel often make conflicting implicit assumptions about code standards, architecture, and project state. This leads to agents overwriting each other's work or producing "Frankenstein" codebases where different tools impose competing worldviews.
*   **The "Git Throughput Mismatch":** Agents generate code and commits far faster than human reviewers or traditional CI/CD pipelines can validate them. This parallel generation outpaces branch and commit discipline, creating a massive review bottleneck.
*   **Merge Conflict Incompetence (Semantic Drift):** While agents excel at generation, they frequently fail at resolving merge conflicts. They lack the deep context to understand the *intent* behind overlapping changes. A textual resolution may be syntactically correct but functionally broken, leading to silent semantic drift.
*   **Non-Determinism in Git Operations:** Practitioners report agents struggling with Git nuances—such as branching from incorrect commits, pushing to the wrong remote, or accidentally staging sensitive files (e.g., `.env`).
*   **Context Collapse in Reviews:** Using the same agent or model to both write and review code often results in the agent being "saturated" by its own logic, causing it to rubber-stamp its own off-by-one errors or missing null checks.

### 2. Cross-Computer Agent Coordination
Coordinating agents across different machines introduces a significant "coordination tax" and exposes the limitations of current orchestration frameworks.

*   **State Synchronization & Divergence:** Maintaining a unified "source of truth" across distributed agents is a primary challenge. Agents often operate on stale data due to asynchronous race conditions, leading to contradictory actions where one agent undermines another.
*   **The "Coordination Tax" & Stalled Workflows:** Scaling the number of agents is not a linear path to better performance. Communication and synchronization costs scale exponentially. Without clear termination criteria, agents can enter circular loops—debating indefinitely, requesting redundant clarifications, or repeating work—which consumes compute budget without progressing the task.
*   **Observability Trilemma:** Traditional monitoring is inadequate for non-deterministic, parallel agent execution. Practitioners struggle to balance completeness, timeliness, and system overhead. When a multi-agent chain fails, identifying the root cause (e.g., an invisible handoff failure vs. a model hallucination) is extremely difficult without graph-based tracing.
*   **Protocol Fragility & Latency:** The lack of standardized communication protocols (such as consistent A2A or Model Context Protocol usage) means agents struggle to exchange data with reliable semantics. In cross-computer setups, network latency degrades real-time coordination, and centralized orchestrators easily become single points of failure.

## Emerging Practitioner Solutions
To mitigate these friction points, the industry is moving toward treating agentic workflows as governed distributed systems:

1.  **Git Worktrees for Isolation:** Teams are heavily adopting `git worktree` to give each agent an isolated, parallel directory and branch structure, preventing them from fighting over the same physical files.
2.  **Primitive Blocking & Hookflows:** Intercepting raw Git commands with custom CLI extensions to enforce repository rules and prevent destructive actions.
3.  **Path Reservation & Pessimistic Locks:** Orchestrators that require agents to claim file paths before execution, queueing tasks if overlaps are detected.
4.  **Adversarial Review Loops:** Utilizing distinct agents (often different base models) for the "Builder" and "Reviewer" roles to combat context collapse.
5.  **Explicit Information Contracts:** Defining strict syntactic and semantic expectations for data payloads passed between distributed agents to prevent communication breakdowns.
