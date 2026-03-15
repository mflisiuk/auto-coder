# Execution Core

## Co robi jeden tick

`auto-coder run` uruchamia dokładnie jeden tick workflow.

Przepływ:

1. recovery przerywanych runów i wygasłych lease'ów
2. wybór taska przez scheduler
3. utworzenie albo wznowienie work ordera
4. wybór workera przez router
5. utworzenie git worktree
6. odpalenie `baseline_commands`
7. uruchomienie workera CLI
8. odczyt `AGENT_REPORT.json`
9. policy checks na changed files
10. odpalenie `completion_commands`
11. deterministic review
12. manager review
13. commit / push jeśli włączone
14. zapis attemptu, run ticku i artefaktów

## Obowiązkowy raport workera

Worker ma zostawić `AGENT_REPORT.json` w katalogu raportu próby.

Minimalny kontrakt:

```json
{
  "status": "completed | partial | blocked | quota_exhausted",
  "summary": "Short summary of what was done",
  "completed_items": ["..."],
  "remaining_items": ["..."],
  "blockers": ["..."],
  "tests_run": ["..."],
  "files_touched": ["..."],
  "next_recommended_step": "..."
}
```

Brak raportu nie kończy taska sukcesem. Próba trafia do retry/block flow.

## Deterministic gates

Przed manager review system sprawdza:

- changed files mieszczą się w `allowed_paths`
- nic nie dotknęło `protected_paths`
- `completion_commands` przeszły
- diff istnieje i nie jest pustą próbą

To jest twarda bramka. LLM review nie zastępuje testów ani policy.

## Retry i quota

Retryable statusy obejmują m.in.:

- `agent_failed`
- `agent_report_missing`
- `no_changes`
- `policy_failed`
- `tests_failed`
- `review_failed`
- `quota_exhausted`

`quota_exhausted` trafia do osobnego stanu taska:

- `waiting_for_quota`

To pozwala schedulerowi wrócić do taska po cooldownie zamiast traktować go jak zwykły fail.

## Worktree i artefakty

Każda próba działa w osobnym worktree pod:

```text
.auto-coder/worktrees/
```

Artefakty trafiają do:

```text
.auto-coder/reports/<run-id>/
```

Typowe pliki:

- stdout/stderr workera
- stdout/stderr testów
- `AGENT_REPORT.json`
- `baseline.json`
- `completion.json`
- diff i metadata próby
