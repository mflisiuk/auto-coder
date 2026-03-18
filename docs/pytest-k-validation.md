# Pytest -k Validation & Auto-Fix

## Problem

Pytest's `-k` option uses **Python boolean expressions**, not regular expressions. This is a common source of errors when writing task specifications.

### Incorrect (Regex Syntax)
```bash
pytest -k "test_login|test_logout"  # WRONG: | is regex OR
pytest -k "test_a&test_b"            # WRONG: & is regex AND
pytest -k "!test_skip"               # WRONG: ! is regex NOT
```

### Correct (Python Boolean Expressions)
```bash
pytest -k "test_login or test_logout"  # CORRECT
pytest -k "test_a and test_b"          # CORRECT
pytest -k "not test_skip"              # CORRECT
```

## How Auto-Coder Handles This

### Automatic Detection

When running baseline tests, auto-coder validates all pytest commands for common `-k` syntax errors:

```python
from auto_coder.policy import validate_pytest_k_syntax

commands = ['pytest -k "test_a|test_b"']
warnings = validate_pytest_k_syntax(commands)
# Returns: ['Command 0: regex operator "|" in -k expression']
```

### Automatic Fix

The system automatically applies corrections before running tests:

```python
from auto_coder.policy import fix_pytest_k_syntax

fixed = fix_pytest_k_syntax(commands)
# Returns: ['pytest -k "test_a or test_b"']
```

### Runtime Behavior

When you run `auto-coder run --live`, you'll see warnings like:

```
[pytest-k WARNING] Command 0: regex operator "|" in -k expression
[pytest-k AUTO-FIX] Applying automatic correction...
```

The corrected commands are then used for:
1. Baseline test execution
2. Repair task generation (fixed commands stored in task dict)

## Supported Fixes

| Regex Operator | Python Equivalent | Example |
|---------------|-------------------|---------|
| `|` | ` or ` | `test_a\|test_b` → `test_a or test_b` |
| `&` | ` and ` | `test_a&test_b` → `test_a and test_b` |
| `!` | ` not ` | `!test_skip` → ` not test_skip` |

## Best Practices

### For Task Authors

1. **Use correct syntax from the start** — write `or`, `and`, `not` instead of `|`, `&`, `!`
2. **Test your pytest commands locally** before adding to task-spec:
   ```bash
   pytest -k "test_login or test_logout" -v
   ```
3. **Use quotes around expressions** — always wrap `-k` values in single or double quotes

### Example Task Specification

```yaml
tasks:
  - name: Implement user authentication
    baseline_commands:
      - pytest -k "test_login or test_logout" tests/auth/
      - pytest -k "not test_skip_slow" tests/integration/
    test_commands:
      - pytest tests/auth/
```

## Implementation Details

### Validation Function

```python
def validate_pytest_k_syntax(commands: list[str]) -> list[str]:
    """Validate pytest -k expressions for common syntax errors.
    
    Returns list of warnings for commands with invalid syntax.
    """
```

### Fix Function

```python
def fix_pytest_k_syntax(commands: list[str]) -> list[str]:
    """Apply automatic fixes for common pytest -k syntax errors.
    
    Replaces | with ' or ', & with ' and ', ! with ' not '.
    """
```

### Integration Point

Validation happens in `orchestrator.run_one_task()` before baseline test execution:

```python
# Validate and auto-fix pytest -k syntax
k_warnings = validate_pytest_k_syntax(baseline_commands)
for warning in k_warnings:
    print(f"[pytest-k WARNING] {warning}")
    print(f"[pytest-k AUTO-FIX] Applying automatic correction...")
if k_warnings:
    baseline_commands = fix_pytest_k_syntax(baseline_commands)
```

## Related Documentation

- [Execution Policy](docs/execution.md) — How test commands are validated and executed
- [Operator Runbook](docs/operator-runbook.md) — Troubleshooting test failures
- [Common Pitfalls](docs/common-pitfalls.md) — Other common syntax errors to avoid
