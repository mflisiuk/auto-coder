# Architektura auto-coder

Dokument dla deweloperów chcących zrozumieć lub rozbudować auto-coder.

## Struktura plików

```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── cli.py              # Główny interfejs CLI
│   ├── bootstrap_brief.py  # Generowanie briefu z istniejących docs
│   ├── planner/            # Moduł planowania
│   ├── executor/           # Moduł wykonawczy
│   ├── providers/          # Integracje z AI providerami
│   └── db/                 # Warstwa danych (SQLite)
├── docs/                   # Dokumentacja
├── tests/                  # Testy
├── setup.py
└── README.md
```

## Komponenty

### CLI (`cli.py`)

Główne komendy:
- `init` - inicjalizacja projektu
- `bootstrap-brief` - generowanie briefu z istniejących dokumentów
- `doctor` - diagnostyka środowiska
- `plan` - generowanie backlogu
- `run` - uruchomienie pętli wykonawczej

### Bootstrap Brief (`bootstrap_brief.py`)

Moduł skanujący istniejące repozytorium i generujący pliki briefu:
- Analizuje `README.md`, `docs/*.md`
- Ekstrahuje tytuły i sekcje
- Generuje szablony `ROADMAP.md`, `PROJECT.md`, `PLANNING_HINTS.md`

### Planner

Syntezuje zadania z dokumentów wejściowych:
- Parsuje `ROADMAP.md` i `PROJECT.md`
- Używa AI do generowania tasków
- Routuje do odpowiedniego providera (quota-aware)

### Executor

Pętla wykonawcza:
- Pobiera taski z backlogu
- Uruchamia w izolowanym worktree
- Wykonuje policy checks
- Commituje zmiany
- Aktualizuje `work_progress.md`

### Providers

Warstwa abstrakcji dla backendów AI:
- Anthropic provider
- Codex provider
- Quota probes - sprawdzanie dostępności

### Database (SQLite)

Przechowuje:
- Backlog tasków
- Historię wykonań
- Statusy i metadane

## Przepływ danych

```
[Brief Docs] → [Planner] → [Backlog DB] → [Executor] → [Git Commits]
                    ↓           ↓              ↓
               [Providers]  [SQLite]    [work_progress.md]
```

## Jak rozbudować

### Dodanie nowego providera

1. Stwórz `auto_coder/providers/new_provider.py`
2. Zaimplementuj interfejs provider (quota check, generate)
3. Zarejestruj w routerze

### Dodanie nowej komendy CLI

1. Dodaj funkcję w `auto_coder/cli.py`
2. Zarejestruj w parserze argumentów
3. Udokumentuj w `docs/usage.md`

### Rozszerzenie walidacji briefu

1. Edytuj `auto_coder/validator.py`
2. Dodaj nowe reguły walidacji
3. Zaktualizuj `docs/brief-validation.md`

## Testowanie

```bash
# Uruchom testy
pytest tests/

# Tryb debugowania
export AUTO_CODER_DEBUG=1
auto-coder run --dry-run
```

## Zasady bezpieczeństwa

- Izolacja przez git worktree
- Policy checks przed commit
- Quota limits na providerów
- Walidacja wejścia przed wykonaniem

Więcej: [Operator runbook](docs/operator-runbook.md), [Pre-mortem](docs/pre-mortem.md)
