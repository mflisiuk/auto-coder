# Auto-Coder Self-Healing Design

## Date: 2026-03-19

## Problem Statement

Auto-coder creates repair tasks when things fail, but:
1. Repair tasks wait for next cron tick (30 min delay)
2. Same types of failures happen repeatedly across projects
3. No learning from past failures
4. Manual intervention still required

## Patterns Discovered Today

### Pattern 1: python vs python3 (Exit 127)

**Symptom:**
```
completion_commands:
  - python -c "from gtm_cli.auth import GtmAuth..."
# Result: exit 127 (command not found)
```

**Root Cause:** On Ubuntu/Debian, `python` doesn't exist, only `python3`

**Current Fix:** Manual edit to tasks.yaml

**Proposed Auto-Fix:**
```yaml
# Auto-coder should detect exit 127 + "python" in command
# and automatically create repair-environment::python-command
```

### Pattern 2: .coverage outside allowed_paths (Policy Violation)

**Symptom:**
```json
{"violations": ["outside_allowed:.coverage"]}
```

**Root Cause:** Running pytest creates `.coverage` file, but it's not in protected_paths

**Current Fix:** Add `.coverage` to protected_paths in config.yaml

**Proposed Auto-Fix:**
```yaml
# Auto-coder should detect "outside_allowed:.coverage"
# and automatically add to protected_paths
# OR detect pytest in completion_commands and pre-add .coverage
```

### Pattern 3: __pycache__ outside allowed_paths

**Symptom:**
```json
{"violations": ["outside_allowed:gtm_cli/__pycache__/__init__.cpython-312.pyc"]}
```

**Root Cause:** Python creates `__pycache__/` when importing modules

**Current Fix:** Add `__pycache__/` to protected_paths

**Proposed Auto-Fix:**
```yaml
# Auto-coder should auto-add common Python artifacts to protected_paths:
# - __pycache__/
# - "*.pyc"
# - "*.pyo"
# - .pytest_cache/
# - .coverage
# - .mypy_cache/
```

### Pattern 4: YAML Colons in Strings

**Symptom:**
```yaml
prompt: Add subcommands: capabilities, doctor, tools list
# YAML parser fails on unquoted colon
```

**Root Cause:** YAML treats colons as key-value separators

**Current Fix:** Quote the string

**Proposed Auto-Fix:**
```python
# Auto-coder should validate tasks.yaml after agent edits
# If YAML parse fails, auto-quote problematic strings
```

## Self-Healing Architecture

### Level 1: Pre-emptive Protection (Before Agent Runs)

```yaml
# In config.yaml
auto_protected_patterns:
  python_project:
    - __pycache__/
    - "*.pyc"
    - .pytest_cache/
    - .coverage
    - .mypy_cache/
    - "*.egg-info/"
    - dist/
    - build/
  node_project:
    - node_modules/
    - dist/
    - ".next/"
    - "*.tsbuildinfo"
```

### Level 2: Command Normalization (Before Execution)

```python
def normalize_command(cmd: str) -> str:
    """Auto-fix common command issues before execution."""
    # python -> python3
    cmd = re.sub(r'(^|\s)python\s+-', r'\1python3 -', cmd)
    cmd = re.sub(r'(^|\s)python\s+-c', r'\1python3 -c', cmd)

    # pytest --cov without .coverage in protected
    if 'pytest' in cmd and '--cov' in cmd:
        ensure_protected('.coverage')

    return cmd
```

### Level 3: Failure Classification + Auto-Repair

```python
FAILURE_PATTERNS = {
    "python_not_found": {
        "detect": lambda r: r.returncode == 127 and "python" in r.command,
        "repair": "replace_python_with_python3",
        "auto_apply": True,
    },
    "coverage_outside_allowed": {
        "detect": lambda r: "outside_allowed:.coverage" in r.violations,
        "repair": "add_coverage_to_protected",
        "auto_apply": True,
    },
    "pycache_outside_allowed": {
        "detect": lambda r: "__pycache__" in str(r.violations),
        "repair": "add_pycache_to_protected",
        "auto_apply": True,
    },
    "yaml_parse_error": {
        "detect": lambda r: "could not find expected" in r.stderr,
        "repair": "quote_yaml_strings",
        "auto_apply": False,  # Needs review
    },
}
```

### Level 4: Learning Loop

```python
class FailureLearner:
    """Capture new failure patterns and suggest fixes."""

    def analyze_failure(self, failure: FailureResult) -> Optional[RepairRecipe]:
        # Check known patterns
        for pattern_id, pattern in FAILURE_PATTERNS.items():
            if pattern["detect"](failure):
                return RepairRecipe(
                    pattern_id=pattern_id,
                    repair_fn=pattern["repair"],
                    auto_apply=pattern["auto_apply"],
                )

        # Unknown pattern - create learning note
        self.capture_unknown_pattern(failure)
        return None

    def capture_unknown_pattern(self, failure: FailureResult):
        """Write to knowledge/failures/ for later analysis."""
        slug = slugify(failure.summary[:50])
        path = f"knowledge/failures/{datetime.now():%Y-%m-%d}_{slug}.md"
        write_file(path, f"""# Unknown Failure Pattern

## Symptom
{failure.summary}

## Context
- Task: {failure.task_id}
- Command: {failure.command}
- Exit code: {failure.returncode}
- Violations: {failure.violations}

## stderr
```
{failure.stderr[:1000]}
```

## Manual Fix Applied
<!-- Fill in after fixing -->
""")
```

## Implementation Plan

### Sprint 1: Pre-emptive Protection (Easy)

1. Add `auto_protected_patterns` to default config
2. Auto-merge these into `protected_paths` based on project type
3. Detect project type from files (pyproject.toml, package.json, etc.)

### Sprint 2: Command Normalization (Medium)

1. Add `normalize_command()` to baseline/completion command execution
2. Log when normalization is applied
3. Track in state DB for learning

### Sprint 3: Failure Classification (Harder)

1. Implement `FailureLearner` class
2. Add known patterns from today's failures
3. Create repair task with correct fix pre-applied

### Sprint 4: Learning Loop (Hardest)

1. Capture unknown patterns to knowledge/failures/
2. Weekly review of unknown patterns
3. Promote common patterns to known patterns

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| Manual interventions per day | ~5-10 | ~1-2 |
| Time to repair | 30 min (next cron) | <1 min (auto) |
| Repeated failures | Yes | No (learned) |
| Knowledge captured | Ad-hoc | Structured |

## Related Files

- `/home/ubuntu/auto-coder/COMMON_PITFALLS.md` - Agent guidance
- `/home/ubuntu/auto-coder/auto_coder/policy.py` - Policy engine
- `/home/ubuntu/auto-coder/auto_coder/orchestrator.py` - Repair task creation
