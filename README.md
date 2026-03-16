# auto-coder

> Autonomiczny manager kodowania: otrzymuje brief projektu, generuje zadania, uruchamia AI workerów w izolowanych git worktrees, recenzuje wyniki, commituje, pushuje i otwiera PR-y — bez ręcznej interwencji.

## Co to robi

`auto-coder` to Pythonowy workflow engine dla zespołów chcących automatyzować dostarczanie feature'ów. Czyta dokumentację produktu (`ROADMAP.md`, `PROJECT.md`), generuje backlog przez AI managera (`anthropic` lub `codex`), uruchamia workerów w izolowanych środowiskach, recenzuje wyniki i merge'uje do main.

**Kluczowe właściwości:**
- Jedna instalacja działa dla dowolnej liczby repozytoriów
- Błędy kwotowe (429) nie są zaliczane jako failure — system czeka na reset kwoty
- `PROGRESS.md` jest aktualizowany po każdym ticku — zawsze widoczny na GitHub
- Cron co 20 min to rekomendowany model deploymentu (bez persistent daemon)

## Szybki start

```bash
# 1. Instalacja globalna (działa dla wszystkich repozytoriów)
git clone https://github.com/mflisiuk/auto-coder && cd auto-coder
pip install -e .

# 2. W swoim repozytorium — wygeneruj brief (opcjonalnie)
auto-coder bootstrap-brief /path/to/your-repo

# 3. Zainicjalizuj auto-coder w repozytorium
cd /path/to/your-repo
auto-coder init

# 4. Ustaw klucz API
export ANTHROPIC_API_KEY=sk-ant-...   # lub skonfiguruj codex

# 5. Sprawdź czy wszystko działa
auto-coder doctor --probe-live

# 6. Wygeneruj backlog zadań z briefu
auto-coder plan

# 7. Najpierw dry-run — bez zmian w kodzie
auto-coder run --dry-run

# 8. Tryb live
auto-coder run --live
```

## Konfiguracja

Po `auto-coder init` edytuj `.auto-coder/config.yaml`:

```yaml
dry_run: false          # false = rzeczywiste uruchomienie agentów
auto_commit: true       # commituj wyniki workerów
auto_push: true         # pushuj branch do origin
auto_pr: true           # otwórz PR przez gh CLI
auto_merge: true        # auto-merge PR po utworzeniu

default_worker: cc      # cc = Claude Code (free), cch = Claude Code (paid)
fallback_worker: cch    # fallback gdy wyczerpano kwotę default_worker

max_tasks_per_run: 1    # zadania na jeden tick crona
max_attempts_per_task_per_run: 3
failure_block_threshold: 3  # consecutive failures before task is blocked

quota_cooldown_hours: 4     # czas oczekiwania po 429 przed retry
```

## PROGRESS.md

Po każdym wykonaniu zadania auto-coder zapisuje `PROGRESS.md` w rootcie projektu z:
- Podsumowaniem (Razem / Ukończone / W toku / Oczekujące / Błędy)
- Statusem per task z emoji (✅ ⚙️ ⏳ 🔁 🚫 ❌)
- Nazwą workera, liczbą prób, czasem trwania
- Szczegółową sekcją błędów dla tasków zablokowanych

## Dokumentacja

- **[common-pitfalls.md](docs/common-pitfalls.md)** — typowe problemy i rozwiązania
- **[setup.md](docs/setup.md)** — instalacja i konfiguracja krok po kroku
- **[usage.md](docs/usage.md)** — pełny opis komend i workflow
- **[operator-runbook.md](docs/operator-runbook.md)** — przewodnik dla operatora
- **[provider-routing.md](docs/provider-routing.md)** — routing providerów AI

## Wymagania

- Python 3.8+
- Git
- Opcjonalnie: `gh` CLI do automatycznych PR-ów
