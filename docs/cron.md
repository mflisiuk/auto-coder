# Cron & unattended mode

`auto-coder` does not run as a daemon. You trigger it via an external scheduler (cron). Each invocation is a self-contained tick: pick a task, run it, save state, exit. The next invocation picks up from where the previous left off.

## Why cron (not a persistent daemon)?

- **Quota exhaustion**: workers may hit API rate limits mid-execution. Cron gracefully resumes after cooldown without any process management.
- **Multi-day projects**: tasks can take hours or days. A cron job restarting every 20 min is more resilient than a daemon that needs babysitting.
- **Multi-repo**: easy to add/remove repos from crontab independently.
- **Simplicity**: no PID files, no systemd services, no restart logic.

## Minimal cron (single repo)

Every 20 minutes (recommended):

```cron
*/20 * * * * cd /path/to/repo && auto-coder run --live >> .auto-coder/cron.log 2>&1
```

## Multi-repo cron

```cron
# Each repo runs independently every 20 min
*/20 * * * * cd /home/user/repo-a && auto-coder run --live >> .auto-coder/cron.log 2>&1
*/20 * * * * cd /home/user/repo-b && auto-coder run --live >> .auto-coder/cron.log 2>&1
*/20 * * * * cd /home/user/repo-c && auto-coder run --live >> .auto-coder/cron.log 2>&1
```

Tip: use absolute paths for the auto-coder binary. Find it with `which auto-coder`.

## Interval recommendations

| Interval | Use case |
|---|---|
| 10-20 min | Recommended. Fast feedback loop, good quota utilization. |
| 30-60 min | Conservative. Good if you want to review output before next tick. |
| > 60 min | Only if quota is very tight or you run occasional jobs. |

## Good practices

1. Start with `dry_run: true` — confirm tasks look correct before going live
2. Enable `auto_commit: true` before `auto_push: true`
3. Enable `auto_pr: true` before `auto_merge: true`
4. Keep `review_required: true` during initial rollout — disable only when you trust the setup
5. Always log cron output to `.auto-coder/cron.log`
6. Run `auto-coder doctor --probe-live` manually before first live run

## Monitoring

```bash
# Watch live log
tail -f /path/to/repo/.auto-coder/cron.log

# Check PROGRESS.md on GitHub — it's updated after every tick
# Or locally:
cat /path/to/repo/PROGRESS.md
```

## Loop mode (alternative to cron)

If you prefer a single long-running process instead of cron:

```bash
auto-coder run --live --loop --max-ticks 200
```

This runs ticks continuously until all tasks complete, then exits cleanly. Useful for short projects or CI pipelines.
