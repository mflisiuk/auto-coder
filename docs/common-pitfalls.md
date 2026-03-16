# Common Pitfalls & Solutions

**Universal lessons learned from auto-coder deployments**

This document contains the most common, stupid bugs that prevent auto-coder from working. These are "facepalm" errors that waste hours but have simple fixes.

---

## 🔥 TOP 3 CRITICAL BUGS

### Bug #1: `python` vs `python3` Commands

**The Problem:**
```yaml
# In PROJECT.md or tasks.yaml
baseline_commands:
  - python -m compileall src  # ❌ WRONG
```

**The Error:**
```
bash: line 1: python: command not found
returncode: 127
status: quarantined
```

**Why This Happens:**
- Auto-coder reads PROJECT.md to generate tasks
- If PROJECT.md has `python`, all tasks get `python` commands
- Most Linux systems don't have `python` command (only `python3`)
- Tasks fail baseline → get quarantined → BLOCK EVERYTHING

**The Fix:**
```bash
# In PROJECT.md, line 54:
sed -i 's/python -m/python3 -m/g' PROJECT.md
```

**Prevention:**
- ALWAYS use `python3` in PROJECT.md
- Check with `which python` before using `python`
- Test baseline commands manually before running auto-coder

---

### Bug #2: ANTHROPIC_API_KEY Not Set

**The Problem:**
```bash
# You have:
ANTHROPIC_AUTH_TOKEN=sk-ant-...

# Auto-coder checks:
os.environ.get("ANTHROPIC_API_KEY")  # ❌ NOT FOUND
```

**The Error:**
```
FAIL  manager:anthropic key
RuntimeError: Manager backend unavailable: anthropic
```

**Why This Happens:**
- Auto-coder checks `ANTHROPIC_API_KEY`
- Your system has `ANTHROPIC_AUTH_TOKEN`
- Different variable names → auto-coder can't find the key

**The Fix:**
```bash
# In scripts/auto-coder-live.sh:
export ANTHROPIC_API_KEY="${ANTHROPIC_AUTH_TOKEN:-}"
```

**Prevention:**
- Add API key export to the entry script
- Test with: `auto-coder doctor --probe-live`
- Verify key is set in the actual runtime environment

---

### Bug #3: Manager Disabled by Default

**The Problem:**
```yaml
# In .auto-coder/config.yaml:
manager_enabled: false  # ❌ WRONG
```

**The Error:**
```
RuntimeError: Manager backend unavailable: anthropic
```

**Why This Happens:**
- Auto-coder init creates config with `manager_enabled: false`
- You need to explicitly enable it
- Without manager, no tasks get planned

**The Fix:**
```bash
# In .auto-coder/config.yaml:
sed -i 's/manager_enabled: false/manager_enabled: true/' .auto-coder/config.yaml
```

**Prevention:**
- Always check config after `auto-coder init`
- Run `auto-coder doctor` to verify setup
- Enable manager if you want autonomous development

---

## ⚙️ CONFIGURATION PITFALLS

### Pitfall #4: Wrong Manager Backend

**Problem:**
```yaml
manager_backend: codex  # But you don't have Codex quota
```

**Solution:**
```yaml
manager_backend: anthropic  # Use Claude
```

---

### Pitfall #5: No Fallback Configured

**Problem:**
```yaml
default_worker: ccg
# ccg quota exhausted → no worker available → BLOCKED
```

**Solution - Multi-level fallback chain:**
```yaml
# Worker fallback chain: ccg → cch → gemini → qwen → claude → codex
default_worker: ccg
fallback_worker: cch

providers:
  ccg:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: cch
  cch:
    token_limit_daily: 200000
    quota_threshold: 0.90
    fallback: gemini
  gemini:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: qwen
  qwen:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: claude
  claude:
    token_limit_daily: 500000
    quota_threshold: 0.90
    fallback: codex
  codex:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: null  # End of chain

providers:
  codex:
    fallback: cc  # When Codex quota → use Claude
```

---

### Pitfall #6: Quarantine Blocks Everything

**Problem:**
```
Task fails 3x → quarantined → BLOCKS ALL OTHER TASKS
```

**Why This Happens:**
- Auto-coder creates repair tasks for failures
- If repair tasks also fail → quarantine
- Quarantined tasks prevent new tasks from starting

**Solution:**
```bash
# 1. Fix root cause (e.g., PROJECT.md)
# 2. Disable quarantined tasks in tasks.local.yaml:
cat >> .auto-coder/tasks.local.yaml <<EOF
- id: repair-environment::missing-command-python
  enabled: false
EOF

# 3. Reset state:
rm .auto-coder/state.db .auto-coder/state.json
```

**Prevention:**
- Fix baseline commands before running
- Test baseline commands manually
- Check cron.log for errors

---

## 🔧 OPERATIONAL PITFALLS

### Pitfall #7: Stale Lock Files

**Problem:**
```
RuntimeError: auto-coder already running
```

**Cause:** Previous run crashed without cleaning lock

