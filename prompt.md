❯ Flow = a company that runs itself — goals become projects and tasks on a kanban board, executed by a fleet of coding agents that go from ticket → git worktree → PR → merge, in
  parallel, and file their own bugs. Agents monitor every metrics and keep the business and platform healthy and keep growing. Humans can be in the loop or just observe.

  Main components:
  — Goals — define what's the business purpose. Agents once a week create a project.
  - Kanban board (/admin/todo) — human ↔ agent interface; drag-drop, goals, projects, epics, tasks, bugs, dependencies, per-card execution policy.
  - Agent orchestrator — coding agents read the board (claude code, codex) → plans waves of independent tasks → dispatches agents.
  - Agents (engineers, operators) — one git worktree for agent; implement, lint, test, push, open PR — run in parallel, no collisions. Agents track their memory: agents/memory.md,
  track their steps agents/{id}/steps.md
  —


  - Verification loop — scores work 0–100 against goal_percentage, re-runs until met.
  - Automerge vs. Review — per-card autonomy: agent merges itself, or parks for a human verdict.
  - agent_runs tracker — live run tree (orchestrator → wave → task) in Postgres, heartbeats + state machine.
  - Agents Manager UI — real-time DAG/runs view.
  - Two CLIs — todo-cli (board r/w) + agent-cli (run lifecycle + memory) for headless DB access from worktrees.
  - Nightly self-feeding sweeps — visual-QA + performance scans auto-file bug cards.
  - Runner daemon — long-running autopilot that claims cards and drives them autonomously.
  - /admin dashboards — site + engineering metrics (backlog, releases, token spend, errors, perf).