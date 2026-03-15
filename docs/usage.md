# Jak używać auto-coder

## Standardowy flow

### 1. Przygotuj brief

W repo projektu utrzymuj aktualne:

- `ROADMAP.md`
- `PROJECT.md`
- opcjonalnie `CONSTRAINTS.md`
- opcjonalnie `ARCHITECTURE_NOTES.md`

### 2. Wygeneruj backlog

```bash
auto-coder doctor
auto-coder plan
```

`plan`:

- waliduje brief
- odpala manager backend
- zapisuje `.auto-coder/tasks.generated.yaml`
- scala lokalne override'y z `.auto-coder/tasks.local.yaml`
- zapisuje wynik do `.auto-coder/tasks.yaml`
- synchronizuje taski do SQLite

### 3. Podejrzyj status

```bash
auto-coder status
```

Status pokazuje:

- task runtime w SQLite
- licznik prób
- provider usage
- quota state i `retry_after`

### 4. Wykonaj jeden tick

```bash
auto-coder run --dry-run
auto-coder run --live
```

`run` robi jeden pełny tick:

- recovery po przerwanych runach
- wybór taska przez scheduler
- utworzenie worktree
- uruchomienie workera
- policy checks
- testy
- review i zapis attemptu
- opcjonalny commit/push

## Praca codzienna

### Gdy zmieniasz brief

Po zmianie `ROADMAP.md` albo `PROJECT.md`:

```bash
auto-coder plan
auto-coder status
```

`auto-coder run` i tak spróbuje zrobić `refresh_if_changed()`, ale jawne `plan` jest lepsze do kontroli.

### Gdy chcesz odpalić tylko jeden task

```bash
auto-coder run --task task-id --dry-run
auto-coder run --task task-id --live
```

### Gdy migrujesz stary backlog

```bash
auto-coder migrate ./legacy-tasks.yaml
auto-coder plan
```

To importuje taski do `.auto-coder/tasks.local.yaml`.

## Jak czytać wyniki

### `completed`

Task przeszedł:

- allowed/protected path policy
- completion commands
- deterministic review
- manager review

### `waiting_for_retry`

Task jest naprawialny i wróci w kolejnym ticku z feedbackiem.

### `waiting_for_quota`

Provider wszedł w limit albo zwrócił `429`. Task nie jest traktowany jako zwykła porażka.

### `blocked`

Task nie robi postępu albo wymaga zmiany briefu, testów albo polityki projektu.

## Artefakty runtime

W `.auto-coder/` znajdziesz:

- `state.db` — source of truth
- `tasks.generated.yaml` — backlog z managera
- `tasks.local.yaml` — lokalne override'y
- `tasks.yaml` — efektywny backlog
- `reports/` — logi runów, testów, diffów i raportów workerów
- `worktrees/` — tymczasowe repo dla prób

## Tryb unattended

`auto-coder` nie ma własnego demona. Odpalasz go tickami:

- przez `cron`
- przez `systemd` timer
- przez zewnętrzny scheduler CI / VM

Przykłady są w `docs/cron.md`.
