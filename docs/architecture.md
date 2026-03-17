# Architektura auto-coder

Dokumentacja dla deweloperów chcących zrozumieć lub rozbudować `auto-coder`.

## Struktura plików

```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── cli.py              # Główny interfejs CLI
│   ├── config.py           # Konfiguracja i domyślne wartości
│   ├── db.py               # SQLite storage dla tasków i stanu
│   ├── planner.py          # Generowanie backlogu z briefu
│   ├── orchestrator.py     # Główny engine wykonawczy
│   ├── progress.py         # Tracking postępu (PROGRESS.md, work_progress.md)
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstrakcyjna klasa worker
│   │   ├── cc.py           # Claude Code worker
│   │   ├── cch.py          # Claude Code paid worker
│   │   ├── ccg.py          # Claude Code Google worker
│   │   ├── gemini.py       # Google Gemini worker
│   │   ├── qwen.py         # Alibaba Qwen worker
│   │   └── codex.py        # OpenAI Codex worker
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstrakcyjna klasa manager
│   │   ├── anthropic.py    # Anthropic manager
│   │   ├── codex.py        # Codex manager
│   │   └── cc_bridge.py    # Claude Code manager bridge
│   └── utils/
│       ├── git.py          # Operacje na git (worktrees, commit, push)
│       ├── quota.py        # Probe i obsługa błędów kwotowych
│       └── lease.py        # System lease dla długotrwałych tasków
├── docs/                   # Dokumentacja
├── tests/                  # Testy
├── setup.py
└── README.md
```

## Przepływ danych

```
[Brief: ROADMAP.md, PROJECT.md]
         ↓
    [Planner]
         ↓
    [BACKLOG.md] (lista tasków w SQLite)
         ↓
   [Orchestrator] ←→ [SQLite DB]
         ↓
    [Manager AI] → generuje zadania
         ↓
    [Worker AI] → wykonuje w git worktree
         ↓
    [Review] → akceptuje/odrzuca
         ↓
    [Git: commit → push → merge/PR]
         ↓
    [PROGRESS.md, work_progress.md]
```

## Kluczowe komponenty

### 1. Orchestrator (`orchestrator.py`)

Główny engine wykonawczy. Odpowiada za:
- Pobieranie tasków z SQLite
- Uruchamianie workerów w izolowanych git worktrees
- Obsługę błędów kwotowych (429 → `waiting_for_quota`)
- Retry logic i fallback chain
- Aktualizację `PROGRESS.md` po każdym ticku

**Tryby pracy:**
- `--dry-run` — symulacja bez wykonania
- `--live` — autonomiczne wykonanie
- `--loop` — ciągła pętla aż do ukończenia

### 2. Manager AI (`managers/*.py`)

Generuje zadania z briefu projektu. Dostępne backendy:
- `cc` / `claude` — Claude Code (domyślny, brak API key)
- `anthropic` — Anthropic API
- `codex` — OpenAI Codex API

**Interfejs:**
```python
class ManagerBackend:
    def generate_tasks(self, brief: str) -> List[Task]:
        ...
    
    def review_result(self, task: Task, result: str) -> ReviewResult:
        ...
```

### 3. Worker AI (`workers/*.py`)

Wykonuje pojedyncze zadanie w izolowanym środowisku. Dostępni workerzy:
- `ccg` — Claude Code Google (domyślny)
- `cc` — Claude Code subscription (fallback)
- `cch` — Claude Code paid
- `gemini` — Google Gemini
- `qwen` — Alibaba Qwen
- `codex` — OpenAI Codex

**Fallback chain:**
```
ccg → cc → cch → gemini → qwen → codex
```

### 4. Progress Tracking (`progress.py`)

Aktualizuje pliki postępu:
- `.auto-coder/PROGRESS.md` — szczegółowy raport z błędami i statystykami
- `work_progress.md` — krótki status pushowany do `main` po każdym tasku

**Format `work_progress.md`:**
```markdown
# Work Progress

## Current Task
- ID: TASK-001
- Status: ✅ completed / 🔄 in_progress / ❌ failed
- Worker: ccg

## Summary
- Completed: 5/12
- Failed: 0
- Waiting for quota: 1
```

### 5. Git Automation (`utils/git.py`)

Operacje na git:
- Tworzenie izolowanych worktrees dla każdego taska
- Auto-commit po wykonaniu taska
- Auto-push do `main` (domyślnie włączone)
- Auto-merge lub auto-PR (konfigurowalne)

## Jak dodać nowego worker

1. Utwórz plik `auto_coder/workers/<nazwa>.py`:

```python
from .base import WorkerBackend

class NazwaWorker(WorkerBackend):
    def execute(self, task: Task) -> ExecutionResult:
        # Implementacja
        ...
```

2. Dodaj do `SUPPORTED_WORKERS` w `config.py`:

```python
SUPPORTED_WORKERS = {"cc", "cch", "ccg", "codex", "qwen", "gemini", "nazwa"}
```

3. Zarejestruj w `workers/__init__.py`:

```python
from .nazwa import NazwaWorker

__all__ = [..., "NazwaWorker"]
```

4. Udokumentuj w `docs/provider-routing.md`

## Jak dodać nowego manager

1. Utwórz plik `auto_coder/managers/<nazwa>.py`:

```python
from .base import ManagerBackend

class NazwaManager(ManagerBackend):
    def generate_tasks(self, brief: str) -> List[Task]:
        # Implementacja
        ...
    
    def review_result(self, task: Task, result: str) -> ReviewResult:
        # Implementacja
        ...
```

2. Dodaj do `DEFAULT_MANAGER_MODELS` w `config.py`:

```python
DEFAULT_MANAGER_MODELS = {
    "anthropic": "claude-opus-4-6",
    "cc": "claude-opus-4-6",
    "claude": "claude-opus-4-6",
    "nazwa": "model-name",
}
```

3. Zarejestruj w `managers/__init__.py`

## Błędy kwotowe (429)

System traktuje błędy 429 jako `waiting_for_quota`, nie jako failure:

```python
if error.status_code == 429:
    task.status = "waiting_for_quota"
    task.retry_after = now + timedelta(hours=quota_cooldown_hours)
    # Task nie jest zaliczany jako failed
```

## Testowanie

```bash
# Testy jednostkowe
pytest tests/

# Test integracyjny z dry-run
auto-coder run --dry-run

# Probe providerów
auto-coder doctor --probe-live
```
