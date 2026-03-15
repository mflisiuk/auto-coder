# auto-coder v1 - Architecture

## Goal

`auto-coder` is an autonomous software delivery system.

The human provides product direction and project constraints. The system:

- turns roadmap context into concrete tasks
- turns tasks into small executable work orders
- picks a manager backend
- picks a coding worker based on quota and availability
- runs work in an isolated git worktree
- reviews the result
- retries with feedback until done or blocked
- commits and optionally pushes completed work

The v1 target is unattended execution with periodic ticks, not a one-shot nightly batch.

## Operating Model

The system should be designed around a recurring manager tick.

Typical loop:

1. cron wakes the manager every `N` minutes
2. manager checks active leases, quota, and pending work
3. manager creates or resumes a small work order
4. worker executes the work order
5. worker leaves a required final report
6. manager reviews artifacts and either:
   - marks work complete
   - issues feedback and queues another attempt
   - waits for quota reset
   - blocks the task

Hourly cron is acceptable as a safe default, but if the goal is to consume paid quotas efficiently, the tick interval should be configurable. In practice, `10-15` minute ticks are better than once per night and usually better than once per hour.

## Core Principles

1. Deterministic gates before LLM judgment.
2. Persistent state across restarts is mandatory.
3. A task is a contract, but a work order is the real execution unit.
4. Manager backends, worker adapters, and quota probes must be swappable.
5. Quota exhaustion is a first-class state, not a generic failure.
6. Retry loops must converge or stop.
7. Protected branches and paths must be enforced by policy, not trust.

## Human Inputs

Minimum input:

- `ROADMAP.md`
- `PROJECT.md`

Recommended input:

- `ROADMAP.md`
  Loose product roadmap, modules, milestones, business order.
- `PROJECT.md`
  Tech stack, repo structure, test/build commands, forbidden paths, repo conventions.
- `CONSTRAINTS.md`
  Hard constraints such as "no new dependencies", "do not touch auth", "no infra changes".
- `ARCHITECTURE_NOTES.md`
  Optional architectural intent if there are strong design constraints.

The system should work with only `ROADMAP.md` and `PROJECT.md`, but planning quality improves significantly with explicit constraints.

The planner must be intentionally strict:

- if the brief is too vague to derive deterministic tasks, planning must fail
- the system must not silently invent missing requirements
- the rejection path must list exactly what is missing or contradictory

Expected rejection style:

- `brief niejasny - brakuje X, Y, Z`

## System Boundaries

### Manager Backends

Only two manager backends are in scope:

- Anthropic via Python SDK
- Codex via Codex SDK

No other manager backends are in scope for v1.

Implementation note:

- Anthropic manager can be implemented natively in Python.
- Codex manager should be treated as a bridge backend from the Python core to a Codex SDK helper process, with persisted thread or session state stored in SQLite.

The manager interface must therefore be provider-neutral and resumable across ticks.

### Coding Workers

Workers are separate from the manager backend. Supported worker families:

- `cc`
- `cch`
- `ccg`
- `qwen`
- `gemini`
- `codex`

Workers are CLI-driven subprocesses. The core system should not depend on a single coding provider.

### Quota Awareness

Quota must be checked per provider before issuing a new work order whenever possible.

Examples:

- `ccg`: explicit usage query through a provider-specific probe
- `cc`: usage/status probe if available, otherwise local accounting plus observed rate-limit signals
- `cch`: likely the default fallback if limits are effectively non-problematic
- others: either provider-specific probe or fallback to local token accounting and `429` detection

Quota detection and quota querying are separate concerns.

## High-Level Architecture

```text
auto_coder/
  cli.py
  brief_validator.py
  config.py
  models.py
  storage.py
  scheduler.py
  executor.py
  reviewer.py
  planner.py
  policy.py
  git_ops.py
  reports.py
  managers/
    base.py
    anthropic.py
    codex_bridge.py
  workers/
    base.py
    claude_code.py
    codex_cli.py
    generic_cli.py
  quota/
    base.py
    ccg.py
    cc.py
    local_counter.py
  prompts/
    planner.py
    manager_review.py
    worker_instruction.py
```