**Solution:**
```bash
rm .auto-coder/runner.lock .auto-coder/cron.lock
```

**Prevention:**
- Use `flock` in cron (already in `install-cron`)
- Check for lock files before manual runs

---

### Pitfall #8: Doctor Check False Positives

**Problem:**
```bash
$ auto-coder doctor
FAIL  manager:anthropic key

# But auto-coder works fine in cron!
```

**Why This Happens:**
- Test shell lacks environment variables
- Cron environment has different vars

**Solution:**
- Trust actual runs, not just doctor
- Check environment: `env | grep ANTHROPIC`
- Test with same environment as cron

---

### Pitfall #9: Wrong Base Branch

**Problem:**
```yaml
base_branch: feature/old-branch  # Branch doesn't exist
```

**Solution:**
```yaml
base_branch: main  # Use existing branch
worktree_base_ref: "origin/main"
```

---

## 📁 PROJECT STRUCTURE PITFALLS

### Pitfall #10: PROJECT.md Is Source of Truth

**Critical:** Auto-coder generates tasks from PROJECT.md

**If PROJECT.md is wrong → ALL TASKS ARE WRONG**

**Example:**
```markdown
## Verification
\`\`\`bash
python -m compileall src  # ❌ This generates BAD tasks
\`\`\`
```

**Solution:**
- Keep PROJECT.md accurate
- Test all commands in PROJECT.md
- Use correct command names (`python3` not `python`)

---

### Pitfall #11: Missing Dependencies

**Problem:**
```bash
baseline_commands:
  - composer install  # Fails if composer not in PATH
```

**Solution:**
```bash
# Set PATH in scripts/auto-coder-live.sh:
export PATH="/usr/local/bin:/home/ubuntu/.local/bin:$PATH"
```

---

### Pitfall #12: Protected Paths Too Broad

**Problem:**
```yaml
protected_paths:
  - src/  # Can't modify src/ at all
```

**Solution:**
```yaml
protected_paths:
  - src/external_lib/  # Only protect specific subdirs
```

---

## 🧪 TESTING PITFALLS

### Pitfall #13: Baseline Commands Fail

**Problem:**
```bash
baseline_commands:
  - ./vendor/bin/phpunit  # Fails: vendor not installed
```

**Solution:**
```bash
baseline_commands:
  - composer install      # Setup first
  - ./vendor/bin/phpunit  # Then test
```

---

### Pitfall #14: Test Commands Wrong Directory

**Problem:**
```bash
completion_commands:
  - ./vendor/bin/phpunit  # Wrong: not in plugin dir
```

**Solution:**
```bash
completion_commands:
  - cd packages/wp-plugin/agency-elementor && ./vendor/bin/phpunit
```

---

## 🚀 DEPLOYMENT CHECKLIST

Use this checklist when deploying auto-coder to a NEW repo:

- [ ] 1. Check PROJECT.md commands (use `python3` not `python`)
- [ ] 2. Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN
- [ ] 3. Update entry script to export API key
- [ ] 4. Enable manager: `manager_enabled: true`
- [ ] 5. Set manager_backend: `anthropic` or `codex`
- [ ] 6. Configure worker with fallback
- [ ] 7. Run `auto-coder doctor --probe-live`
- [ ] 8. Test run: `auto-coder run`
- [ ] 9. Install cron: `auto-coder install-cron "*/20 * * * *"`
- [ ] 10. Monitor first run: `tail -f .auto-coder/cron.log`

---

## 📊 QUICK REFERENCE

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python: not found` | PROJECT.md has `python` | Change to `python3` |
| `Manager backend unavailable` | `manager_enabled: false` | Set to `true` |
| `auto-coder already running` | Stale lock | `rm .auto-coder/*.lock` |
| Tasks stuck in quarantine | Repeated failures | Fix root + reset state |
| Doctor FAIL but works | Wrong test environment | Ignore if cron works |
| `ANTHROPIC_API_KEY` missing | Wrong var name | Export in script |

---

## 🎓 GOLDEN RULES

1. **ALWAYS use `python3`** - never `python`
2. **Export API key in script** - don't rely on environment
3. **Enable manager explicitly** - not enabled by default
4. **Configure fallback** - Codex → Claude
5. **Test baseline commands** - before running auto-coder
6. **Fix quarantine immediately** - blocks everything
7. **PROJECT.md is truth** - bugs here cascade everywhere

---

## 🔄 EMERGENCY RESET

If auto-coder is completely stuck:

```bash
# 1. Stop everything
pkill -f auto-coder

# 2. Clean locks
rm -f .auto-coder/*.lock

# 3. Reset state (LAST RESORT)
rm -f .auto-coder/state.db .auto-coder/state.json

# 4. Fix root cause
# Edit PROJECT.md, config, etc.

# 5. Restart
auto-coder run
```

---

**Last updated:** 2026-03-16
**Contributors:** auto-coder community lessons learned

**Found a new pitfall?** Please add it here to save others hours of debugging!
