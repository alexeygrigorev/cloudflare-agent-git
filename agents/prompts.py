"""
agents/prompts.py - Task prompt builder for autonomous coding agents under Agent Branches.
"""

from typing import Optional


def build_agent_prompt(
    task_id: str,
    title: str,
    body: str,
    branch: str,
    server_url: str,
    agent_id: Optional[str] = None,
) -> str:
    """Format the operational prompt for an autonomous coding agent executing a demo task.
    
    Instructs the agent on task requirements, test execution, frequent WIP git pushes,
    checking integration radar status, and acknowledging warnings.
    """
    aid_info = f" (agent id: {agent_id})" if agent_id else ""
    return f"""You are an autonomous coding agent assigned to implement the following task in this repository:

# Task {task_id}{aid_info}: {title}

{body}

================================================================================
CRITICAL AGENT BRANCHES WORKFLOW RULES:
================================================================================
1. You are working in your own isolated git fork on branch '{branch}'.
2. Frequently commit and push your WIP changes to origin so the integration radar can observe your progress:
     git add -u
     git commit -m "wip: {title} progress"
     git push origin {branch}

3. Run the local test suite using `node --test` (or `npm test`) often to ensure your code is solid.

4. Check the Integration Radar status periodically and BEFORE you finish:
     agent-branches --server {server_url} status
   This will show you if any concurrent agents working on other tasks have introduced conflicting changes with your code!

5. If an integration warning is reported for your branch, inspect the conflicting files.
   If you have investigated or rebased to resolve it, acknowledge the warning:
     agent-branches --server {server_url} ack --task-id {task_id} --warning-id <warning_id>

6. Do not reformat unrelated files. Make sure all tests pass before completing.
"""
