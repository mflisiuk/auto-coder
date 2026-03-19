# Common Pitfalls for Auto-Coder Agents

**READ THIS FILE BEFORE MAKING ANY CHANGES**

This document lists common mistakes that agents make when working with auto-coder tasks.
Avoiding these pitfalls will significantly improve success rates.

---

## Python Command

### PITFALL: Using `python` instead of `python3`

**WRONG:**
```yaml
completion_commands:
  - python -c "import mymodule"
```

**CORRECT:**
```yaml
completion_commands:
  - python3 -c "import mymodule"
```

**Why:** On most Linux systems, `python` is not symlinked to `python3`. The command `python` often doesn't exist or points to Python 2. Always use `python3` explicitly.

**Detection:** Exit code 127 (command not found) when running Python commands.

---

## Test Frameworks

### PITFALL: Using pytest -k with special characters

**WRONG:**
```yaml
completion_commands:
  - pytest -k "test_my_function(with_args)"
```

**CORRECT:**
```yaml
completion_commands:
  - pytest -k "test_my_function" -k "with_args"
  # Or use proper escaping:
  - pytest -k "test_my_function_and_with_args"
```

**Why:** Parentheses, quotes, and special characters in pytest -k expressions cause parsing errors. Use simple strings or combine multiple -k flags.

---

## File Paths and Coverage

### PITFALL: Forgetting `.coverage` in protected_paths

**WRONG:**
```yaml
protected_paths:
  - README.md
```

**CORRECT:**
```yaml
protected_paths:
  - README.md
  - .coverage
  - __pycache__/
  - "*.pyc"
  - .pytest_cache/
```

**Why:** Running pytest creates `.coverage` files and `__pycache__` directories. If these aren't in protected_paths, the policy engine will flag them as violations even though they're auto-generated artifacts.

---

## Working Directory

### PITFALL: Not using `cd` in cron commands

**WRONG:**
```
15 * * * * auto-coder run --live
```

**CORRECT:**
```
15 * * * * bash -c "cd /home/ubuntu/myrepo && auto-coder run --live"
```

**Why:** auto-coder needs to run from the repository root to find `.auto-coder/config.yaml`. Cron jobs run from the home directory by default.

---

## Test Collection

### PITFALL: Tests not being collected (pytest exit 5)

**Status:** Exit code 5 from pytest means "no tests collected". This is now treated as a baseline PASS (not a failure) because it may indicate the test structure is still being built.

**Action:** If you see exit code 5, check if:
1. Test files exist in the expected location
2. Test functions start with `test_`
3. Test files are named `test_*.py` or `*_test.py`

---

## Import Guards

### PITFALL: Not using import guards for optional dependencies

**WRONG:**
```python
from google.auth import default
```

**CORRECT:**
```python
try:
    from google.auth import default
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False
    default = None
```

**Why:** Not all environments have all dependencies installed. Use import guards and provide graceful fallbacks.

---

## JSON Output

### PITFALL: Mixing human output with JSON output

**WRONG:**
```python
print("Starting process...")
print(json.dumps(result))
```

**CORRECT:**
```python
# Human output to stderr
import sys
print("Starting process...", file=sys.stderr)
# JSON output to stdout only
print(json.dumps(result))
```

**Why:** auto-coder expects clean JSON on stdout. Any extra output breaks JSON parsing. Use stderr for human-readable logs.

---

## Allowed Paths

### PITFALL: Using `*` or `**` incorrectly

**Note:** Recent versions of auto-coder now properly handle `*` and `**` in allowed_paths:
- `**` matches any number of directories
- `*` matches any single path component

**Example:**
```yaml
allowed_paths:
  - src/**/*.py     # All Python files under src/
  - tests/          # Everything under tests/
```

---

## Policy Violations

### PITFALL: Creating files outside allowed_paths

**Symptom:** "Policy violations: outside_allowed:filename"

**Fix:** Either:
1. Add the file pattern to `allowed_paths` if it's intentional
2. Add to `protected_paths` if it's an auto-generated artifact that should be ignored
3. Don't create the file if it's not needed

---

## Baseline vs Completion Commands

### PITFALL: Confusing baseline_commands with completion_commands

- `baseline_commands`: Run BEFORE the agent starts work. Used to verify the starting state.
- `completion_commands`: Run AFTER the agent finishes work. Used to verify the changes.

**Common mistake:** Putting verification in baseline_commands that expects the agent's changes.

---

## Exit Codes

### Standard Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Continue |
| 1 | General error | Check output |
| 2 | Misuse of command | Fix command syntax |
| 5 | No tests collected (pytest) | Treated as pass |
| 127 | Command not found | Fix command path or use full path |

---

## Checklist Before Submitting

- [ ] All Python commands use `python3` not `python`
- [ ] `.coverage` and `__pycache__/` in protected_paths
- [ ] JSON output only on stdout, logs on stderr
- [ ] Import guards for optional dependencies
- [ ] Test file names follow `test_*.py` convention
- [ ] Cron jobs include `cd /path/to/repo &&`

---

## Version

- Last updated: 2026-03-19
- Auto-coder version: Check with `auto-coder --version`
