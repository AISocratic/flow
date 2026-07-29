# install.md — Flow agent orchestrator & AI project manager

**Audience: the coding agent.** A human dropped this repo's `flow/` code into their project and
said "run install.md". You are that agent. Follow this file top to bottom. Do not improvise around
a blocked step — stop and report.

**Design contract, in one line:** Flow drops into any project, runs on the toolchain that is
already installed, and adds **no new runtime dependency and no new build step**. The only thing the
repo gains is one skill — `.claude/skills/flow-agent-orchestrator/` — plus (for integrated
installs) board routes and tables inside the app that is already there.

- System design spec: `flow.html`

---

## 0. Preconditions — verify before changing anything

Stop with a clear message if any of these fail.

| Check | Command | Requirement |
|---|---|---|
| Git repo | `git rev-parse --show-toplevel` | succeeds |
| Clean tree | `git status --porcelain` | empty (or the human explicitly says to proceed) |
| Default branch known | `git symbolic-ref --short HEAD` | recorded for later |
| Remote (optional) | `git remote -v` | needed only if agents should open PRs |
| PR tooling (optional) | `gh auth status` | needed only for the PR/merge loop |

Then ask the human exactly two questions — nothing else is required to install:

1. **Deployment shape** — `integrated` (recommended) or `standalone`?
2. **Autonomy for the first run** — `automerge off` (recommended) or on?

If the human is absent or says "you decide": choose `integrated` when the repo contains a web app
with an existing authenticated/admin area, otherwise `standalone`. Always choose `automerge off`.

---

## 1. Snapshot branch — do this first, always

The single guarantee that makes Flow safe to try is that a pre-install commit always exists.

```sh
git branch flow/pre-install
git rev-parse flow/pre-install   # record this SHA in the install report
```

Never delete this branch during install. Tell the human its name in your final report.

---

## 2. Detect the stack — discover commands, don't add them

Read whichever of these exist and record the **project's own** commands. Do not install package
managers, test runners, or linters, and do not add dependencies.

| Marker | Read | Typical commands to record |
|---|---|---|
| `package.json` | `scripts` | `test`, `lint`, `typecheck`, `build`, `dev` |
| `pyproject.toml` / `setup.cfg` / `tox.ini` | `[tool.*]`, `[project.scripts]` | `pytest`, `ruff check`, `mypy` |
| `Cargo.toml` | workspace members | `cargo test`, `cargo clippy`, `cargo build` |
| `go.mod` | — | `go test ./...`, `go vet ./...`, `go build ./...` |
| `Makefile` / `justfile` | targets | prefer `make test` / `just test` when present |
| CI config (`.github/workflows/*`) | job steps | the authoritative list — CI is what actually gates merges |

Write the result to `.claude/skills/flow-agent-orchestrator/detected.json`:

```json
{
  "stack": ["node", "python"],
  "verify": { "test": "npm test", "lint": "npm run lint", "typecheck": "npm run typecheck", "build": "npm run build" },
  "package_manager": "pnpm",
  "worktree_dir": "../.flow-worktrees",
  "default_branch": "main",
  "snapshot_branch": "flow/pre-install",
  "mode": "integrated"
}
```

Rules:

- Every recorded command must run **as-is** in a clean checkout. Verify each one before recording
  it; drop what fails and say so in the report.
- A missing command is fine — record `null`. Agents skip verification steps they don't have.
- These commands are the verification hooks. `goal_percentage` / `loop_limit` re-work loops
  (`flow.html` §03, §14) score against their output.

---

## 3. Install the skill — the only mandatory repo change

```
.claude/skills/flow-agent-orchestrator/
├── SKILL.md            # read board → plan epochs → dispatch → PR → merge/wait
├── detected.json       # written in step 2
├── install.md          # this file, for re-runs and audits
└── scripts/
    ├── todo-cli.*      # headless board read/write: board, get, status, pr, set, create, comment
    └── agent-cli.*     # headless run lifecycle + memory: run-start/heartbeat/finish/ask/answer, memory-*
```

