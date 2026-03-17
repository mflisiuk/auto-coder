# Architektura

## Struktura projektu

```
auto-coder/
├── auto_coder/
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Konfiguracja i loading
│   ├── orchestrator.py     # Główny orchestrator
│   ├── operator.py         # Komendy operatora
│   ├── brief_validator.py  # Walidacja briefu
│   ├── bootstrap_brief.py  # Bootstrap brief generator
│   ├── managers/
│   │   ├── anthropic.py    # Anthropic manager backend
│   │   ├── codex_bridge.py # Codex manager backend
│   │   └── cc_bridge.py    # CC-Manager bridge
│   ├── workers/
│   │   ├── ccg_worker.py   # CCG worker
│   │   ├── cc_worker.py    # CC worker
│   │   └── ...             # Inni workerzy
│   ├── storage.py          # SQLite storage layer
│   └── execution.py        # Execution core
├── docs/                   # Dokumentacja
├── tests/                  # Testy
├── setup.py                # Package setup
└── README.md
```

## Komponenty

### CLI (`cli.py`)

Główny entry point dla komend:
- `init` — inicjalizacja repozytorium
- `plan` — generowanie backlogu
- `run` — uruchomienie orchestratora
- `status` — status zadań
- `doctor` — health check

### Managerowie

Managerowie generują zadania z briefu projektu:

| Backend | Opis | Wymaga API Key |
|---------|------|----------------|
| `cc` / `claude` | Claude Code subscription | Nie |
| `anthropic` | Anthropic API | Tak |
| `codex` | Codex API | Tak |

### Workerzy

Workerzy wykonują zadania w izolowanych git worktrees:

| Worker | Opis | Fallback |
|--------|------|----------|
| `ccg` | Claude Code Google subscription | → `cc` |
| `cc` | Claude Code subscription | → `cch` |
| `cch` | Claude Code paid | → `gemini` |
| `gemini` | Gemini API | → `qwen` |
| `qwen` | Qwen API | → `codex` |
| `codex` | Codex API | — |

### Orchestrator

Główna pętla wykonawcza:
1. Pobiera następne zadanie z backlogu
2. Tworzy izolowany git worktree
3. Uruchamia worker z task contract
4. Recenzuje wynik
5. Commituje i pushuje
6. Aktualizuje `PROGRESS.md` i `work_progress.md`

### Storage

SQLite database dla stanu wykonania:
- Tasks — backlog zadań
- Work orders — przypisania workerów
- Attempts — próby wykonania
- Runtime — metryki wykonania

## Przepływ danych

```
Brief (ROADMAP.md, PROJECT.md)
    ↓
Manager (cc/anthropic/codex)
    ↓
Tasks (tasks.yaml)
    ↓
Orchestrator
    ↓
Worker (ccg/cc/cch/...)
    ↓
Git Worktree → Code Changes
    ↓
Review → Commit → Push → PR
```

## Rozbudowa

### Dodanie nowego managera

1. Utwórz `auto_coder/managers/<name>_bridge.py`
2. Zaimplementuj `probe_live(config)` i `run(config, tasks)`
3. Dodaj obsługę w `cli.py:_probe_manager_backend()`
4. Zaktualizuj `DEFAULT_MANAGER_MODELS` w `config.py`

### Dodanie nowego workera

1. Utwórz `auto_coder/workers/<name>_worker.py`
2. Zaimplementuj `run_task(config, task)`
3. Dodaj do `FALLBACK_CHAIN` w `config.py`
4. Zaktualizuj dokumentację

## Zobacz też

- [CC-Manager Bridge](cc-manager-bridge-spec.md)
- [Provider routing](provider-routing.md)
- [Execution](execution.md)
