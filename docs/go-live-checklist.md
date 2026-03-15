# Go-Live Checklist

Przejdź ten checklist przed włączeniem ciągłego `run --live`.

## Repo

- repo ma co najmniej jeden commit
- `auto-coder doctor` przechodzi na zielono
- `ROADMAP.md` i `PROJECT.md` przechodzą walidację
- `completion_commands` są deterministyczne
- `Editable Paths` i `Protected Paths` są wpisane

## Runtime

- `dry_run` był już przetestowany
- `run --dry-run` zapisał raport i status
- `state.db` istnieje i aktualizuje się
- `reports/` i `worktrees/` są tworzone poprawnie

## Manager

- backend managera jest wybrany świadomie
- dla Anthropic jest `ANTHROPIC_API_KEY`
- dla Codexa działa `codex` i `node`

## Workers

- default worker działa z terminala
- fallback worker działa z terminala
- provider thresholds są ustawione sensownie

## Bezpieczeństwo

- `auto_merge: false`
- `auto_push` jest włączane tylko świadomie
- sekrety są poza zakresem edycji
- repo działa na kontrolowanej maszynie

## Operacje

- cron jest ustawiony
- log output idzie do pliku
- ktoś sprawdza `status` i logi przynajmniej raz dziennie
