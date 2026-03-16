# Operator Runbook

Ten dokument jest dla Ciebie jako operatora systemu. To nie jest opis architektury, tylko dokładna instrukcja uruchomienia i pracy krok po kroku.

## 1. Co musi być gotowe

### Maszyna

- Linux albo macOS
- Python `>=3.11`
- Git `>=2.23`
- Node `>=18`, jeśli używasz managera `codex`
- zainstalowane CLI workerów, których chcesz używać, np. `cc`, `cch`, `ccg`, `codex`

### Repo projektu

Repo, które ma rozwijać `auto-coder`, musi:

- być repo Git
- mieć co najmniej jeden commit
- mieć działające komendy testowe
- mieć jasny brief wejściowy

## 2. Zainstaluj auto-coder

W repo `auto-coder`:

```bash
git clone <repo-z-auto-coderem>
cd auto-coder
pip install -e .
```

Sprawdź, że entrypoint działa:

```bash
auto-coder --help
```

## 3. Przygotuj repo docelowe

W repo, które ma być rozwijane:

```bash
git init -b main                # jeśli repo jeszcze nie istnieje
git add .
git commit -m "initial commit"  # jeśli nie ma jeszcze HEAD
auto-coder bootstrap-brief      # jeśli repo już ma README/docs i chcesz wygenerować pierwszy draft briefu
auto-coder init
```

To stworzy:

```text
.auto-coder/
  config.yaml
  state.db
  .gitignore
```

## 4. Przygotuj brief wejściowy

W katalogu repo muszą istnieć:

- `ROADMAP.md`
- `PROJECT.md`
- `PLANNING_HINTS.md` jeśli repo ma własne konwencje, które planner ma respektować

Silnie zalecane:

- `CONSTRAINTS.md`
- `ARCHITECTURE_NOTES.md`

Użyj jako wzorca:

- `INPUT_SPEC.md`
- `example-project/`

## 5. Wybierz manager backend

### Opcja A: Anthropic

```bash
export ANTHROPIC_API_KEY=...
```

`.auto-coder/config.yaml`:

```yaml
manager_backend: anthropic
manager_model: ""
default_worker: cc
fallback_worker: cch
```

### Opcja B: Codex

Wymagania:

- `codex` działa z terminala
- `node` jest dostępny
- masz aktywną autoryzację CLI

`.auto-coder/config.yaml`:

```yaml
manager_backend: codex
manager_model: ""
codex_reasoning_effort: medium
default_worker: codex
fallback_worker: cch
```

## 6. Ustaw bezpieczny profil startowy

Na start ustaw tak:

```yaml
enabled: true
dry_run: true
auto_commit: false
auto_push: false
auto_merge: false
review_required: true
fetch_before_run: true
max_tasks_per_run: 1
max_attempts_per_task_per_run: 3
failure_block_threshold: 3
agent_timeout_minutes: 45
test_timeout_minutes: 20
quota_cooldown_hours: 4
cleanup_worktree_on_success: true
cleanup_worktree_on_failure: false
cleanup_worktree_older_than_days: 7
```

To jest profil "preview / hardening", nie "production live".

## 7. Wypełnij path policy i provider policy

W `PROJECT.md` musisz mieć:

- `Editable Paths`
- `Protected Paths`
- `Commands`

W `.auto-coder/config.yaml` możesz dodatkowo ustawić globalne fallbacki providerów:

```yaml
providers:
  ccg:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: cch
  cc:
    token_limit_daily: 500000
    quota_threshold: 0.90
    fallback: cch
  cch:
    token_limit_daily: null
    quota_threshold: 1.00
    fallback: null
```

## 8. Zrób pierwszy preflight

W repo docelowym:

```bash
auto-coder doctor --probe-live
```

`doctor` musi przejść na zielono dla:

- `git available`
- `state.db present`
- `worktree base ref (...)`
- manager backend
- worker CLI
- brief validation
- manager live probe

