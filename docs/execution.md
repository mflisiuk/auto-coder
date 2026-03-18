# Execution Engine

Ten dokument opisuje jak `auto-coder` wykonuje testy i interpretuje wyniki.

## Uruchamianie testów

Funkcja `run_tests()` w `executor.py` odpowiada za wykonywanie komend testowych w izolowanym worktree.

### Parametry

```python
def run_tests(
    commands: list[str],
    worktree: Path,
    report_dir: Path,
    timeout_minutes: int,
    *,
    prefix: str = "tests",
    skip_no_tests: bool = False,
) -> tuple[bool, list[dict[str, Any]]]:
```

- `commands` — lista komend do uruchomienia (zwykle pytest)
- `worktree` — ścieżka do izolowanego worktree git
- `report_dir` — gdzie zapisać logi i raporty JSON
- `timeout_minutes` — timeout na każdą komendę
- `prefix` — prefiks dla plików raportów (np. `setup-tests`, `baseline-tests`)
- `skip_no_tests` — czy traktować exit code 5 jako sukces

### Exit codes pytest

| Code | Znaczenie | Domyślna interpretacja |
|------|-----------|------------------------|
| 0 | Wszystkie testy przeszły | ✅ PASS |
| 1-4 | Różne błędy testów | ❌ FAIL |
| 5 | No tests collected | ⚠️ Zależne od kontekstu |

### Handling exit code 5 (No Tests Collected)

Exit code 5 oznacza, że pytest nie znalazł żadnych testów do uruchomienia. Interpretacja zależy od kontekstu:

**Setup/Baseline tests:** ✅ PASS (gdy `skip_no_tests=True`)
- Task może tworzyć pliki z testami od zera
- Brak istniejących testów jest oczekiwany
- Parametr `skip_no_tests=True` jest domyślnie ustawiony dla setup i baseline

**Task tests:** ❌ FAIL (gdy `skip_no_tests=False`)
- Task powinien utworzyć testy
- Brak testów oznacza niezrealizowane zadanie

### Przykład użycia w orchestratorze

```python
# Setup tests - skip_no_tests=True domyślnie
setup_ok, setup_results = run_tests(
    setup_commands, worktree, report_dir,
    config["test_timeout_minutes"], prefix="setup-tests",
    skip_no_tests=True,  # brak testów = OK
)

# Baseline tests - skip_no_tests=True domyślnie
baseline_ok, baseline_results = run_tests(
    baseline_commands, worktree, report_dir,
    config["test_timeout_minutes"], prefix="baseline-tests",
    skip_no_tests=True,  # brak testów = OK
)
```

### Struktura raportu

Po uruchomieniu testów tworzone są:

```
report_dir/
├── {prefix}/
│   ├── test-00.stdout.log
│   ├── test-00.stderr.log
│   └── ...
└── {prefix}.json
```

Format JSON:
```json
{
  "passed": true,
  "results": [
    {
      "index": 0,
      "command": "pytest -xvs tests/",
      "returncode": 0,
      "passed": true,
      "skipped_no_tests": false
    }
  ]
}
```

### Debugowanie

Logi stdout/stderr każdej komendy są zapisywane w `report_dir/{prefix}/`. Przy błędach:

```bash
# Sprawdź stderr ostatniego testu
cat reports/baseline-tests/test-00.stderr.log

# Sprawdź exit code
cat reports/baseline.json | jq '.results[].returncode'
```
