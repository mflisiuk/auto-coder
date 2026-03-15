# Jak używać auto-coder

Ten dokument opisuje typowe przypadki użycia dla użytkowników końcowych.

## Przypadek 1: Pierwsze uruchomienie z nowym projektem

```bash
# 1. Zainicjalizuj auto-coder w repozytorium
auto-coder init

# 2. Sprawdź środowisko i dostępność providerów
auto-coder doctor

# 3. Wygeneruj plan zadań z briefu
auto-coder plan

# 4. Sprawdź status
auto-coder status

# 5. Uruchom jeden tick pracy
auto-coder run --live
```

## Przypadek 2: Praca ciągła z cronem

```bash
# Dodaj do crontab (uruchomienie co 15 minut)
*/15 * * * * cd /path/to/project && auto-coder run --live >> /var/log/auto-coder.log 2>&1
```

## Przypadek 3: Praca z różnymi backendami

### Anthropic backend
```bash
export ANTHROPIC_API_KEY=sk-ant-...
auto-coder run --live
```

### Codex backend
```bash
# Wymaga zainstalowanego codex i node
auto-coder run --backend codex --live
```

## Tryby pracy

| Tryb | Opis |
|------|------|
| `--dry-run` | Symulacja bez faktycznej pracy |
| `--live` | Pełne wykonanie ticka |
| `--verbose` | Szczegółowe logi |

## Komendy

| Komenda | Opis |
|---------|------|
| `auto-coder init` | Inicjalizacja projektu |
| `auto-coder doctor` | Sprawdzenie środowiska |
| `auto-coder plan` | Generowanie planu z briefu |
| `auto-coder status` | Status tasków i providerów |
| `auto-coder run` | Uruchomienie jednego ticka |
| `auto-coder migrate` | Migracja bazy danych |
