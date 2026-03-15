# auto-coder
> Autonomiczny manager kodowania, który bierze brief projektu, zamienia go w backlog i wykonuje pracę tickami bez ręcznego "approve".

## Co działa

`auto-coder` ma Pythonowy core i działa jako mały workflow engine:

- waliduje brief wejściowy (`ROADMAP.md`, `PROJECT.md`)
- generuje backlog przez manager backend (`anthropic` albo `codex`)
- synchronizuje taski do SQLite
- na każdym ticku wybiera gotowy task i tworzy mały work order
- uruchamia workera CLI w osobnym git worktree
- wymaga `AGENT_REPORT.json`, odpala testy i policy checks
- reviewuje wynik, retryuje z feedbackiem albo kończy task
- opcjonalnie commituje i pushuje gotową pracę

## Szybki start

### 1. Zainstaluj pakiet

```bash
git clone <twoje-repo-z-auto-coderem>
cd auto-coder
pip install -e .
```

### 2. Przygotuj projekt docelowy

W repo projektu, który ma być rozwijany:

```bash
auto-coder init
```

To tworzy:

```text
.auto-coder/
  config.yaml
  state.db
  .gitignore
```

### 3. Dodaj brief projektu

W katalogu repo muszą istnieć co najmniej:

- `ROADMAP.md`
- `PROJECT.md`

Referencja poprawnego wsadu:

- [INPUT_SPEC.md](INPUT_SPEC.md)
- [example-project/README.md](example-project/README.md)

### 4. Skonfiguruj manager backend

Anthropic:

```bash
export ANTHROPIC_API_KEY=...
```

Codex:

- zainstalowany `codex`
- zainstalowany `node`
- aktywna autoryzacja CLI

W `.auto-coder/config.yaml`:

```yaml
manager_backend: codex
manager_model: ""   # pusty = backend-specific default
default_worker: codex
```

### 5. Sprawdź środowisko i wygeneruj plan

```bash
auto-coder doctor
auto-coder plan
auto-coder status
```

### 6. Uruchom tick

```bash
auto-coder run --dry-run
auto-coder run --live
```

`auto-coder run` wykonuje jeden tick. Do pracy ciągłej odpalasz go z crona lub systemd timera.

## Główne komendy

- `auto-coder init`
- `auto-coder doctor`
- `auto-coder plan`
- `auto-coder status`
- `auto-coder run`
- `auto-coder migrate`

## Dokumentacja

- [Architektura v1](ARCHITECTURE.md)
- [Spec wejścia](INPUT_SPEC.md)
- [Setup](docs/setup.md)
- [Usage](docs/usage.md)
- [Execution](docs/execution.md)
- [Brief validation](docs/brief-validation.md)
- [Cron](docs/cron.md)
- [Input pack](docs/inputs.md)

## Stan produktu

Aktualny v1 wspiera:

- manager backend `anthropic`
- manager backend `codex` przez Node bridge do `codex exec`
- workery `cc`, `cch`, `ccg`, `codex`, `qwen`, `gemini` jako adaptery CLI
- planner, quota-aware routing, recovery po crashu, retry loop i SQLite persistence

## Changelog

[Zobacz CHANGELOG.md](CHANGELOG.md)
