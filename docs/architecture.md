# Architektura auto-coder

## Przegląd systemu

```
┌─────────────────────────────────────────────────────────────┐
│                     Human Inputs                            │
│  ROADMAP.md │ PROJECT.md │ CONSTRAINTS.md │ ARCHITECTURE   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Manager (Core)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Planner    │  │  Scheduler  │  │  Reviewer           │ │
│  │  (tasks)    │  │  (tick)     │  │  (artifacts)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                            │                                │
│  ┌─────────────┐  ┌────────▼────────┐  ┌─────────────────┐ │
│  │  State      │  │  Orchestrator   │  │  Quota Manager  │ │
│  │  (persist)  │  │  (work orders)  │  │  (limits)       │ │
│  └─────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Manager    │ │   Manager    │ │   Manager    │
    │   Backend    │ │   Backend    │ │   Backend    │
    │   (Jira)     │ │   (GitHub)   │ │   (Linear)   │
    └──────────────┘ └──────────────┘ └──────────────┘
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Worker     │ │   Worker     │ │   Worker     │
    │   (Claude)   │ │   (GPT-4)    │ │   (Local)    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

## Cykl życia zadania

```
PENDING → PLANNED → QUEUED → IN_PROGRESS → REVIEW
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
           COMPLETE               RETRY                   BLOCKED
        (commit + push)    (feedback loop)          (manual review)
```

## Moduły systemu

### 1. Planner
- Parsuje ROADMAP.md i PROJECT.md
- Generuje zadania z kryteriami akceptacji
- Waliduje brief (odrzucanie niejasnych wymagań)
- Output: lista zadań z priorytetami

### 2. Scheduler
- Zarządza tickami (co N minut)
- Sprawdza aktywne lease'y
- Monitoruje kwoty workerów
- Decyduje o kolejności zadań

### 3. Orchestrator
- Tworzy work orders (jednostki wykonania)
- Wybiera backend managera
- Wybiera workera (quota + dostępność)
- Uruchamia pracę w git worktree

### 4. Worker Adapter
- Abstrakcja nad różnymi providerami (Claude, GPT, lokalne)
- Normalizuje input/output
- Monitoruje zużycie tokenów
- Obsługuje timeouty i błędy

### 5. Reviewer
- Analizuje artefakty po wykonaniu
- Sprawdza czy kod przechodzi testy
- Weryfikuje zgodność z PROJECT.md
- Decyduje: accept / retry / block

### 6. State Manager
- Persistencja stanu między restartami
- Trackowanie historii zadań
- Lease'y i locki
- Queue zadań oczekujących

## Struktura plików

```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── manager.py          # Główna pętla managera
│   ├── orchestrator.py     # Koordynacja pracy
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── brief_validator.py
│   │   └── task_generator.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── work_order.py
│   │   ├── worker_adapter.py
│   │   └── sprint_loop.py
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── jira_manager.py
│   │   └── github_manager.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── claude_worker.py
│   │   └── gpt_worker.py
│   ├── state/
│   │   ├── __init__.py
│   │   ├── persistence.py
│   │   └── models.py
│   └── cli.py              # CLI dla operacji manualnych
├── docs/
├── ROADMAP.md
├── PROJECT.md
├── CONSTRAINTS.md
├── ARCHITECTURE.md
├── requirements.txt
├── .env.example
└── pyproject.toml
```

## Rozszerzanie systemu

### Dodanie nowego manager backendu
1. Utwórz `auto_coder/backends/new_manager.py`
2. Zaimplementuj interfejs `ManagerBackend`:
   ```python
   class NewManagerBackend(ManagerBackend):
       def get_tasks(self) -> List[Task]
       def update_status(self, task_id: str, status: str)
       def add_comment(self, task_id: str, comment: str)
   ```
3. Dodaj konfigurację w `.env.example`
4. Zarejestruj w `auto_coder/backends/__init__.py`

### Dodanie nowego workera
1. Utwórz `auto_coder/workers/new_worker.py`
2. Zaimplementuj interfejs `WorkerAdapter`:
   ```python
   class NewWorkerAdapter(WorkerAdapter):
       def execute(self, work_order: WorkOrder) -> ExecutionResult
       def get_quota(self) -> QuotaInfo
       def estimate_tokens(self, prompt: str) -> int
   ```
3. Dodaj konfigurację w `.env.example`
4. Zarejestruj w `auto_coder/workers/__init__.py`

### Dodanie nowego typu zadania
1. Zdefiniuj schemat w `auto_coder/state/models.py`
2. Dodaj walidację w `auto_coder/planner/brief_validator.py`
3. Zaimplementuj handler w `auto_coder/execution/`

## Zasady działania

### 1. Deterministyczne gate'y
Przed każdym wywołaniem LLM wykonaj walidację deterministyczną:
- Czy ścieżki są chronione?
- Czy kwota wystarczy?
- Czy brief jest kompletny?

### 2. Persistencja stanu
Stan musi przetrwać restart:
- Używaj SQLite lub plików JSON
- Zapisuj po każdej zmianie stanu
- Obsługuj corrupted state

### 3. Retry z granicą
- Max 3 próby na zadanie
- Backoff wykładniczy (300s, 600s, 1200s)
- Po przekroczeniu → BLOCKED

### 4. Izolacja
- Każde zadanie w osobnym git worktree
- Clean state przed rozpoczęciem
- Cleanup po zakończeniu (success lub failure)

### 5. Quota jako first-class state
- `QUOTA_EXHAUSTED` ≠ `FAILED`
- Wstrzymaj zadanie, nie odrzucaj
- Wznów po resecie kwoty
