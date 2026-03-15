# Architektura auto-coder v1

## Struktura plików

```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── manager.py          # Główny workflow engine
│   ├── backends/
│   │   ├── anthropic.py    # Anthropic backend
│   │   └── codex.py        # Codex backend
│   ├── workers/
│   │   ├── cc.py           # Worker adapter
│   │   ├── cch.py
│   │   ├── ccg.py
│   │   ├── codex.py
│   │   ├── qwen.py
│   │   └── gemini.py
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── synthesis.py    # Synteza planera
│   │   └── routing.py      # Quota-aware routing
│   ├── probes/
│   │   └── quota.py        # Sondy dostępności kwotów
│   └── storage/
│       └── sqlite.py       # SQLite persistence
├── docs/
├── tests/
├── setup.py
└── requirements.txt
```

## Jak działa kod

### 1. Manager (workflow engine)

```python
# auto_coder/manager.py
class Manager:
    def tick(self):
        # 1. Wybierz gotowy task
        # 2. Stwórz work order
        # 3. Uruchom workera
        # 4. Wymagaj AGENT_REPORT.json
        # 5. Odpal testy i policy checks
        # 6. Reviewuj wynik
        # 7. Retry lub zakończ
```

### 2. Backends

Backendy generują backlog z briefu:

- `anthropic` - używa API Anthropic
- `codex` - używa Node bridge do `codex exec`

### 3. Workers

Workery wykonują zadania jako CLI w osobnym git worktree.

### 4. Planner

Syntezuje plan zadań i routuje do dostępnych providerów.

### 5. Quota Probes

Sondy sprawdzają dostępność kwotów przed routowaniem.

## Jak rozbudować

### Dodanie nowego backendu

1. Stwórz `auto_coder/backends/twoj_backend.py`
2. Zaimplementuj interfejs `Backend`
3. Zarejestruj w `manager.py`

### Dodanie nowego workera

1. Stwórz `auto_coder/workers/twoj_worker.py`
2. Zaimplementuj interfejs `Worker`
3. Dodaj adapter CLI

### Dodanie nowej sondy

1. Stwórz `auto_coder/probes/twoj_probe.py`
2. Zaimplementuj `probe()` zwracające dostępność
3. Podłącz do routingu
