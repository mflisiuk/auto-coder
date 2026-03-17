# Jak używać auto-coder

Ten dokument opisuje typowe przypadki użycia `auto-coder` — od inicjalizacji repozytorium po autonomiczne wykonywanie zadań.

## Wymagania wstępne

- Python 3.10+
- Git 2.30+
- Claude Code (`claude`) zainstalowane globalnie
- Dostęp do repozytorium z uprawnieniami do push

## Inicjalizacja repozytorium

```bash
# 1. Sklonuj auto-coder i zainstaluj
git clone https://github.com/mflisiuk/auto-coder
cd auto-coder
pip install -e .

# 2. Przejdź do swojego repozytorium
cd /path/to/your-repo

# 3. Zainicjalizuj auto-coder
auto-coder init
```

Komenda `init` tworzy:
- `.auto-coder/config.yaml` — konfiguracja projektu
- `.auto-coder/tasks/` — katalog na wygenerowane zadania
- `.auto-coder/reports/` — raporty z wykonania zadań

## Sprawdzenie konfiguracji

```bash
# Sprawdź czy auto-coder widzi Claude Code
auto-coder doctor --probe-live

# Sprawdź aktualną konfigurację
auto-coder config show
```

## Generowanie backlogu

```bash
# Wygeneruj zadania z ROADMAP.md i PROJECT.md
auto-coder plan

# Zobacz wygenerowane zadania
cat .auto-coder/tasks/backlog.json
```

## Uruchomienie wykonania

```bash
# Najpierw suchy przebieg — sprawdź co się wydarzy
auto-coder run --dry-run

# Uruchom autonomiczne wykonanie
auto-coder run --live
```

Podczas wykonania:
- `auto-coder` tworzy izolowane worktree dla każdego zadania
- Uruchamia AI workera (`ccg` domyślnie) w worktree
- Recenzuje zmiany i uruchamia testy baseline
- Commituje, pushuje i merge'uje do base branch
- Aktualizuje `PROGRESS.md` i `work_progress.md`

## Monitorowanie postępu

```bash
# Zobacz aktualny postęp
cat PROGRESS.md

# Zobacz szczegóły ostatniego zadania
cat .auto-coder/reports/latest/report.json
```

## Konfiguracja zadań — baseline_commands

Dla zadań tworzących pliki od zera użyj pustej listy baseline_commands:

```yaml
# W task-spec JSON
{
  "id": "create-new-module",
  "title": "Create new authentication module",
  "allowed_paths": ["src/auth/**"],
  "baseline_commands": [],  # Pomiń testy baseline — pliki nie istnieją
  "test_commands": ["pytest tests/auth/"]
}
```

Dla zadań modyfikujących istniejące pliki:

```yaml
{
  "id": "fix-auth-bug",
  "title": "Fix authentication bug",
  "allowed_paths": ["src/auth/**"],
  "baseline_commands": ["pytest tests/auth/"],  # Uruchom przed zmianą
  "test_commands": ["pytest tests/auth/"]       # Uruchom po zmianie
}
```

## Tryby uruchomienia

| Tryb | Komenda | Opis |
|------|---------|------|
| Dry-run | `auto-coder run --dry-run` | Symulacja — pokazuje co się wydarzy |
| Live | `auto-coder run --live` | Pełne autonomiczne wykonanie |
| Single task | `auto-coder run --task TASK_ID` | Wykonaj pojedyncze zadanie |
| Debug | `auto-coder run --live --debug` | Verbose logging |

## Cron deployment

Rekomendowany model deploymentu to cron co 20 minut:

```bash
# Dodaj do crontab
crontab -e

# Uruchamiaj auto-coder co 20 minut
*/20 * * * * cd /path/to/repo && auto-coder run --live >> /var/log/auto-coder.log 2>&1
```

## Rozwiązywanie problemów

```bash
# Sprawdź logi ostatniego zadania
cat .auto-coder/reports/latest/stderr.log

# Wymuś naprawę tasku
auto-coder repair TASK_ID

# Zresetuj stan runtime
rm .auto-coder/runtime.json
```

Więcej w [Typowe problemy](common-pitfalls.md).
