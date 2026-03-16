# Jak używać auto-coder

Ten dokument opisuje realny flow operatorski dla aktualnego CLI.

## Przypadek 1: Istniejące repo

```bash
cd /path/to/project
auto-coder bootstrap-brief
auto-coder init
auto-coder doctor --probe-live
auto-coder plan
auto-coder run --dry-run
```

Jeśli brief jest niejasny, `doctor` albo `plan` powinny go odrzucić zamiast zgadywać.

## Przypadek 2: Przejście na tryb live

```bash
auto-coder go-live --codex --cron '*/20 * * * *'
auto-coder status
auto-coder run --live
```

Alternatywnie możesz osobno użyć:

```bash
auto-coder install-cron '*/20 * * * *'
auto-coder install-systemd 20
```

## Przypadek 3: Operacje operatorskie

```bash
auto-coder runs
auto-coder inspect <task-id>
auto-coder retry <task-id>
auto-coder tail
auto-coder pin <task-id> --priority 5
auto-coder prefer-worker <task-id> codex
auto-coder disable-task <task-id>
```

## Komendy

| Komenda | Opis |
| --- | --- |
| `auto-coder bootstrap-brief` | Generuje pierwszy draft `ROADMAP.md`, `PROJECT.md`, `PLANNING_HINTS.md`, `CONSTRAINTS.md`, `ARCHITECTURE_NOTES.md` z istniejącego repo |
| `auto-coder init` | Tworzy `.auto-coder/config.yaml`, `.auto-coder/state.db` i `.auto-coder/.gitignore` |
| `auto-coder doctor --probe-live` | Sprawdza środowisko, brief i wykonuje minimalny live probe managera |
| `auto-coder plan` | Generuje `.auto-coder/tasks.generated.yaml` i `.auto-coder/tasks.yaml` |
| `auto-coder status` | Pokazuje status tasków i usage providerów |
| `auto-coder run --dry-run` | Wykonuje tick bez odpalania live workera |
| `auto-coder run --live` | Wykonuje jeden live tick |
| `auto-coder runs` | Pokazuje ostatnie ticki runtime |
| `auto-coder inspect <task-id>` | Pokazuje runtime taska, work ordery i próby |
| `auto-coder retry <task-id>` | Ręcznie przepina task z powrotem do retry |
| `auto-coder tail` | Tails log operatora albo ostatni log raportu |
| `auto-coder pin` | Promuje task przez override w `tasks.local.yaml` |
| `auto-coder prefer-worker` | Ustawia preferowanego workera dla taska |
| `auto-coder disable-task` | Wyłącza task przez `tasks.local.yaml` |
| `auto-coder go-live` | Ustawia live profile i opcjonalnie instaluje cron/systemd |
| `auto-coder install-cron` | Instaluje blok crona dla ticków |
| `auto-coder install-systemd` | Pisze user service i timer systemd |

## Repo-visible progress

Przy każdym domkniętym tasku, przed commitem/pushem, runtime generuje `work_progress.md` w branchu taska. Plik zawiera:

- `task id`
- tytuł taska
- krótki opis
- `done yes/no`
- czas domknięcia
- łączny czas od pierwszego startu taska do jego ukończenia
