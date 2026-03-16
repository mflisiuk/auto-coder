# auto-coder

> An autonomous coding manager: give it a product brief, it generates tasks, dispatches AI workers in isolated git worktrees, reviews results, commits, pushes, and opens PRs — all unattended.

## What it does

`auto-coder` is a Python workflow engine for teams that want to automate feature delivery. It reads product documentation (`ROADMAP.md`, `PROJECT.md`), generates a task backlog via an AI manager backend (`anthropic` or `codex`), runs workers in isolated git worktrees, reviews their output, and merges work into main — ticking forward each time you run it (or via cron).

**Key properties:**
- One installation works for any number of repos — each repo just needs `.auto-coder/` config
- Quota errors (`429`) are never counted as failures — the system waits patiently for quota reset
- `PROGRESS.md` is written to your project root after every tick so GitHub always shows current status
- Program stops cleanly when all tasks are `completed` or in terminal error state
- Cron every 20 min is the recommended deployment model (no persistent daemon needed)

## Quick start

```bash
# 1. Install once globally (works for all your repos)
git clone https://github.com/mflisiuk/auto-coder && cd auto-coder
pip install -e .

# 2. In your target repo — generate a brief from existing docs (optional)
auto-coder bootstrap-brief /path/to/your-repo

# 3. Initialize auto-coder in your target repo
cd /path/to/your-repo
auto-coder init

# 4. Set API key
export ANTHROPIC_API_KEY=sk-ant-...   # or configure codex

# 5. Verify everything works
auto-coder doctor --probe-live

# 6. Generate task backlog from your brief
auto-coder plan

# 7. Dry-run first — no actual code changes
auto-coder run --dry-run

# 8. Go live
auto-coder run --live
```

## Multi-repo setup

`auto-coder` is installed **once** globally. Each repository you want to automate needs its own `.auto-coder/` directory (created by `auto-coder init`). There is **no code duplication**.

```
/home/user/
├── auto-coder/          ← installed once with pip install -e .
├── repo-a/
│   └── .auto-coder/     ← auto-coder init (separate config + state.db)
├── repo-b/
│   └── .auto-coder/
└── repo-c/
    └── .auto-coder/
```

**Cron for multiple repos (every 20 minutes each):**

```cron
# repo-a
*/20 * * * * cd /home/user/repo-a && auto-coder run --live >> .auto-coder/cron.log 2>&1

# repo-b
*/20 * * * * cd /home/user/repo-b && auto-coder run --live >> .auto-coder/cron.log 2>&1

# repo-c
*/20 * * * * cd /home/user/repo-c && auto-coder run --live >> .auto-coder/cron.log 2>&1
```

Each repo manages its own state, quota tracking, and worker execution independently.

## Configuration

After `auto-coder init`, edit `.auto-coder/config.yaml`. Key options:

```yaml
dry_run: false          # set to false to actually run agents

# Git automation
auto_commit: true       # commit worker output
auto_push: true         # push branch to origin
auto_pr: true           # open GitHub PR via gh CLI (requires gh)
auto_merge: true        # auto-merge PR after creation

# Worker
default_worker: cc      # cc = Claude Code (free tier), cch = Claude Code (paid)
fallback_worker: cch    # fallback when quota exhausted on default_worker

# Limits
max_tasks_per_run: 1    # tasks per cron tick
max_attempts_per_task_per_run: 3
failure_block_threshold: 3  # consecutive failures before task is blocked

# Quota handling
quota_cooldown_hours: 4     # wait time after 429 before retrying
```

**Quota errors are never counted as failures.** When a worker hits a 429 rate limit, the task enters `waiting_for_quota` status and resumes automatically on the next cron tick after the cooldown window.

## PROGRESS.md

After every task execution, auto-coder writes `PROGRESS.md` to your project root. This file is always visible on GitHub and shows:

- Summary counts (Total / Done / In progress / Not started / Errors)
- Per-task status with emoji (✅ completed, ⚙️ running, ⏳ waiting for quota, 🔁 retrying, 🚫 blocked, ❌ failed)
- Worker name, attempt count, start/end time, duration
- Error reason for failed tasks
- Detailed error section with last 3 attempt notes for blocked/quarantined tasks

## Features

- Brief validation and task generation via `anthropic` or `codex` manager backends
- Tasks synced to SQLite — survives restarts, cron-safe
- Quota-aware worker routing with automatic fallback chain (`cc` → `cch` → `gemini` → `qwen` → `codex`)
- Workers run in isolated git worktrees — no interference with your working directory
- AI manager reviews worker output; failing review triggers retry with context
- Lease heartbeat system — long-running workers never get killed by stale lease expiry
- `--loop` mode: run continuously until all tasks complete (`auto-coder run --live --loop`)
- `doctor --probe-live` for real API health check
- Auto-generated repair tasks when baseline tests fail

## Documentation

- **[Common pitfalls & solutions](docs/common-pitfalls.md)** — Read this first
- [Setup & configuration](docs/setup.md)
- [Usage guide](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Execution model](docs/execution.md)
- [Brief validation](docs/brief-validation.md)
- [Cron & unattended mode](docs/cron.md)
- [Input pack](docs/inputs.md)
- [Operator runbook](docs/operator-runbook.md)
- [Go-live checklist](docs/go-live-checklist.md)

## Changelog

[CHANGELOG.md](CHANGELOG.md)
