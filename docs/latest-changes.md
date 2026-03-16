## auto-coder Documentation Index

### Core Documentation

| Document | Purpose |
|----------|---------|
| [architecture.md](docs/architecture.md) | System architecture overview, components, data flow |
| [setup.md](docs/setup.md) | Installation and initial configuration guide |
| [usage.md](docs/usage.md) | Complete command reference and workflow examples |
| [common-pitfalls.md](docs/common-pitfalls.md) | Known issues, troubleshooting, solutions |
| [operator-runbook.md](docs/operator-runbook.md) | Day-to-day operator procedures and troubleshooting |

### Technical Deep Dives

| Document | Purpose |
|----------|---------|
| [execution.md](docs/execution.md) | Worker execution model, isolation, retry logic |
| [provider-routing.md](docs/provider-routing.md) | AI provider routing, quota handling, fallback chains |
| [cron.md](docs/cron.md) | Cron deployment model, scheduling, multi-repo setup |
| [inputs.md](docs/inputs.md) | Input specification, brief validation, PLANNING_HINTS |

### Checklists

| Document | Purpose |
|----------|---------|
| [go-live-checklist.md](docs/go-live-checklist.md) | Pre-production validation checklist |
| [pre-mortem.md](docs/pre-mortem.md) | Risk analysis and mitigation strategies |
| [brief-validation.md](docs/brief-validation.md) | Brief validation rules and requirements |

### Quick Reference

**Common commands:**
```bash
auto-coder init                    # Initialize .auto-coder/ in current repo
auto-coder doctor --probe-live     # Health check with real API call
auto-coder plan                    # Generate task backlog from brief
auto-coder run --dry-run           # Execute without code changes
auto-coder run --live              # Execute with real code changes
auto-coder run --live --loop       # Run until all tasks complete
auto-coder bootstrap-brief /path   # Generate brief from existing docs
```

**Status meanings:**
- ✅ `completed` — task finished successfully
- ⚙️ `running` — worker currently executing
- ⏳ `waiting_for_quota` — rate limited, waiting for cooldown
- 🔁 `retrying` — failed review, retrying with context
- 🚫 `blocked` — consecutive failures or baseline blocker
- ❌ `failed` — terminal failure state

**Key properties:**
- Quota errors (429) never count as failures
- Workers run in isolated git worktrees
- SQLite state survives restarts, cron-safe
- Lease heartbeat prevents stale worker kills
