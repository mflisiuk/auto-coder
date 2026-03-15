# auto-coder
> Autonomiczny manager kodowania, który bierze brief projektu, zamienia go w backlog i wykonuje pracę tickami bez ręcznego "approve".

## Co to robi
`auto-coder` to Pythonowy workflow engine dla zespołów chcących automatyzować dostarczanie feature'ów. Przyjmuje dokumentację produktu (`ROADMAP.md`, `PROJECT.md`), generuje zadania przez backend AI (`anthropic` lub `codex`), uruchamia pracę w izolowanym środowisku i recenzuje wyniki. Rozwiązuje problem ręcznego tłumaczenia wymagań na kod.

## Szybki start
```bash
git clone <twoje-repo-z-auto-coderem> && cd auto-coder
pip install -e .
auto-coder init
export ANTHROPIC_API_KEY=...  # lub skonfiguruj codex
auto-coder run --live
```

## Funkcjonalności
- Walidacja briefu wejściowego
- Generowanie backlogu przez `anthropic` lub `codex`
- Synchronizacja tasków do SQLite
- Quota-aware routing providerów
- Automatyczne wykrywanie dostępności providerów
- Worker CLI w osobnym git worktree
- Policy checks i retry loop
- [Architektura v1](docs/architecture.md)

## Dokumentacja
- [Instalacja i konfiguracja](docs/setup.md)
- [Jak używać](docs/usage.md)
- [Architektura](docs/architecture.md)
- [Execution](docs/execution.md)
- [Brief validation](docs/brief-validation.md)
- [Cron](docs/cron.md)
- [Input pack](docs/inputs.md)

## Changelog
[Zobacz CHANGELOG.md](CHANGELOG.md)