## Module Responsibilities

- `cli.py`
  Thin commands only: `init`, `plan`, `run`, `status`, `doctor`, `migrate`.

- `brief_validator.py`
  Validates human input files before planning and rejects underspecified briefs with a structured explanation.

- `config.py`
  Repo discovery, config defaults, path resolution, schema validation.

- `models.py`
  Domain models and enums for tasks, work orders, attempts, run ticks, leases, reviews, usage.

- `storage.py`
  SQLite persistence and query helpers. This is the source of truth.

- `scheduler.py`
  Chooses the next executable work based on dependencies, priority, retry state, quota state, and leases.

- `executor.py`
  Runs one work order attempt in a worktree.

- `reviewer.py`
  Runs deterministic review and optional manager LLM review.

- `planner.py`
  Converts repo docs into a validated backlog of tasks with stable IDs.

- `policy.py`
  Enforces allowed paths, protected paths, diff size budgets, secret scan, binary file rules, branch rules.

- `git_ops.py`
  Creates worktrees, branches, commits, pushes, and cleanup behavior.

- `reports.py`
  Stores run and attempt artifacts under `.auto-coder/reports/`.

- `managers/*`
  Backends used by the manager for planning and review.

- `workers/*`
  Adapters used to run coding CLIs.

- `quota/*`
  Adapters used to query or estimate provider quota and decide routing.

## Why SQLite, Not JSON

Persistent JSON files are acceptable for artifacts and exports, but not as the source of truth.

The system needs:

- restart-safe state
- attempt history
- manager feedback history
- lease handling
- quota snapshots
- task/work order querying
- auditability

`sqlite3` is in the standard library and is a strong fit for v1.

Artifacts such as logs, prompts, diffs, and worker reports should live on disk. SQLite should store metadata and references.

## Core Domain Model

### Task

A task is a durable backlog item derived from planning.

Task fields:

- `id`
- `title`
- `description`
- `priority`
- `enabled`
- `depends_on`
- `allowed_paths`
- `protected_paths`
- `baseline_commands`
- `completion_commands`
- `acceptance_criteria`
- `preferred_workers`
- `risk_level`
- `max_attempts_total`
- `cooldown_minutes`
- `estimated_effort`
- `estimated_tokens`

### Work Order

A work order is the unit actually given to a coding worker.

One task may require several work orders over time.

Work order fields:

- `id`
- `task_id`
- `sequence_no`
- `goal`
- `scope_summary`
- `allowed_paths`
- `completion_commands`
- `selected_worker`
- `manager_feedback`
- `status`
- `retry_after`
- `created_by`

### Attempt

An attempt is one execution of one work order by one coding worker.

Attempt fields:

- `id`
- `run_tick_id`
- `task_id`
- `work_order_id`
- `attempt_no`
- `worker_name`
- `worker_command`
- `worker_returncode`
- `quota_probe_snapshot`
- `tokens_used`
- `changed_files`
- `diff_stat`
- `policy_result`
- `test_result`
- `worker_report_path`
- `review_result`
- `failure_signature`
- `started_at`
- `finished_at`

### Run Tick

A run tick is a single invocation of `auto-coder run`.

Run tick fields:

- `id`
- `started_at`
- `finished_at`
- `host`
- `pid`
- `selected_task_id`
- `selected_work_order_id`
- `outcome`
- `exit_code`

### Lease

A lease prevents duplicate work on the same task or work order.

Lease fields:

- `resource_type`
- `resource_id`
- `run_tick_id`
- `owner_pid`
- `heartbeat_at`
- `expires_at`

### Quota Snapshot

A quota snapshot records provider availability at a point in time.

Fields:

- `provider`
- `checked_at`
- `usage_ratio`
- `remaining_estimate`
- `quota_state`
- `raw_payload_path`

