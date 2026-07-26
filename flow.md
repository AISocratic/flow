# AI Orchestrator — System Design (flow.md)

> **Status:** Living spec · **Owner:** Fed · **Last updated:** 2026-07-06
> **Scope:** The autonomous AI software-engineering orchestrator that runs the AI Socratic
> website's own backlog — from a Kanban card to a merged PR — plus the dashboards,
> nightly jobs, and skill files that surround it.

This document describes how the orchestrator works today (what is actually built and
running), and the metrics + gaps we should close next. It is the companion to
`docs/MULTI_AGENT_PM_SPEC.md`, which holds the forward-looking product vision.

---

## 0. Goal

Create an AI agent orchestrator that lets you run your team or startup in **full autonomy**:

1. **Install Flow** — it integrates with the Kanban board you already have, or builds a new one
   (§8, [`install.md`](install.md)).
2. **Wire up the dashboard** so every metric lands in one place: engineering, KPIs, traffic, logs,
   spend (§5).
3. **Give the agents a mission** — they decompose it into projects, epics and tasks on the board
   (§5c, §6).
4. **Orchestrate them** — waves of agents work the board until the metric moves (§3, §4).

All of it on **your AI subscriptions** rather than metered API credits. The exception is models cheap
enough to justify on their own — Gemma 4, DeepSeek, Kimi 3, GLM 5.2 and similar — used for
summarization and other **non-mission-critical** work. See §4f.

---

## 1. What it is, in one paragraph

The orchestrator turns the admin Kanban board (`/admin/todo`) into the work queue for a
fleet of coding agents. A human (or a nightly job) files cards; the `agent-todo` skill
reads the board, builds a dependency-ordered plan, and dispatches one agent **per task in
its own git worktree** so independent work runs in parallel. Each agent implements its
card, lints, tests, opens a PR, and reports back. Cards then either **automerge** or land
in a **Review** column for a human verdict. Every run is tracked in Postgres
(`agent_runs`) so the live **Agents Manager** UI can show the orchestrator → wave → task
tree in real time. Two nightly sweeps (visual-QA and performance) auto-file bug cards, so
the system also *feeds itself work*.

```
   ┌──────────────┐   files cards   ┌───────────────────┐
   │  Humans /     │ ─────────────▶ │  Kanban board     │
   │  Nightly jobs │                │  /admin/todo      │
   └──────────────┘                 │  (todos table)    │
                                    └─────────┬─────────┘
                                              │ todo-cli board (plan: waves)
                                              ▼
                            ┌───────────────────────────────────┐
                            │  agent-todo  (orchestrator skill) │
                            │  Sense → Plan → Distribute        │
                            └───────┬───────────────┬───────────┘
                          wave 1    │               │   wave 2 …
                     ┌──────────────┴─────┐     ┌───┴────────────┐
                     │ Workflow (fan-out) │     │ Workflow       │
                     └───┬──────────┬─────┘     └────────────────┘
              task agent │          │ task agent   (1 git worktree each, parallel)
            ┌────────────▼┐   ┌─────▼────────┐
            │ branch+impl │   │ branch+impl  │  lint • test • push • gh pr create
            │ lint/test   │   │ lint/test    │
            │ PR + report │   │ PR + report  │
            └──────┬──────┘   └──────┬───────┘
                   │ run-start/heartbeat/finish (agent-cli)
                   ▼
            ┌──────────────────────┐  approved / automerge   ┌──────────┐
            │ agent_runs (Postgres)│ ──────────────────────▶ │  merged  │
            │ live run tree        │    needs_human_review   │  → Done  │
            └──────────┬───────────┘ ──────────────────────▶ │  Review  │
                       │ polled every 10s                    └──────────┘
                       ▼
            ┌─────────────────────┐
            │ Agents Manager UI   │  /admin/todo/agents
            │ Agents · Runs · DAG │
            └─────────────────────┘
```

---

## 2. ERD — Orchestrator data model

The orchestrator persists everything in the same Supabase Postgres that backs the site.
Seven tables form the core. Relationships:

