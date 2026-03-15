# Architektura auto-coder

Szczegółowa architektura v1 jest opisana w [../ARCHITECTURE.md](../ARCHITECTURE.md).

Ten dokument to krótki operacyjny skrót.

## Model działania

`auto-coder` działa tickami:

1. scheduler budzi się przez `auto-coder run`
2. recovery czyści stare lease'y i przerwane runy
3. planner odświeża backlog, jeśli zmienił się brief
4. scheduler wybiera jeden gotowy task
5. manager backend tworzy work order
6. worker CLI wykonuje pracę w osobnym worktree
7. reviewer odpala deterministic gates i review managera
8. task przechodzi do `completed`, `waiting_for_retry`, `waiting_for_quota` albo `blocked`

## Najważniejsze moduły

- `config.py`
  Ładowanie `.auto-coder/config.yaml` i backend-specific defaults.

- `brief_validator.py`
  Odrzuca niejasny brief zanim planner zacznie generować backlog.

- `planner.py`
  Generuje `tasks.generated.yaml`, scala `tasks.local.yaml`, waliduje DAG i syncuje taski do SQLite.

- `storage.py`
  Source of truth w SQLite: taski, work orders, attempts, run ticks, leases, manager threads.

- `scheduler.py`
  Wybór taska do uruchomienia z uwzględnieniem zależności, retry i cooldownów.

- `orchestrator.py`
  Jeden tick end-to-end.

- `reviewer.py`
  Deterministic review + handoff do manager backendu.

- `managers/`
  Obsługiwane backendy managera:
  - `anthropic`
  - `codex` przez bridge Node -> `codex exec`

- `workers/`
  Adaptery CLI dla agentów kodujących.

- `quota/` i `router.py`
  Probe'y usage, fallback providerów i `waiting_for_quota`.

## Source of truth

Metadane runtime idą do SQLite:

- task runtime
- attempts
- run ticks
- leases
- manager thread state
- work orders

Duże artefakty trafiają do `.auto-coder/reports/`.

## Stany taska

- `queued`
- `ready`
- `leased`
- `running`
- `waiting_for_retry`
- `waiting_for_quota`
- `blocked`
- `completed`

## Zasady bezpieczeństwa

- worktree per attempt
- allowed/protected path policy
- obowiązkowe `completion_commands`
- obowiązkowy `AGENT_REPORT.json`
- `quota_exhausted` nie jest zwykłym failure
- auto-merge jest wyłączony domyślnie