Jeśli `doctor` nie przechodzi, nie uruchamiaj `run`.

## 9. Wygeneruj backlog

```bash
auto-coder plan
auto-coder status
```

Sprawdź:

- czy taski mają sens
- czy kolejność jest sensowna
- czy `allowed_paths` są właściwe
- czy `completion_commands` są wykonalne

Jeśli chcesz nadpisać lub doprecyzować konkretne taski, edytuj:

```text
.auto-coder/tasks.local.yaml
```

Albo użyj CLI:

```bash
auto-coder pin <task-id> --priority 5
auto-coder prefer-worker <task-id> codex
auto-coder disable-task <task-id>
```

Potem uruchom:

```bash
auto-coder plan
```

## 10. Pierwsze uruchomienie dry-run

```bash
auto-coder run --dry-run
auto-coder status
```

Sprawdź:

- czy task dostał status `dry_run`
- czy powstał wpis w `.auto-coder/reports/`
- czy nie ma niespodziewanego `runner_failed`

## 11. Wejście w tryb live

Dopiero po poprawnym `doctor`, `plan` i `run --dry-run`:

```yaml
dry_run: false
auto_commit: true
auto_push: true
auto_merge: false
```

Nie włączaj `auto_merge` na start.

Szybsza ścieżka operatorska:

```bash
auto-coder go-live --codex --cron '*/20 * * * *'
```

## 12. Tick manualny live

```bash
auto-coder run --live
auto-coder status
```

Po zamknięciu taska branch dostanie też `work_progress.md`, żeby wynik pracy był widoczny bez wchodzenia do CLI i bez czytania SQLite.

Jeśli pierwszy live tick przejdzie sensownie:

- task poszedł w `completed`
- albo w `waiting_for_retry`
- albo w `waiting_for_quota`

to możesz przejść do crona.

## 13. Cron

Bezpieczny start:

```cron
*/15 * * * * cd /path/to/repo && /usr/bin/env auto-coder run --live >> .auto-coder/cron.log 2>&1
```

Dodatkowo raz dziennie:

```cron
5 0 * * * cd /path/to/repo && /usr/bin/env auto-coder doctor >> .auto-coder/doctor.log 2>&1
```

## 14. Co monitorować

Regularnie sprawdzaj:

```bash
auto-coder status
tail -n 200 .auto-coder/cron.log
find .auto-coder/reports -maxdepth 2 -type d | tail
```

Sygnały ostrzegawcze:

- dużo tasków w `waiting_for_retry`
- dużo tasków w `waiting_for_quota`
- częste `runner_failed`
- brak nowych attemptów mimo ticków
- rosnące `.auto-coder/worktrees/` albo `.auto-coder/reports/`

## 15. Co robić przy awarii

### `brief niejasny`

- popraw `ROADMAP.md` albo `PROJECT.md`
- uruchom `auto-coder plan`

### `runner_failed`

- uruchom `auto-coder doctor`
- sprawdź `worktree base ref`
- sprawdź czy repo ma commit i branch bazowy

### `waiting_for_quota`

- poczekaj do resetu limitu
- ustaw inny fallback worker
- zmniejsz wielkość tasków

### `blocked`

- sprawdź ostatni report w `.auto-coder/reports/`
- doprecyzuj brief
- popraw testy albo policy

## 16. Profil produkcyjny, który polecam

Jeśli chcesz bezpiecznie dojść do "autonomicznego developmentu 24/7", rób to w 3 etapach:

### Etap 1: Preview

- `dry_run: true`
- `auto_commit: false`
- `auto_push: false`

### Etap 2: Controlled live

- `dry_run: false`
- `auto_commit: true`
- `auto_push: true`
- `auto_merge: false`
- jedna maszyna
- jeden worker domyślny

### Etap 3: Unattended live

- cron co `10-15` minut
- fallback workers włączone
- codzienny `doctor`
- osobna gałąź integracyjna albo osobne repo testowe przed `main`