## Recommended Database Tables

- `tasks`
- `work_orders`
- `attempts`
- `run_ticks`
- `leases`
- `manager_threads`
- `provider_usage`
- `quota_snapshots`
- `events`
- `artifacts`

This structure is intentionally future-proof for multi-developer execution, even if v1 runs only one active developer at a time.

`manager_threads` should store at least:

- `task_id`
- `manager_backend`
- `thread_key`
- `external_thread_id`
- `state_payload`
- `updated_at`

## State Model

### Task Statuses

- `waiting_for_dependency`
- `ready`
- `leased`
- `running`
- `waiting_for_retry`
- `waiting_for_quota`
- `blocked`
- `completed`
- `abandoned`

### Work Order Statuses

- `queued`
- `selected`
- `running`
- `needs_review`
- `retry_pending`
- `quota_delayed`
- `completed`
- `cancelled`

### Attempt Statuses

- `started`
- `worker_failed`
- `quota_exhausted`
- `no_changes`
- `policy_failed`
- `tests_failed`
- `review_failed`
- `approved`
- `interrupted`

`waiting_for_quota` is not a generic failure. It must preserve task continuity and avoid burning retries unnecessarily.

## Manager vs Worker vs Quota Probe

These roles must stay separate.

### Manager Backend

The manager backend is responsible for:

- planning tasks from docs
- converting task context into a concrete work order
- reviewing results
- generating retry feedback
- deciding `approve`, `retry`, or `block`

The manager backend is not responsible for:

- running coding CLIs
- parsing git diffs directly from subprocesses
- checking provider usage

### Worker Adapter

The worker adapter is responsible for:

- launching the coding CLI
- passing the prompt
- capturing stdout and stderr
- parsing provider-specific output
- extracting token usage if available
- identifying `429` or quota exhaustion from process output
- ensuring a required final report exists

### Quota Probe

The quota probe is responsible for:

- checking provider usage before starting new work
- estimating whether a provider should be avoided for now
- marking a provider as `healthy`, `near_limit`, or `exhausted`
- storing raw probe payload for auditability

It must not run coding work.

## Contracts

### Manager Backend Contract

Each manager backend must implement:

- `name()`
- `is_available(config)`
- `plan_tasks(context) -> list[TaskSpec]`
- `create_work_order(task, history, repo_context) -> WorkOrderSpec`
- `review_attempt(task, work_order, attempt_context, history) -> ReviewDecision`
- `load_thread(task_id) -> ManagerThread | None`
- `save_thread(task_id, thread_state) -> None`

For Python core plus Codex SDK, the Codex manager backend should be treated as a bridge process. The Python core should not embed provider-specific assumptions into scheduling logic.

The goal is:

- same scheduler
- same reviewer pipeline
- same stored task history
- different manager backend implementation behind one interface

### Worker Adapter Contract

Each worker adapter must implement:

- `name()`
- `is_installed()`
- `build_command(work_order, config)`
- `run(work_order, prompt, worktree, report_dir, timeout_minutes)`
- `parse_usage(stdout, stderr)`
- `detect_quota_exhaustion(stdout, stderr)`
- `extract_final_report(worktree)`

Normalized worker result must include:

- worker name
- command
- return code
- stdout
- stderr
- token usage
- quota exhausted flag
- final report payload

### Quota Probe Contract

Each quota probe must implement:

- `provider_name()`
- `is_available()`
- `check_quota(config) -> QuotaSnapshot`
- `should_accept_work(snapshot, estimated_tokens) -> bool`
- `retry_after(snapshot) -> datetime | None`

If no provider-native probe exists, the fallback is:

- local token accounting
- recent `429` history
- conservative cooldown

## Worker Final Report Contract

Every coding worker must leave a machine-readable final report in the worktree root.

Suggested filename:

- `AGENT_REPORT.json`

Suggested structure:

