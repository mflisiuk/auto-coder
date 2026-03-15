# auto-coder v1 - Delivery Roadmap

## Product Goal

Build a quota-aware autonomous coding manager that runs in ticks, not in one long fragile session.

The human should be able to provide project intent and constraints, then let the system:

- plan work
- execute work
- review work
- retry with feedback
- wait for quota reset when necessary
- continue later without supervision

## Delivery Principles

1. Persistence and recovery come before sophistication.
2. Quota-aware routing is part of the core product, not a late add-on.
3. Manager and workers must be decoupled from day one.
4. A task is too large to schedule directly; v1 should execute small work orders.
5. Every sprint must end in a runnable vertical slice.

## Recommended Sprint Order

1. Foundations and persistent state
2. Tick engine and single-worker execution
3. Manager review loop and work orders
4. Quota probes and multi-worker routing
5. Planner and backlog synthesis
6. Unattended operations and Codex manager backend

## Sprint 0 - Foundation and Persistent State

### Objective

Create the project skeleton, config model, SQLite storage, and status visibility.

### Files

- `pyproject.toml`
- `auto_coder/__init__.py`
- `auto_coder/brief_validator.py`
- `auto_coder/cli.py`
- `auto_coder/config.py`
- `auto_coder/models.py`
- `auto_coder/storage.py`
- `INPUT_SPEC.md`
- `example-project/README.md`
- `example-project/ROADMAP.md`
- `example-project/PROJECT.md`
- `example-project/CONSTRAINTS.md`
- `example-project/ARCHITECTURE_NOTES.md`
- `tests/test_config.py`
- `tests/test_brief_validator.py`
- `tests/test_storage.py`
- `tests/test_cli.py`
- `example/PROJECT.md`
- `example/config.yaml`

### Tasks

1. Add packaging and `auto-coder` console entrypoint.
2. Implement project root discovery.
3. Implement config loading with defaults for:
   - manager backend
   - worker registry
   - quota thresholds
   - tick interval
   - retry thresholds
4. Create SQLite schema for:
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
5. Implement `auto-coder init`.
6. Implement `auto-coder status`.
7. Implement strict brief validation for required files and sections.
8. Add an example input pack that should pass validation.
9. Add tests for config, DB bootstrapping, and brief validation.

Manager-related storage must already account for both supported manager backends. `manager_threads` is not Anthropic-specific.

### Definition of Done

- `pip install -e .` works.
- `auto-coder init` creates:
  - `.auto-coder/config.yaml`
  - `.auto-coder/state.db`
  - `.auto-coder/reports/`
- `auto-coder init` is idempotent.
- `auto-coder status` works in an empty repo and in a repo with seeded rows.
- storage tests verify required tables exist.
- the brief validator rejects unclear input with explicit missing items.
- the repo contains an `example-project/` showing the expected level of detail.

### Explicit Non-Goals

- no worker execution yet
- no planner yet
- no manager LLM integration yet

## Sprint 1 - Tick Engine and Single Worker

### Objective

Execute one manual work order end-to-end on each manager tick using one coding worker.

### Recommended First Worker

- `cch`

Reason:

- stable fallback profile
- low quota anxiety for the first vertical slice
- keeps early debugging focused on orchestration, not quota

### Files

- `auto_coder/scheduler.py`
- `auto_coder/executor.py`
- `auto_coder/policy.py`
- `auto_coder/git_ops.py`
- `auto_coder/reports.py`
- `auto_coder/workers/base.py`
- `auto_coder/workers/claude_code.py`
- `tests/test_scheduler.py`
- `tests/test_executor.py`
- `tests/test_policy.py`
- `tests/fixtures/manual_tasks.yaml`

### Tasks

1. Implement manual backlog loading from YAML into SQLite.
2. Implement task readiness and work order readiness.
3. Implement a single `run tick`.
4. Implement lease acquisition and release.
5. Implement git worktree creation and cleanup.
6. Implement worker adapter base class.
7. Implement the first worker adapter.
8. Implement worker prompt building.
9. Require the worker to leave `AGENT_REPORT.json`.
10. Save logs and artifacts under `.auto-coder/reports/`.
11. Persist attempt outcomes in DB.

### Definition of Done

- `auto-coder run` executes at most one work order on one tick.
- the run uses a separate git worktree.
- a missing worker report fails the attempt.
- worker stdout, stderr, prompt, changed files, and report metadata are persisted.
- policy can reject changed files outside allowed scope.
- task, work order, and attempt rows are updated consistently.

### Explicit Non-Goals

- no manager review loop yet
- no planner yet
- no quota probe yet

## Sprint 2 - Manager Review Loop and Retry Semantics