- `todos` is the spine: cards, hierarchy (`parent_id` → epic), cross-links (`dependencies uuid[]`),
  and per-card execution policy (`model`, `effort`, `subtasks_*`, `goal_percentage`, `loop_limit`).
- `todo_comments` is the append-only work log shared by humans and agents.
- `agents` is the registry of executors (orchestrator, wave, per-task agents).
- `card_assignments` records who is working a card: **two slots** with claim timestamps, so a race is
  recorded rather than lost, but only **one active worker** ever survives arbitration.
- `agent_runs` is the **execution tracker** — a self-referential tree
  (`parent_run_id`) grouped by `workflow_run_id`, with a state machine + heartbeat.
- `agent_memories` / `user_agent_memories` are durable knowledge scoped to an agent or a user.
- `releases` records shipped tags (surfaced on the dashboard and the board's Releases tab).

![Orchestrator ERD — todos, agents, agent_runs, card_assignments, todo_comments, agent_memories, releases](/flow-erd.png)

_Entity-relationship diagram of the orchestrator data model. See the relationships above; every table is keyed in Supabase Postgres._

---

## 3. Kanban board — `/admin/todo`

The board is the human ↔ agent interface. Source: `app/(admin)/admin/todo/`.

### Columns (the `todos.status` lifecycle)

`backlog → todo → doing → review → done` plus a parked `to-follow-up` lane and
terminal `wont-do` and `archive`. A card moves to `to-follow-up` when it's blocked on an
answer, an external event, or something to revisit later, then rejoins the flow once unblocked.
Dragging a card **into** Review clears its `review_status` (a fresh verdict is required).

### Card types

- **task** — leaf work unit (the only thing agents implement directly).
- **epic** — container; the orchestrator breaks it into child tasks (`parent_id`).
- **bug** — auto-filed by the nightly visual-QA / performance sweeps (deduped by title).

### Key features

| Feature | How it works |
|---|---|
| **Drag & drop** | `dnd-kit` with custom collision detection; one batched `POST /reorder` on drop. |
| **Hierarchy** | Epics nest subtasks visually when both are in the same column; `parent_id` FK. |
| **Dependencies** | `dependencies uuid[]` cross-links; task deps stay inside one epic, epic deps live on the project. |
| **Three views** | **Board** (Kanban), **List** (grouped), **Workflow Graph** (per-epic execution DAG — see below). |
| **Execution policy** | Per card: `effort` (low/mid/high) + `model` (tier or slug); `subtasks_*` for children. |
| **Verification loop** | `goal_percentage` (0–100) + `loop_limit` drive re-work until the score is met. |
| **Review & merge** | `pr_url` + `review_status=approved` → "Merging" badge; agent squash-merges → Done. |
| **Automerge** | `automerge=true` (or `needs_human_review=false`) → agent merges without a human. |
| **Bulk actions** | Cmd/Ctrl/Shift-select → move / re-priority / assign / approve / archive. |
| **Live refresh** | Polls `GET /api/admin/todos/version` every 10s; refetches only when the token changes. |
| **Comments** | Per-card append-only log; authored by humans or `agent-todo`. |

### Workflow Graph view — the board as an execution plan

The third view is the one the orchestrator actually executes (see §4 and the
_Workflow Graph / Agent Orchestrator_ chart in the design doc). Rules:

- **One graph per epic.** Nodes are tasks, edges are `dependencies`. An epic's graph is
  self-contained, so a wave of it can be dispatched without reading the rest of the board.
- **Task edges never cross epics.** A dep is accepted only when both cards resolve to the same
  `parent_id`; anything else is refused at write time with the reason in the card log.
- **Epics connect only at the project layer.** An epic → epic link is stored as a gate on the two
  epic cards. When it clears, the downstream epic's whole graph becomes ready at once.
- **X-axis is the ready wave.** A task enters wave _N_ once every dep cleared by _N−1_, so
  horizontal position is execution order; a gated epic shifts right as a whole, independent epics
  start at wave 1.
- **Cycles are rejected**, so the graph is a DAG by construction rather than by nightly repair.

### API surface

| Endpoint | Methods | Purpose |
|---|---|---|
| `/api/admin/todos` | GET, POST | List (tree/graph/grouped views) / create |
| `/api/admin/todos/[id]` | GET, PATCH, DELETE | Read / update / delete a card |
| `/api/admin/todos/reorder` | POST | Persist drag-drop (status + sort_order, optional review clear) |
| `/api/admin/todos/version` | GET | Cheap change token (todos + comments + agents + assignments + runs) |
| `/api/admin/todos/[id]/comments` | GET, POST | Card log |
| `/api/admin/todo-metrics` | GET | Aggregate counts for the dashboard Backlog card |
| `/api/admin/agents`, `/agents/runs`, `/agents/runs/[id]`, `/agents/runs/[id]/heartbeat`, `/agents/runs/[id]/feedback`, `/agents/assignments`, `/agents/board` | GET/POST/PATCH | Agents Manager data |

All routes require `requireAdminAuth()`.

---

## 4. Agents Manager — how we run agents locally

UI: `app/(admin)/admin/todo/agents/page.tsx` (tabs: **Agents · Runs · DAG · Memory**).
Engine: the `agent-todo` skill + two CLIs + git worktrees + the Workflow primitive.

### 4a. The execution model

1. **Plan.** The orchestrator calls `todo-cli board`, which returns
   `{ nodes, edges, plan }`. The plan buckets open cards into **waves** (independent tasks
   that can run in parallel), plus `inProgress`, `blocked`, `needsBreakdown`,
   `humanAssigned`, and `readyToMerge`. Approved PRs (`readyToMerge`) are merged first on
   every run.

2. **Claim.** An agent chooses its scope — a **whole epic**, or **a few tasks inside one** (both
   are safe because an epic graph is self-contained). It then **assigns the card to itself and
   moves it to `doing`** as one atomic step; that column move is the signal to every other agent
   and human that the card is taken. `card_assignments` holds **two slots** per card, so a
   simultaneous claim is recorded instead of lost: when two workers land on the same card, the
   **lowest claim timestamp** decides whether to keep the card or leave it to the other agent, and
   the decision is written to the card log. A worker that stops heartbeating loses its slot and the
   card returns to the ready wave.

3. **Distribute.** For each wave the orchestrator spawns **one Workflow** that fans out a
   **per-task agent in a fresh git worktree** under `.claude/worktrees/<workflow_run_id>/`.
   Worktrees are full checkouts of the default branch with `node_modules` symlinked and
   `.env.local` copied in, so parallel agents never collide on files.

4. **Implement.** Each task agent: checks out `todo/<8-char-id>-<kebab-title>`, implements
   the card, runs `pnpm lint` + `pnpm test`, pushes, and opens a PR via `gh pr create`.
   It returns `{ id, status: done|failed, prUrl, branch, summary }`.

5. **Verify (optional loop).** If `goal_percentage > 0`, a verification agent scores the
   work 0–100. If `score < goal` and `attempts < loop_limit`, the task re-runs on the same
   branch/PR; each attempt is logged as a card comment.

6. **Resolve model/effort.** `resolveExecution(card, parent)` in
   `lib/agents/model-policy.ts` maps tiers → slugs (`low→haiku-4.5`, `mid→sonnet-4.6`,
   `high→opus-4.8`; `fable-5` = high) and applies relative child policies (`same`,
   `same_lower`).

7. **Merge or wait.** `automerge` / `needs_human_review=false` → squash-merge → Done.
   Otherwise the card sits in **Review** for a human verdict.

### 4b. The two CLIs (headless DB access from worktrees)

Worktrees lack the app's runtime, so all DB I/O goes through CLIs run from the main tree
with the service-role key:

```bash
LOG_LEVEL=warn npx tsx --env-file=.env.local --tsconfig ./tsconfig.json \
  .claude/skills/agent-todo/scripts/todo-cli.ts  <command>   # board/get/status/pr/set/create/comment
  .claude/skills/agent-todo/scripts/agent-cli.ts <command>   # run-start/heartbeat/finish/ask/answer/tree/memory-*
```

- **`todo-cli`** — board reads + card writes (`board`, `get`, `status`, `pr`, `set`, `create`, `comments`, `comment`).
- **`agent-cli`** — run lifecycle + memory (`run-start`, `run-heartbeat`, `run-finish`, `run-ask`, `run-answer`, `run-tree`, `memory-list/get/set/delete`).

### 4c. The run tree

Every agent registers a row in `agent_runs`, linked by `parent_run_id` and grouped by
`workflow_run_id`:

```
orchestrator (harness=claude-code, parent_run_id=null)
└─ wave 1 (harness=workflow-agent)
   ├─ task:abc12345 (model=opus-4.8)  queued → running(implement) → running(verify) → done
   └─ task:def67890 (model=sonnet-4.6) queued → running → done
└─ wave 2 …
```

`heartbeat_at` drives staleness detection; `state=needs-feedback` pauses a run on a human
question (`run-ask`/`run-answer`). The Agents Manager polls `/api/admin/agents/runs?view=tree`
to render this live.

### 4d. Prompt & run snapshots — rollback, fork, MCTS *(planned — see `prompts.md`)*

Every coding-agent run should be a reproducible, forkable snapshot:

- **Prompts as files** — one markdown file per prompt under `prompts/` (frontmatter +
  body). Git is the version history: `pnpm prompts list|show|history|diff|rollback|fork|status`
  wraps it, and a read-only `/admin/prompts` page shows content + GitHub commit history.
- **Per-run snapshot** — each run records the exact prompt it executed
  (`agent_runs.prompt`, live today) **plus** the repo commit and prompt-file commit it ran
  against, so any run can be replayed or diverged from precisely.
- **Rollback & fork → search** — because every run is a snapshot on its own branch, a
  card can be re-run from any earlier snapshot with a tweaked prompt. The run tree becomes
  a **search tree (MCTS-style)**: multiple prompt/approach branches per card, where the
  branch to continue from is chosen either **automatically** (the verification score picks
  the best child) or **by the user** from the Agents Manager DAG view.

### 4e. The two entry points

- **`agent-todo` skill** — the full multi-wave orchestrator (the default for "run the board").
- **`todo-task-worker` agent** (`.claude/agents/todo-task-worker.md`) — a single-task
  worker: picks one unblocked high-value card and drives it to a PR. Model: Opus.

### 4f. Cost classes — subscriptions first, cheap models for the rest

Model choice is routed by **cost class** as well as capability. `resolveExecution(card, parent)`
already resolves `model` + `effort` per card; the cost class is the second axis:

| Lane | Runs on | Used for | Bill |
|---|---|---|---|
| **Subscription** (default) | Claude Code / Codex seats we already pay for | Plan, implement, review, verify, judge — anything mission-critical | Flat monthly; unchanged as agent count grows |
| **Cheap-metered** (exception) | Gemma 4, DeepSeek, Kimi 3, GLM 5.2 etc. via OpenRouter | Summarize, label, dedupe, digest, embed — never mission-critical | Metered, but cheaper than a seat for this work |

What we deliberately don't do is pay per token for work a subscription seat already covers. A card
can override its lane, so the split is visible and adjustable per card rather than a global switch.

### 4g. Agent signaling — **TBD**

Board state is a good *status* channel: claim a card, move a column, comment on the card, and
everyone converges on the next poll. What's missing is **agent-to-agent signaling** for live runs —
updates, changes and notifications pushed between running agents without round-tripping through the
board ("I changed this module's shape", "my card will break yours", "stop, already fixed").

Open design questions: transport, delivery guarantees, ordering, and who may interrupt whom.
**Action: ask @dan van flyman about Synapse** before building anything here — it may already be the
answer.

---

## 5. `/admin` dashboards — metrics

The admin dashboard (`app/(admin)/admin/page.tsx`, cards in `components/admin/`) has a
global toolbar: **View filter** (All/Favourites/Community/Audience/Events/Engineering),
**Date range**, **Resolution** (auto/daily/weekly/monthly), and a global refresh with a
"updated X ago" stamp. Data comes from Supabase, Google Analytics 4 (GA4), and the
build/metrics pipeline.

### 5a. Metrics we measure today

**Community Overview** (Supabase)
- Total Users · Total Members · Workshop Subscribers · Newsletter Subscribers · Avg Open Rate · Avg Click Rate

**User Growth / Signups** (GA4 + Supabase)
- Total / New / Returning users per period (with in-progress projection) · New registrations bar chart

**Content & Pages** (GA4)
- Page views · users (new/returning) · top blog posts · top landing pages (sessions, bounce)

**Audience** (GA4)
- Top countries (world map + ranking) · Traffic sources by channel + top referrals
- Engagement: avg session duration, engagement rate, sessions/user, pages/session
- Devices: desktop / mobile / tablet split

**Events / Luma** (GA4 + Supabase)
- Luma analytics (views, users, top pages, sources) · Luma funnel (sessions/users from lu.ma) · Event attendance (registrations per event)

**Engineering** (Supabase + build pipeline)
- **Backlog** — open cards by type (bug/epic/task) and by column; in-review; done
- **Latest Releases** — last 6 tags with summary, highlights tally, date
- **AI Coding Usage** — Claude Code + Codex token spend (combined, output, daily trend)
- **Server Errors** — total / errors / warnings, trend, most-common errors (fingerprint, count, last seen)
- **Performance Metrics** — Lighthouse (mobile/desktop) + Core Web Vitals p75 (LCP, CLS, INP, TTFB), payload size, latest reports
- **Project Health** — repo size, node_modules size, build/deploy/test time, dependency count, LOC (nightly snapshots)
- **Anomalies / Triggers / Server errors** — global resolution control + monitoring triggers (auto-investigate)

### 5b. Tracking pillars — everything observable lands on the dashboard

All operational tracking surfaces in one place, `/admin`:

- **Error / bug tracking (Sentry-style)** — server errors are captured today
  (fingerprint, count, last seen, trend). Target: full issue lifecycle — group → assign →
  link to a board card → resolve — with release tagging and alert routing
  (email/Telegram/SMS via `lib/agents/notify.ts`).
- **App / website performance** — Lighthouse (mobile/desktop) + Core Web Vitals p75
  (LCP, CLS, INP, TTFB) today. Target: per-route trends and regression alerts that
  auto-file cards (the perf health check already files red/yellow tickets).
- **Code quality / performance** — Project Health snapshots today (repo/node_modules
  size, build/deploy/test time, dep count, LOC). Target: lint/test-failure trends,
  type-error counts, and bundle-size budgets checked per PR.
- **SEO** — nightly `seo-audit` cron exists. Target: a dashboard card with audit scores,
  broken links / meta issues, and search-impression trends over time.
- **Agent observability / eval / token usage** — run states + live tree today. Target:
  evals per run (verification scores), token spend attributed to `agent_runs` and cards
  (from AI Coding Usage), prompt-version linkage per run, and the success/failure-rate
  metrics in §5d.

### 5c. Goals — dashboard-first, board-executable

High-level goals (e.g. "grow newsletter signups 20%", "ship cafes v2") live on the
dashboard next to the metrics that measure them, each with a target + current value +
trend. A goal is **executable**: it can be translated into board work — goal → mission
(`/admin/todo/missions`) → epic + dependency-ordered tasks via the mission decomposer —
so progress shows up twice: as the metric moving, and as card completion on the Kanban
board. The mission pipeline is live (2026-07); the dashboard goals card is the remaining
gap.

### 5d. Metrics we should add (gaps for the orchestrator)

These are agent/orchestrator-native metrics the dashboard does **not** yet surface:

- **Agent throughput** — cards moved to Done per day/week by agents vs humans.
- **Lead time & cycle time** — created→done and doing→review→done per card (and p50/p90).
- **PR success rate** — % of agent PRs merged vs closed-without-merge vs failed lint/test.
- **Automerge ratio** — share of cards merged without human review.
- **Verification loop cost** — avg attempts to hit `goal_percentage`, and goal-miss rate.
- **Run reliability** — % runs ending `done` vs `failed` vs `stale`; mean time-to-stale.
- **Feedback latency** — time a run spends in `needs-feedback` before a human answers.
- **Cost per card** — token spend (from AI Coding Usage) attributed to `agent_runs` / cards.
- **Model mix** — distribution of resolved models (haiku/sonnet/opus/fable) per wave.
- **Wave parallelism** — avg concurrent task agents; worktree utilization.
- **Auto-ticket funnel** — bugs filed by nightly sweeps → triaged → fixed → verified.
- **Rework rate** — cards bounced from Review back to Todo (`changes_requested`).

---

## 6. Nightly & scheduled jobs

Two scheduling layers: **GitHub Actions** (self-hosted Hetzner runners) and a
**docker-compose `cron` container** (Alpine `crond`) calling `Bearer $CRON_SECRET`
endpoints under `app/(main)/api/cron/`.

| When (UTC) | Job | What it does | Auto-files cards? |
|---|---|---|---|
| `*/5 * * * *` | process-email-queue | Drain transactional email queue (Postmark) | — |
| `0 */5 * * *` | refresh-leaderboard | Scrape HLE / SWE-bench / LM Arena (Firecrawl) | — |
| `0 0` | sync-luma | Sync Luma events + metadata | — |
| `0 1` | sync-luma-users | Sync Luma attendee profiles | — |
| `0 2` | sync-luma-attendance | Sync event attendance | — |
| `0 3` | refresh-embeddings | Regenerate content embeddings | — |
| `0 4` | generate-cafe-rotations | AI café rotations + invites (8 weeks) | — |
| `0 5` | refresh-opensource-stars | GitHub star history | — |
| `0 6` | lighthouse | Lighthouse perf scan → stores metrics | feeds perf check |
| **`0 7`** | **Nightly visual QA** (GitHub Actions `visual-qa.yml`) | Full-page screenshots across desktop-chrome/webkit/iphone-15/pixel-7, judged by a vision model; emails a digest | **Yes** |
| `0 9 * * 1` | city-digest | Weekly city intro email (Mondays) | — |
| `0 10` | onboarding-emails | New-user onboarding | — |
| `0 11` | workshop-upsell-emails | Segment upsell | — |
| `0 23` | release-digest | Daily/weekly AI research digest | — |

### The self-feeding loop (nightly → board)

The **07:00 UTC visual-QA sweep** (`scripts/metrics/visual-qa-report.ts`) does two things that
file work onto the board, both idempotent via `fileBugIfAbsent()` (dedupe by stable title):

- **`POST /api/cron/visual-qa-bugs`** — one bug card per major visual finding
  (`[Visual QA] {route} on {device}`), high priority, into `todo`.
- **`POST /api/cron/performance-bugs`** — runs `runPerformanceHealthCheck()`
  (`lib/admin/performance-tickets.ts`): Lighthouse < 50 → high-priority `todo` bug;
  50–69 → backlog card with `needs_human_review=true`.

So overnight the system can detect its own regressions, file cards, and have agents pick
them up on the next board run. **Monitoring triggers** (`scripts/triggers/`) similarly
evaluate conditions, dedupe with a 1-hour cooldown, and can launch an investigate agent
(`TRIGGERS_AGENT_MODEL`, default `claude-opus-4-8`).

> **Update (2026-07):** the autonomous manager gap is closed — `scripts/agents/runner.ts`
> is a long-running daemon (autopilot board scan, race-safe claim, worktree execution via
> claude-code-headless/codex/api harnesses, merge-or-Review, Telegram/SMS alerts). The
> missions pipeline (`/admin/todo/missions`) turns a typed goal into an epic + tasks, and
> the insights agent (cron, 4h) files `[insights]` cards from analytics.

---

## 7. Skills & markdown files the system uses

| File | Role |
|---|---|
| `.claude/skills/agent-todo/SKILL.md` | The orchestrator: read board → plan waves → dispatch per-task worktree agents → PR → merge/wait. Verification loops via `goal_percentage`/`loop_limit`. |
| `.claude/skills/agent-todo/scripts/todo-cli.ts` | Headless Kanban read/write (board, get, status, pr, set, create, comment). |
| `.claude/skills/agent-todo/scripts/agent-cli.ts` | Headless run lifecycle + memory (run-start/heartbeat/finish/ask/answer, memory-*). |
| `.claude/agents/todo-task-worker.md` | Single-task autonomous worker (picks one card, drives it to a PR). Model: Opus. |
| `lib/agents/model-policy.ts` | Single source of truth for tier→model + `resolveExecution()` precedence. |
| `lib/db/todos.ts` | `createTodo()`, `fileBugIfAbsent()` — the board's write layer. |
| `lib/admin/performance-tickets.ts` | `runPerformanceHealthCheck()` — turns red/yellow perf into cards. |
| `scripts/metrics/visual-qa-report.ts` | Nightly screenshot judge + digest + auto-ticket caller. |
| `scripts/triggers/{index,evaluate,investigate}.ts` | Monitoring triggers + investigate agent. |
| `.claude/memory/*` | Project-scoped agent memory (durable knowledge across runs). |
| `CLAUDE.md` | Repo-wide guidance every agent reads (bias-to-action, deploy flow, conventions). |
| `docs/MULTI_AGENT_PM_SPEC.md` | Forward-looking product spec: manager loop, multi-runtime adapters, autonomy policy, automations engine. |
| `docs/CI-CD.md` | Self-hosted Hetzner runner topology + deploy flow. |

---

## 8. Installation — orchestrator & AI project manager

Full agent-executable procedure: **[`install.md`](install.md)**. Design contract:

- **Drop it in any project.** Flow runs on the toolchain that is already installed — JS, Python,
  Rust, Go — and adds **no new runtime dependency and no new build step**. It *detects* your test /
  lint / build commands and calls them; those become the verification hooks behind
  `goal_percentage` / `loop_limit`.
- **One addition to the repo.** An agent already running on your machine knows what to do after a
  single skill is added: `.claude/skills/flow-agent-orchestrator/`. Nothing more.
- **Two deployment shapes.** Standalone admin panel beside your platform, or **integrated into it**.
  Integrated is better: it shares your **RBAC/ACL** (same users, roles, permissions), your
  **database**, and your **general knowledge**, so agents read your domain instead of guessing.
- **Install = drop the code, then ask the agent to run `install.md`.** It cuts a
  `flow/pre-install` snapshot branch first, detects the stack, mounts the board and API behind your
  existing auth, wires the skill and CLIs, and finishes with a smoke test that drives one real card
  to a PR under your own CI.

### Uninstall

Removal is easy — delete the skill, drop the board routes, drop or keep the tables. What removal
does **not** undo is the work the agents did: those are ordinary commits in your history. The only
full revert is `git checkout flow/pre-install`. So test it thoroughly on a real but non-critical
slice of the backlog, with automerge off, keep the snapshot branch until you're satisfied, and be
ready to revert everything if it isn't working for you. We strongly believe that once you've tried
the Orchestrator you won't roll back.

---

## 9. Where this is going (one-line summary)

Today: a **fully instrumented, self-driving** orchestrator — a runner daemon takes board
cards (and decomposed missions) to merged PRs in parallel worktrees, feeds itself work
via nightly sweeps + the insights agent, and shows it all live. Next: **prompt/run
snapshots with rollback + MCTS-style fork** (§4d), **goals on the dashboard translated
into board work** (§5c), the **tracking pillars** unified on the dashboard (§5b),
**per-card autonomy policy**, and an **automations/hooks engine** — plus the
orchestrator-native metrics in §5d so we can actually measure agent productivity.