```json
{
  "status": "completed | partial | blocked | quota_exhausted",
  "summary": "Short textual summary",
  "completed_items": ["..."],
  "remaining_items": ["..."],
  "blockers": ["..."],
  "tests_run": ["..."],
  "files_touched": ["..."],
  "next_recommended_step": "..."
}
```

This report is not trusted on its own. It is one review input among several:

- git diff
- changed files
- test results
- policy results
- previous history

## Tick Execution Flow

One `auto-coder run` tick should behave like this:

1. Load config and open SQLite.
2. Register a `run_tick`.
3. Expire stale leases and mark interrupted attempts.
4. Refresh task readiness from dependencies and cooldowns.
5. Refresh recent quota snapshots if probes are available.
6. Scheduler selects the best candidate task.
7. Manager backend derives the next work order for that task.
8. Scheduler chooses a worker based on:
   - task preference
   - worker availability
   - quota probe state
   - estimated work size
9. Scheduler creates a lease.
10. Executor creates worktree and branch.
11. Executor runs baseline commands.
12. Executor builds worker prompt from:
   - work order goal
   - task contract
   - path policy
   - prior manager feedback
13. Worker adapter runs the coding CLI.
14. Executor saves artifacts and parses final report.
15. Policy engine validates changed files and safety rules.
16. Executor runs completion commands.
17. Reviewer applies deterministic gates.
18. If deterministic gates pass, manager backend reviews the attempt.
19. Result handling:
   - `approve` -> commit, optional push, mark work complete
   - `retry` -> store feedback, set retry delay, queue next attempt
   - `quota_exhausted` -> set `waiting_for_quota`
   - `block` -> mark task `blocked`
20. Release lease and finalize run tick.

## Scheduling Rules

The scheduler must be strict and boring.

Selection rules:

- only enabled tasks
- only tasks whose dependencies are completed
- skip tasks under retry cooldown
- skip tasks waiting for quota reset
- skip tasks over `max_attempts_total`
- skip tasks with active lease
- prefer lower `priority`
- prefer smaller work if a provider is near quota limit

Blocking rules:

- baseline failure blocks immediately
- repeated identical failure signatures block after threshold
- missing worker binary blocks the worker, not the entire repo
- missing manager backend blocks planning/review features, not deterministic execution

Quota rules:

- if provider quota is above configured threshold, scheduler should prefer another worker
- if a worker returns `429`, mark provider exhausted and compute `retry_after`
- quota exhaustion should not count the same as a logic failure

## Failure Signatures

The system must not spin forever.

Examples:

- `baseline_failed:python -m pytest tests/test_api.py`
- `policy_failed:outside_allowed:auto_coder/cli.py`
- `tests_failed:python -m pytest tests/test_router.py`
- `review_failed:acceptance_not_met`
- `quota_exhausted:ccg`

If the same failure signature repeats `N` times in a row for a task or work order, the task becomes `blocked`.

Suggested default:

- `N = 3`

Quota signatures are special:

- repeated `quota_exhausted` should delay, not block, unless the provider has no realistic recovery path

## Planner Design

Planner input:

- `ROADMAP.md`
- `PROJECT.md`
- optional `CONSTRAINTS.md`
- optional `ARCHITECTURE_NOTES.md`
- repo file listing
- existing test/build commands if detectable

Planner output:

- `tasks.generated.yaml`

Planner precondition:

- brief validation must pass before any LLM planning call

Planner requirements:

- stable `task_id`
- explicit `depends_on`
- explicit `allowed_paths`
- explicit `baseline_commands`
- explicit `completion_commands`
- acceptance criteria per task
- tasks small enough to split into one or a few work orders

Planner rejection rules:

- missing `ROADMAP.md` or `PROJECT.md`
- missing required sections in input files
- no executable verification commands
- no editable or protected path policy
- roadmap lacks ordering or scope boundaries
- constraints contradict project or roadmap requirements
- acceptance criteria are too vague to become review gates

Manual override layer:

- `tasks.local.yaml`

Effective plan:

- generated tasks
- merged with local overrides
- validated before insertion into SQLite