### Objective

Add the real manager loop: review, feedback, retry, block, and work-order progression.

### First Manager Backend

- Anthropic via Python SDK

Codex manager compatibility must be reflected in the interfaces now, but the first live implementation can be Anthropic.

Concretely:

- define one `ManagerBackend` interface
- keep manager thread persistence backend-neutral
- do not hardcode Anthropic message formats into storage or scheduler

### Files

- `auto_coder/reviewer.py`
- `auto_coder/managers/base.py`
- `auto_coder/managers/anthropic.py`
- `auto_coder/prompts/manager_review.py`
- `auto_coder/prompts/worker_instruction.py`
- `auto_coder/models.py`
- `auto_coder/storage.py`
- `tests/test_reviewer.py`
- `tests/test_retry_flow.py`
- `tests/test_work_order_progression.py`

### Tasks

1. Define `ReviewDecision`.
2. Define `ManagerBackend` interface:
   - `create_work_order`
   - `review_attempt`
   - `load_thread`
   - `save_thread`
3. Implement deterministic gates:
   - baseline passed
   - worker report exists
   - no policy violations
   - completion commands passed
4. Implement Anthropic manager review backend.
5. Persist manager conversation history per task.
6. Compute failure signatures.
7. Add `waiting_for_retry` state with `retry_after`.
8. Add block-after-repeated-failure logic.
9. Feed previous manager feedback into the next work order prompt.
10. Allow the manager to refine the next work order instead of reusing the same raw task prompt forever.

### Definition of Done

- the second tick can continue a task from previous manager history.
- a failed attempt produces stored feedback for the next attempt.
- repeated identical failures block the task after the configured threshold.
- deterministic failures cannot be overridden by the manager backend.
- manager review artifacts are written for every reviewed attempt.

### Explicit Non-Goals

- no quota-aware routing yet
- no planner yet

## Sprint 3 - Quota Probes and Multi-Worker Routing

### Objective

Make scheduling aware of provider usage and `429` exhaustion so the system can consume paid limits intelligently.

### Files

- `auto_coder/router.py`
- `auto_coder/quota/base.py`
- `auto_coder/quota/ccg.py`
- `auto_coder/quota/cc.py`
- `auto_coder/quota/local_counter.py`
- `auto_coder/workers/codex_cli.py`
- `auto_coder/workers/generic_cli.py`
- `auto_coder/doctor.py`
- `tests/test_router.py`
- `tests/test_quota_probes.py`
- `tests/test_doctor.py`

### Tasks

1. Implement worker registry for:
   - `cc`
   - `cch`
   - `ccg`
   - `codex`
   - `qwen`
   - `gemini`
2. Implement quota probe base interface.
3. Implement `ccg` usage probe adapter.
4. Implement `cc` usage/status probe adapter if available.
5. Implement local token-accounting fallback probe.
6. Persist quota snapshots in DB.
7. Add `waiting_for_quota` state with provider-specific `retry_after`.
8. Route work to alternate workers when the preferred worker is near limit.
9. Distinguish logic failures from quota failures.
10. Expose quota state in `status` and `doctor`.

### Definition of Done

- if `ccg` is above threshold, scheduler can prefer another worker.
- if a worker returns `429`, the task enters `waiting_for_quota`.
- repeated quota exhaustion does not burn through normal retry logic.
- provider usage and quota snapshots are visible in `auto-coder status`.
- worker-specific quota logic is contained in quota probes and adapters, not spread through scheduler and executor.

### Explicit Non-Goals

- no planner yet
- no parallel developers yet

## Sprint 4 - Planner and Backlog Synthesis

### Objective

Generate useful tasks from project docs and store them in a way that the manager can turn into small work orders.

### Files

- `auto_coder/planner.py`
- `auto_coder/brief_validator.py`
- `auto_coder/task_graph.py`
- `auto_coder/prompts/planner.py`
- `auto_coder/managers/anthropic.py`
- `auto_coder/cli.py`
- `tests/test_planner.py`
- `tests/test_task_graph.py`
- `tests/test_task_validation.py`

### Tasks

1. Define task schema validator.
2. Run brief validation before any planner call.
3. Generate `tasks.generated.yaml` from:
   - `ROADMAP.md`
   - `PROJECT.md`
   - optional `CONSTRAINTS.md`
   - optional `ARCHITECTURE_NOTES.md`
4. Preserve stable task IDs across replans.
5. Require explicit:
   - `depends_on`
   - `allowed_paths`
   - `baseline_commands`
   - `completion_commands`
   - `acceptance_criteria`
