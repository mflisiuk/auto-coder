# auto-coder
> Autonomiczny manager kodowania, który bierze brief projektu, zamienia go w backlog i wykonuje pracę tickami bez ręcznego "approve".

## Co to robi
`auto-coder` to Pythonowy workflow engine dla zespołów chcących automatyzować dostarczanie feature'ów. Przyjmuje dokumentację produktu (`ROADMAP.md`, `PROJECT.md`), generuje zadania przez backend AI (`anthropic` lub `codex`), uruchamia pracę w izolowanym środowisku i recenzuje wyniki. Rozwiązuje problem ręcznego tłumaczenia wymagań na kod.

## Szybki start
```bash
git clone <twoje-repo-z-auto-coderem> && cd auto-coder
pip install -e .
auto-coder bootstrap-brief /path/to/your/repo   # opcjonalnie dla istniejącego repo
auto-coder init
export ANTHROPIC_API_KEY=...  # lub skonfiguruj codex
auto-coder doctor --probe-live
auto-coder plan
auto-coder run --dry-run
```

## Funkcjonalności
- Walidacja briefu wejściowego
- Generowanie backlogu przez `anthropic` lub `codex`
- Synchronizacja tasków do SQLite
- Quota-aware routing providerów
- Automatyczne wykrywanie dostępności providerów
- Worker CLI w osobnym git worktree
- Policy checks i retry loop
- `doctor --probe-live` dla realnego sprawdzenia managera
- `work_progress.md` aktualizowany przy domknięciu taska
- [Architektura v1](docs/architecture.md)

## Dokumentacja
- **[Common pitfalls & solutions](docs/common-pitfalls.md)** ⚠️ - Read this FIRST! Critical bugs that waste hours
- [Instalacja i konfiguracja](docs/setup.md)
- [Jak używać](docs/usage.md)
- [Architektura](docs/architecture.md)
- [Execution](docs/execution.md)
- [Brief validation](docs/brief-validation.md)
- [Cron](docs/cron.md)
- [Input pack](docs/inputs.md)
- [Operator runbook](docs/operator-runbook.md)
- [Go-live checklist](docs/go-live-checklist.md)
- [Pre-mortem](docs/pre-mortem.md)

## Changelog
[Zobacz CHANGELOG.md](CHANGELOG.md)