Suggested rejection payload:

```json
{
  "status": "rejected",
  "summary": "brief niejasny - brakuje wymaganych informacji",
  "missing_files": [],
  "missing_sections": [],
  "ambiguous_points": [],
  "contradictions": [],
  "next_actions": []
}
```

## Review Policy

The approval gate for v1 is:

1. baseline commands passed before coding
2. worker exited in a usable state
3. worker final report exists
4. changed files stay inside allowed scope
5. protected paths are untouched
6. no secret or forbidden binary policy violation
7. completion commands pass
8. manager backend returns `approve`

LLM review is used for:

- concrete feedback
- identifying incomplete implementation
- deciding between retry and block

It is not used as the only safety boundary.

## Brief Validation

Input validation should happen before planning and should be deterministic.

Minimum required files:

- `ROADMAP.md`
- `PROJECT.md`

Required `ROADMAP.md` content:

- project goal
- target user
- ordered milestones or modules
- in-scope items
- out-of-scope items
- acceptance criteria

Required `PROJECT.md` content:

- tech stack
- repo structure
- run and test commands
- editable paths
- protected paths
- environment assumptions

The validator should reject instead of guessing.

Reference materials for input quality should live in:

- `INPUT_SPEC.md`
- `example-project/`

## Git Policy

V1 git policy should be conservative.

- all coding happens in dedicated worktrees
- every work order runs on a task branch
- no direct commits to `main`
- `auto_commit` allowed
- `auto_push` allowed to task branch
- `auto_merge` out of scope for v1

Branch format:

- `ai/<task-id>/<work-order-seq>/<timestamp>`

Commit format:

- `chore(ai): <task title> [auto-coder]`

## Reports and Artifacts

Each run tick should write artifacts under:

```text
.auto-coder/
  reports/
    ticks/<run-tick-id>/
      run.json
      prompt.txt
      review.json
      policy.json
      quota.json
      changed-files.json
      worker.stdout.log
      worker.stderr.log
      AGENT_REPORT.json
      baseline/
      completion/
```

The database should reference those paths instead of storing large blobs.

## Security and Isolation

If the promise is "unattended coding", worktree isolation alone is not sufficient.

Minimum v1 posture:

- no production credentials in worker environment by default
- env allowlist passed to workers
- protected path enforcement
- no direct push to protected branches
- secret scan on changed files

Recommended next step after v1:

- dedicated OS user for workers
- optional containerized execution

## Recovery and Operations

Operational assumptions:

- ticks are periodic
- the previous process may have crashed
- quota may be exhausted for some providers but not others
- manager feedback and attempt history must survive restarts

Recovery rules:

- leases expire if no heartbeat is seen
- stale worktrees are cleaned on startup
- interrupted attempts are marked `interrupted`
- tasks in `waiting_for_quota` remain visible with `retry_after`
- blocked tasks remain visible with the blocking reason

## CLI Surface

v1 CLI should include:

- `auto-coder init`
- `auto-coder doctor`
- `auto-coder plan`
- `auto-coder run`
- `auto-coder status`
- `auto-coder migrate`

`run` means "execute one manager tick", not "run until the entire roadmap is done in one process".

## V1 Scope Boundary

In scope:

- one active developer at a time
- manager backend: Anthropic first, Codex-compatible interface from the start
- multiple worker adapters
- quota-aware routing
- restart-safe unattended execution

Out of scope:

- parallel execution of 2-3 developers
- dashboard
- multi-repo orchestration
- automatic merge to `main`

The design should keep the door open for multi-developer execution later by building around tasks, work orders, leases, and adapters from day one.

## Architecture Success Criteria

The architecture is successful if:

- the process can be killed and resumed without losing manager history
- quota exhaustion delays work instead of corrupting retries
- the system can switch workers without rewriting core logic
- the human only edits roadmap and constraints, not every prompt
- bad tasks converge to `blocked` instead of looping forever
- the same design can later scale from one active developer to several