- Write the CLIs in the **language the repo already runs** (TS if there's a `package.json` and a TS
  toolchain, Python if it's a Python repo, and so on). Use only the standard library plus what the
  repo already depends on.
- `SKILL.md` must encode the Workflow Graph invariants (`flow.html` §03, §04): one graph per epic, task
  deps never cross an epic, epic-to-epic links live at the project layer, cycles rejected, and
  dispatch takes the leftmost unfinished epoch of an epic.
- If `.claude/skills/agent-todo/` already exists, keep it and have the new skill delegate to it
  rather than duplicating it.

**Stop-condition for a standalone install:** if the human chose `standalone`, this step plus step 5
is the whole install of the repo side — the panel and database live in a separate app (step 4b).

---

## 4. Mount the orchestrator

### 4a. Integrated (recommended)

Share what the platform already has. Nothing here should introduce a second identity system.

1. **Database** — add the orchestrator tables to the existing database via the project's own
   migration tool. Per `flow.html` §03: `todos`, `todo_comments`, `agents`, `card_assignments`,
   `agent_runs`, `agent_memories` / `user_agent_memories`, `releases`. Prefix them if the schema is
   crowded; keep FKs to the existing users table.
2. **Auth** — mount every route inside the existing admin/authenticated area and behind the
   existing guard (e.g. `requireAdminAuth()`). Reuse the platform's roles/permissions; add at most
   one permission (`flow:admin`) if the RBAC model needs a named capability.
3. **Routes** — board UI at the app's admin path (e.g. `/admin/todo`) with the three views: Board,
   List, and Workflow Graph. API per `flow.html` §03: `todos`, `todos/[id]`, `todos/reorder`,
   `todos/version`, `todos/[id]/comments`, plus the agents/runs endpoints.
4. **Knowledge** — point agent memory at the repo's existing docs (`CLAUDE.md`, `docs/`, ADRs) so
   agents inherit domain knowledge instead of rediscovering it.

Why this shape: one user model, one database, one audit trail, and the orchestrator can read
product data when planning work.

### 4b. Standalone

1. Scaffold the panel **outside** the target repo (its own directory and deploy).
2. Give it its own database and its own login.
3. Grant it repo access only: clone/worktree, branch, push, open PRs.
4. The target repo still gets the skill from step 3 — that's how local agents know what to do.

Accept the trade-off explicitly in your report: two user models, two sources of truth, no shared
knowledge. Recommend migrating to integrated once the human is convinced.

---

## 5. Configure execution policy

Write defaults into `detected.json` (or the platform's config table for integrated installs):

| Setting | Default | Notes |
|---|---|---|
| `max_parallel` | 3 | concurrent worktree agents; raise only after a clean first week |
| `worktree_dir` | `../.flow-worktrees` | **outside** the repo, so it never lands in a diff |
| `model` / `effort` | repo policy or `high` / `mid` | per-card override wins (`flow.html` §03) |
| `automerge` | `false` | first run must be human-reviewed |
| `goal_percentage` | 90 | verification threshold |
| `loop_limit` | 3 | max re-work cycles per card |
| `heartbeat_seconds` | 60 | stale-run detection |

Also add `.flow-worktrees/` and any local state dir to `.gitignore` if they could ever appear
inside the repo.

---

## 6. Smoke test — install is not done until this passes

1. Create one epic with two independent tasks and one task depending on both:
   `todo-cli create` ×3, then set `dependencies`.
2. Open the **Workflow Graph** view. Assert: one graph for the epic, the two independent tasks in
   epoch 1, the dependent task in epoch 2, no edge leaving the epic.
3. Attempt a task dependency across two different epics. Assert it is **rejected at write time**
   with the reason written to the card log.
4. Move one real, low-risk card to Todo and let the orchestrator run a single epoch. Assert:
   `agent_runs` row created, heartbeat updating, the recorded verification commands executed, a
   branch pushed and a PR opened.
5. Review that PR yourself and confirm CI ran your existing checks — not Flow's.

If step 3 or 4 fails, stop and report. Do not enable automerge.

---

## 7. Install report — end with this

Print, do not just log:

- snapshot branch + SHA
- deployment shape chosen and why
- files created or modified (should be short: the skill, migrations, route files, `.gitignore`)
- dependencies added (**must be zero**; if not, name each one and why it was unavoidable)
- detected verification commands, and which were verified to run
- smoke-test results, PR link
- the uninstall command block from §8

---

## 8. Uninstall

Removal is easy. It removes the orchestrator, **not the work the orchestrator did**.

```sh
# 1. remove the skill
rm -rf .claude/skills/flow-agent-orchestrator

# 2. integrated installs: remove the board routes + API you mounted in step 4a,
#    then drop the orchestrator tables via the project's own migration tool
#    (or keep them — they are inert once the routes are gone)

# 3. standalone installs: delete the separate panel app and its database

# 4. clean up worktrees and ignores
git worktree prune && rm -rf ../.flow-worktrees
```

**What stays:** every commit an agent made is an ordinary commit in your history. Uninstalling does
not rewind them. The only way to fully revert Flow's effects is to go back to the snapshot:

```sh
git checkout flow/pre-install     # inspect the pre-install state
# or, to make it the new tip of your branch (destructive — read the diff first):
git reset --hard flow/pre-install
```

So: **test it thoroughly, and be ready to revert all of it if it isn't working for you.** Run it
first on a real but non-critical slice of the backlog, with `automerge` off, and read the PRs. Keep
`flow/pre-install` until you're satisfied. We strongly believe that once you've tried the
orchestrator, you won't roll back.
