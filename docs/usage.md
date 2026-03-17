# Jak używać

## Przegląd workflow

```
1. init → 2. plan → 3. run --dry-run → 4. run --live
```

## Krok 1: Inicjalizacja

```bash
cd /path/to/your-repo
auto-coder init
```

## Krok 2: Generowanie backlogu

```bash
# Wygeneruj zadania z briefu (ROADMAP.md, PROJECT.md)
auto-coder plan
```

Output:
```
✓ Generated 12 tasks from project brief
✓ Saved to .auto-coder/tasks.yaml
```

## Krok 3: Dry-run (rekomendowane)

```bash
# Sprawdź co zostanie wykonane
auto-coder run --dry-run
```

## Krok 4: Uruchomienie

```bash
# Uruchom w trybie live
auto-coder run --live
```

### Tryb pętli (ciągłe wykonanie)

```bash
# Uruchom aż do ukończenia wszystkich zadań
auto-coder run --live --loop
```

## Monitorowanie postępu

### Status zadań

```bash
auto-coder status
```

### Logi w czasie rzeczywistym

```bash
tail -f .auto-coder/logs/manager.log
```

### Progress na GitHub

Pliki `PROGRESS.md` i `work_progress.md` są automatycznie commitowane i pushowane po każdym zakończonym tasku.

## Przykład: Pełne uruchomienie

```bash
# 1. Przygotowanie
cd /path/to/your-repo
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Inicjalizacja
auto-coder init

# 3. Sprawdzenie providerów
auto-coder doctor --probe-live

# 4. Generowanie backlogu
auto-coder plan

# 5. Dry-run
auto-coder run --dry-run

# 6. Uruchomienie
auto-coder run --live
```

## Przykład: Cron deployment

```bash
# Dodaj cron job (co 20 minut)
auto-cader operator install-cron --interval=20

# Sprawdź zainstalowane crony
crontab -l
```

## Przykład: Operator override

```bash
# Wymuś retry dla konkretnego zadania
auto-cader operator force-retry --task=task-003

# Zmień worker dla następnego zadania
auto-cader operator set-worker --worker=gemini
```

## Rozwiązywanie problemów

### Błąd kwotowy (429)

System automatycznie czeka na reset kwoty. Task przechodzi w stan `waiting_for_quota`.

### Zawieszone zadanie

```bash
# Sprawdź status
auto-cader status

# Wymuś retry
auto-cader operator force-retry --task=<task-id>
```

### Debug logging

```bash
auto-cader run --live --verbose
```

## Zobacz też

- [Setup](setup.md) — instalacja i konfiguracja
- [Operator runbook](operator-runbook.md) — codzienne operacje
- [Common pitfalls](common-pitfalls.md) — typowe problemy
