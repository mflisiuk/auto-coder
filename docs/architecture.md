# Architektura auto-coder

Dokument dla deweloperów — struktura kodu, przepływ danych, jak rozbudowywać.

## Struktura projektu

```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (argparse)
│   ├── orchestrator.py     # Główny orchestrator — run_one_task, worktree management
│   ├── worker.py           # Worker runner — spawn AI subprocessy
│   ├── policy.py           # Validation policy — validate_baseline_spec, path_under
│   ├── cc_bridge.py        # CC-Manager Bridge — integracja z Claude Code
│   ├── git_ops.py          # Git operacje — worktree, merge, push
│   ├── reports.py          # Generowanie raportów
│   └── utils.py            # Helpery
├── bridges/
│   └── cc-manager/
│       ├── src/index.mjs   # Node.js bridge do Claude Code
│       └── package.json
├── docs/                   # Dokumentacja
├── tests/                  # Testy
├── setup.py
└── README.md
```

## Przepływ wykonania

```
┌─────────────┐
│   Brief     │ (ROADMAP.md, PROJECT.md)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ AI Manager  │ (cc/claude — generuje zadania)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Backlog    │ (.auto-coder/tasks/backlog.json)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Orchestrator│ (tworzy worktree, uruchamia workera)
└──────┬──────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
┌─────────────┐ ┌─────────────┐
│ AI Worker   │ │ Baseline    │
│ (ccg/cc)    │ │ Tests       │
└──────┬──────┘ └──────┬──────┘
       │               │
       ▼               ▼
┌─────────────┐ ┌─────────────┐
│ Code Review │ │ Test Report │
└──────┬──────┘ └──────┬──────┘
       │               │
       ▼               ▼
┌─────────────┐
│ Merge/Push  │ (git merge, push, delete branch)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PROGRESS.md │ (aktualizacja statusu)
└─────────────┘
```

## Kluczowe komponenty

### orchestrator.py

Główny orchestrator odpowiedzialny za:
- `run_one_task()` — wykonanie pojedynczego zadania
- `_create_worktree()` — tworzenie izolowanego worktree
- `_baseline_commands()` — generowanie komend baseline
- `run_tests()` — uruchamianie testów baseline i task

### worker.py

Worker runner:
- `spawn_worker()` — tworzy subprocess AI (ccg, cc, etc.)
- `fallback_chain()` — przełączanie przy 429 errors
- PATH augmentation — dla cron/minimal environments

### policy.py

Validation helpers:
- `validate_baseline_spec()` — ostrzeżenia dla nieistniejących plików
- `path_under()` — check czy ścieżka pod prefixem
- `_normalize_prefix()` — normalizacja glob prefixów

### cc_bridge.py

CC-Manager Bridge:
- `CcManagerBridge` — klasa integrująca Claude Code jako manager
- `is_available()` — check z common install locations
- JSON-RPC komunikacja z Node.js bridge

## Jak dodać nowego workera

1. Dodaj entry w `DEFAULT_WORKER_MODELS`:

```python
DEFAULT_WORKER_MODELS = {
    "ccg": "claude-opus-4-6",
    "cc": "claude-opus-4-6",
    "cch": "claude-opus-4-6",
    "gemini": "gemini-2.5-pro",
    "qwen": "qwen-max",  # NOWY
    "codex": "codex-latest",
}
```

2. Zaimplementuj spawn logic w `worker.py`:

```python
def spawn_qwen_worker(task, worktree, config):
    return subprocess.Popen(
        ["qwen", "code", "--worktree", worktree],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
```

3. Dodaj do fallback chain w `orchestrator.py`.

## Jak dodać nowego managera

1. Stwórz bridge class w `auto_coder/`:

```python
class NewManagerBridge:
    def __init__(self, repo_root):
        self.repo_root = repo_root
    
    def is_available(self):
        return shutil.which("new-manager") is not None
    
    def generate_tasks(self, brief):
        # Implement task generation
        pass
```

2. Dodaj do `DEFAULT_MANAGER_MODELS` w `cli.py`.

3. Zaimplementuj `_probe_manager_backend()` dla `doctor --probe-live`.

## Testowanie

```bash
# Uruchom testy jednostkowe
pytest tests/

# Test integracyjny z dry-run
auto-coder run --dry-run --task TEST_TASK

# Debug mode
auto-coder run --live --debug
```

## Rozwiązywanie problemów

### Task zawieszony

```bash
# Sprawdź logi
cat .auto-coder/reports/TASK_ID/stderr.log

# Zabij proces workera
pkill -f "ccg.*TASK_ID"

# Wyczyść worktree
git worktree remove --force .git/worktrees/TASK_ID
```

### Merge conflict

```bash
# Ręczny merge
git checkout main
git merge feature/TASK_ID

# Rozwiąż konflikty
git add .
git commit -m "Resolve merge conflict"

# Push
git push origin main
```