6. Merge `tasks.generated.yaml` with `tasks.local.yaml`.
7. Insert validated tasks into SQLite.
8. Refuse invalid or underspecified planner output.
9. Refuse to plan when brief validation fails.
10. Add `auto-coder plan`.

### Definition of Done

- `auto-coder plan` can generate a backlog from docs with no hand-written task file.
- `auto-coder plan` fails fast when the brief is unclear.
- every task has valid dependency and path scope data.
- unchanged tasks keep the same IDs across replans.
- generated tasks are suitable inputs for manager-created work orders.
- invalid planner output fails fast with a clear reason.
- invalid human input fails fast with a clear reason and a list of missing items.

### Explicit Non-Goals

- no parallel planning for multiple repos

## Sprint 5 - Unattended Operations and Codex Manager Backend

### Objective

Finish the unattended execution story and add the second supported manager backend.

### Files

- `auto_coder/managers/codex_bridge.py`
- `bridges/codex-manager/package.json`
- `bridges/codex-manager/src/index.ts`
- `auto_coder/storage.py`
- `auto_coder/scheduler.py`
- `auto_coder/git_ops.py`
- `auto_coder/cli.py`
- `auto_coder/migrate.py`
- `README.md`
- `docs/cron.md`
- `docs/inputs.md`
- `tests/test_recovery.py`
- `tests/test_git_ops.py`
- `tests/test_codex_manager_backend.py`

### Tasks

1. Implement stale lease expiry.
2. Mark interrupted attempts on startup.
3. Clean stale worktrees on startup.
4. Add optional auto-commit on approved work.
5. Add optional auto-push to task branches.
6. Implement Codex manager backend bridge behind `ManagerBackend`.
7. Add `doctor` checks for manager backend availability.
8. Document the required human input files and recommended formats.
9. Add migration helpers for legacy task formats if needed.

Codex backend task details:

- Python calls a small Codex bridge process
- bridge owns Codex SDK specifics
- thread or session IDs are persisted in `manager_threads`
- next tick resumes prior manager context instead of starting from scratch

### Definition of Done

- the next tick can recover from a crashed previous process.
- stale leases do not deadlock task execution.
- approved work can be committed automatically.
- approved work can be pushed automatically to a task branch.
- both supported manager backends fit behind the same interface.
- docs explain exactly what the human must prepare for the manager.
- switching manager backend does not require changing scheduler or executor code.

### Explicit Non-Goals

- no direct auto-merge to `main`
- no dashboard

## Required Input Spec for the Human

The system should accept the following input contract by v1:

### Required

- `ROADMAP.md`
  Loose product roadmap and desired milestones.
- `PROJECT.md`
  Repo structure, stack, conventions, test/build commands, forbidden paths.

### Recommended

- `CONSTRAINTS.md`
  Hard rules and no-go areas.
- `ARCHITECTURE_NOTES.md`
  Optional architecture constraints when there are several viable implementations.
- `tasks.local.yaml`
  Manual overrides for generated tasks if the human wants extra control.

If the required files are missing or underspecified, the planner should reject the brief instead of guessing.

## Cross-Sprint Technical Rules

### State Rules

- SQLite is the source of truth.
- file artifacts are referenced by the DB.
- every meaningful transition is persisted before launching side-effecting subprocesses.

### Manager Rules

- only Anthropic and Codex are supported manager backends
- manager logic must go through the `ManagerBackend` interface

### Worker Rules

- all coding workers go through `WorkerAdapter`
- every worker must leave `AGENT_REPORT.json`

### Quota Rules

- quota probing is distinct from worker execution
- `429` creates `waiting_for_quota`, not a normal retry failure
- the scheduler may choose smaller work when quota is tight

### Review Rules

- deterministic gates run before LLM review
- a manager backend may reject good code, but may not approve failed deterministic checks

### Brief Rules

- `plan` must validate the brief before any LLM planning call
- unclear briefs must be rejected with explicit missing items
- the system must not invent missing commands, path scopes, or acceptance criteria

### Git Rules

- all work happens in git worktrees
- no direct commits to `main`
- no direct pushes to protected branches

## V1 Exit Criteria

V1 is complete when all of the following are true:

- `init`, `plan`, `run`, `status`, and `doctor` work in a fresh repo
- the system can be driven by periodic ticks without losing state
- a worker can be swapped without rewriting scheduler logic
- quota-aware routing works for at least `ccg` and one fallback worker
- manager review history survives restarts
- the human can provide roadmap files and let the system continue unattended

## Explicitly Out of Scope for V1

- 2-3 developers working in parallel
- dashboard UI
- multi-repo orchestration
- autonomous merge to `main`

The architecture should prepare for multi-developer scheduling later, but v1 should execute one active developer at a time.
