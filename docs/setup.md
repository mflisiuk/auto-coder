# Instalacja i konfiguracja

## Wymagania

- Python `>=3.11`
- Git `>=2.23`
- jeden manager backend:
  - Anthropic SDK z `ANTHROPIC_API_KEY`, albo
  - `codex` CLI + `node`
- co najmniej jeden worker CLI, którego chcesz używać, np. `cc`, `cch`, `ccg`, `codex`

## Instalacja pakietu

```bash
git clone <repo-z-auto-coderem>
cd auto-coder
pip install -e .
```

## Inicjalizacja repo projektu

W repo, które ma być rozwijane przez auto-coder:

```bash
auto-coder init
```

To tworzy `.auto-coder/config.yaml` i `.auto-coder/state.db`.

Repo powinno mieć już co najmniej jeden commit. Worktree execution nie ruszy na pustym repo bez `HEAD`.

## Minimalny wsad wejściowy

W katalogu repo muszą istnieć:

- `ROADMAP.md`
- `PROJECT.md`

Opcjonalnie:

- `CONSTRAINTS.md`
- `ARCHITECTURE_NOTES.md`

Dokładny kontrakt wejścia:

- `INPUT_SPEC.md`
- `docs/inputs.md`
- `example-project/`

## Konfiguracja managera

### Anthropic

```bash
export ANTHROPIC_API_KEY=...
```

`config.yaml`:

```yaml
manager_backend: anthropic
manager_model: ""
default_worker: cc
fallback_worker: cch
```

### Codex

Wymagania:

- zainstalowany `codex`
- zainstalowany `node`
- działające logowanie w Codex CLI

`config.yaml`:

```yaml
manager_backend: codex
manager_model: ""
codex_reasoning_effort: medium
default_worker: codex
fallback_worker: cch
```

Pusty `manager_model` oznacza backend-specific default:

- `anthropic` -> `claude-opus-4-6`
- `codex` -> `gpt-5`

## Typowa konfiguracja Git automation

Bezpieczny start:

```yaml
dry_run: true
auto_commit: false
auto_push: false
auto_merge: false
```

Później możesz przełączyć na:

```yaml
dry_run: false
auto_commit: true
auto_push: true
auto_merge: false
```

## Weryfikacja środowiska

```bash
auto-coder doctor
```

Doctor sprawdza:

- dostępność `git`
- obecność `state.db`
- dostępność manager backendu
- dostępność znanych workerów
- brief validation dla `ROADMAP.md` i `PROJECT.md`
- quota probes, jeśli są skonfigurowane

## Pierwsze uruchomienie

```bash
auto-coder plan
auto-coder status
auto-coder run --dry-run
```

Jeśli preview wygląda dobrze:

```bash
auto-coder run --live
```

## Najczęstsze problemy

### `FAIL: manager backend unavailable`

- dla Anthropic ustaw `ANTHROPIC_API_KEY`
- dla Codexa zainstaluj `codex` i `node`
- sprawdź `manager_backend` w `.auto-coder/config.yaml`

### `FAIL: brief niejasny`

- uzupełnij brakujące sekcje wskazane przez walidator
- dodaj konkretne komendy testowe i policy ścieżek do `PROJECT.md`

### `quota_exhausted`

- poczekaj do `retry_after`
- zmień fallback worker w `providers`
- skróć work ordery albo obniż częstotliwość ticków
