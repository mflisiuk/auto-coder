# Jak używać auto-coder

Ten dokument opisuje typowe przypadki użycia `auto-coder` dla użytkowników końcowych.

## Przypadek 1: Inicjalizacja nowego projektu

Gdy zaczynasz nowy projekt i chcesz, aby auto-coder pomógł Ci go rozwinąć:

```bash
# 1. Sklonuj repozytorium i zainstaluj
git clone <twoje-repo-z-auto-coderem> && cd auto-coder
pip install -e .

# 2. Zainicjalizuj strukturę projektu
auto-coder init

# 3. Skonfiguruj klucz API
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Sprawdź dostępność providerów
auto-coder doctor --probe-live

# 5. Wygeneruj plan z istniejących dokumentów
auto-coder plan

# 6. Uruchom w trybie dry-run najpierw
auto-coder run --dry-run

# 7. Gdy wszystko wygląda dobrze - uruchom na żywo
auto-coder run --live
```

## Przypadek 2: Dołączenie do istniejącego repozytorium

Gdy pracujesz nad istniejącym repozytorium i chcesz wygenerować brief z obecnych dokumentów:

```bash
# 1. Wygeneruj brief z istniejących plików
auto-coder bootstrap-brief /path/to/your/repo

# 2. Jeśli chcesz nadpisać istniejące pliki briefu
auto-coder bootstrap-brief /path/to/your/repo --force

# 3. Sprawdź wygenerowane pliki:
#    - ROADMAP.md
#    - PROJECT.md
#    - PLANNING_HINTS.md (opcjonalny)
#    - CONSTRAINTS.md (opcjonalny)
#    - ARCHITECTURE_NOTES.md (opcjonalny)
```

## Przypadek 3: Praca z taskami i monitorowanie postępu

Podczas pracy auto-coder aktualizuje plik `work_progress.md`:

```bash
# 1. Uruchom pętlę wykonawczą
auto-coder run --live

# 2. Monitoruj postęp w czasie rzeczywistym
tail -f work_progress.md

# 3. Sprawdź status providerów i kwoty
auto-coder doctor

# 4. Jeśli coś pójdzie nie tak - sprawdź logi operatora
#    (szczegóły w docs/operator-runbook.md)
```

## Tryby uruchamiania

| Tryb | Komenda | Opis |
|------|---------|------|
| Dry-run | `auto-coder run --dry-run` | Symulacja bez faktycznych zmian |
| Live | `auto-coder run --live` | Pełne wykonanie z commitami |
| Planowanie | `auto-coder plan` | Generowanie backlogu z briefu |

## Pliki wejściowe

Auto-coder wymaga następujących plików w projekcie:

- **Wymagane:** `ROADMAP.md`, `PROJECT.md`
- **Opcjonalne (rekomendowane):** `PLANNING_HINTS.md`, `CONSTRAINTS.md`, `ARCHITECTURE_NOTES.md`
- **Opcjonalne:** `tasks.local.yaml` dla lokalnych nadpisań

Więcej: [Input pack](docs/inputs.md), [Brief validation](docs/brief-validation.md)
