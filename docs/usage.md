# Usage guide

## Run modes

| Command | What it does |
|---|---|
| `auto-coder run --dry-run` | Validates config and tasks, simulates execution without any real changes |
| `auto-coder run --live` | Full execution: runs worker, commits, pushes, opens PR |
| `auto-coder run --live --loop` | Runs ticks continuously until all tasks complete or `--max-ticks` is reached |
| `auto-coder plan` | Regenerates task backlog from your brief via the AI manager |
| `auto-coder doctor` | Checks configuration, API key presence, worker availability |
| `auto-coder doctor --probe-live` | Same as above + makes a real API call to verify quota is available |
| `auto-coder status` | Shows current task status from SQLite |
| `auto-coder bootstrap-brief /path/to/repo` | Generates brief files (`ROADMAP.md`, `PROJECT.md`) from existing repo docs |

## Scenario 1: New project from scratch

```bash
# 1. Install auto-coder globally (once)
git clone https://github.com/mflisiuk/auto-coder
cd auto-coder && pip install -e .

# 2. Go to your project repo
cd /path/to/my-project

# 3. Initialize auto-coder (creates .auto-coder/ with config.yaml and state.db)
auto-coder init

# 4. Write your brief — these are the input files:
#    ROADMAP.md         (required) - high-level goals, milestones
#    PROJECT.md         (required) - functional specification
#    PLANNING_HINTS.md  (optional) - naming conventions, API style, testing approach
#    CONSTRAINTS.md     (optional) - hard technical constraints
#    ARCHITECTURE_NOTES.md (optional) - architecture decisions

# 5. Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# 6. Verify setup
auto-coder doctor --probe-live

# 7. Generate task backlog
auto-coder plan

# 8. Dry-run first — no real changes
auto-coder run --dry-run

# 9. Enable live execution in config
# .auto-coder/config.yaml: set dry_run: false, auto_commit: true, auto_push: true

# 10. Run live
auto-coder run --live
```

## Scenario 2: Attach to existing repo

```bash
# Generate brief files from your existing docs/code
auto-coder bootstrap-brief /path/to/existing-repo

# With --force to overwrite existing brief files
auto-coder bootstrap-brief /path/to/existing-repo --force

# Then continue with: init → plan → run
```

## Scenario 3: Multi-repo (10+ repos)

Install auto-coder **once**. Each repo gets its own `.auto-coder/` config.

```
auto-coder/           ← git clone here, pip install -e . once
repo-a/
  .auto-coder/        ← auto-coder init inside repo-a
repo-b/
  .auto-coder/        ← auto-coder init inside repo-b
```

Set up crontab for each repo (every 20 min is recommended):

```cron
*/20 * * * * cd /home/user/repo-a && /usr/local/bin/auto-coder run --live >> .auto-coder/cron.log 2>&1
*/20 * * * * cd /home/user/repo-b && /usr/local/bin/auto-coder run --live >> .auto-coder/cron.log 2>&1
```

Find your auto-coder path with: `which auto-coder`

Each repo has independent state, quota tracking, and task history. No shared mutable state.

## Monitoring

**PROGRESS.md** — written to your repo root after every tick. Always visible on GitHub:

```
PROGRESS.md
├── Summary table (Total / Done / In progress / Not started / Errors)
├── Per-task table (status, worker, attempts, timing, error)
└── Error details section (last 3 attempt notes for failed tasks)
```

**Status legend:**
- ✅ completed — task done, merged
- ⚙️ running / leased — worker currently executing
- ⏳ waiting_for_quota — API quota exhausted, will auto-resume after cooldown
- 🔁 waiting_for_retry — failed attempt, scheduled for retry
- ⏸ waiting_for_dependency — blocked on another task completing first
- 🚫 blocked / quarantined — exceeded failure threshold, needs human review
- ❌ baseline_failed / runner_failed — environment or infra error

**Live log monitoring:**

```bash
tail -f .auto-coder/cron.log
```

**Check status from CLI:**

```bash
auto-coder status
auto-coder doctor
```

## Quota handling

When a worker hits a `429` rate limit (quota exhausted):
- The task moves to `waiting_for_quota` status
- **This is never counted as a failed attempt** — it does not move the task toward being blocked
- `retry_after` is set based on `quota_cooldown_hours` (default: 4 hours)
- On the next cron tick after the cooldown, the task is automatically selected again
- If the default worker still has no quota, the fallback chain is tried: `cc` → `cch` → `gemini` → `qwen` → `codex`

## Program exit behavior

- **Cron mode (default):** Each invocation processes `max_tasks_per_run` tasks (default: 1), then exits. The next cron tick continues.
- **Loop mode** (`--loop`): Runs continuously until no ready tasks remain. Exits cleanly when all tasks are `completed`, `blocked`, or `quarantined`. Also exits if tasks are in `waiting_for_quota`/`waiting_for_retry` — re-run after cooldown.

## Git automation config

In `.auto-coder/config.yaml`:

```yaml
auto_commit: true    # git commit worker output
auto_push: true      # git push branch to origin
auto_pr: true        # open GitHub PR (requires gh CLI installed)
auto_merge: true     # auto-merge PR after creation
```

When `auto_pr: true`, after a successful push auto-coder runs:
```
gh pr create --title "chore(ai): <task title> [auto-coder]" --base main --head ai/<branch>
```

When `auto_merge: true`:
```
gh pr merge --squash --auto <pr-url>
```

## Task file format

Tasks are defined in `.auto-coder/tasks.yaml` (auto-generated by `plan`) or can be written manually:

```yaml
tasks:
  - id: "feat-auth"
    title: "Add user authentication"
    prompt: |
      Implement JWT-based authentication with login/logout endpoints.
      Use the existing User model in models/user.py.
    acceptance_criteria:
      - "POST /auth/login returns a JWT token"
      - "Protected routes return 401 without valid token"
    completion_commands:
      - "python -m pytest tests/test_auth.py -v"
    worker: cc           # optional: override default worker
    priority: 10         # lower = higher priority (default: 100)
    depends_on: []       # task IDs that must complete first
```

## Input files

| File | Required | Purpose |
|---|---|---|
| `ROADMAP.md` | Yes | Goals, milestones, feature list |
| `PROJECT.md` | Yes | Functional spec, tech stack, API design |
| `PLANNING_HINTS.md` | Recommended | Naming conventions, test patterns, code style |
| `CONSTRAINTS.md` | Optional | Hard technical limits, what NOT to do |
| `ARCHITECTURE_NOTES.md` | Optional | Architecture decisions, module boundaries |
| `tasks.local.yaml` | Optional | Local task overrides (not committed) |

See also: [Input pack](inputs.md), [Brief validation](brief-validation.md)
