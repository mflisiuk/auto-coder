# Jak używać

## Podstawowe użycie

### Uruchomienie managera
```bash
python -m auto_coder.manager --tick-interval 15
```

Manager będzie cyklicznie:
1. Czytał ROADMAP.md i PROJECT.md
2. Generował zadania
3. Wybierał wykonawców
4. Uruchamiał pracę w izolowanym środowisku
5. Recenzował wyniki
6. Commitował gotową pracę

### Tryb jednorazowy
```bash
python -m auto_coder.manager --once
```

### Walidacja briefów
```bash
python -m auto_coder.validator --brief path/to/brief.md
```

System odrzuci niejasne wymagania i zwróci listę braków.

## Przykłady użycia

### Przykład 1: Nowy feature z roadmapy
1. Dodaj wpis do ROADMAP.md:
```markdown
## Q1 2026
- [ ] System powiadomień email
```

2. Uruchom managera:
```bash
python -m auto_coder.manager --once
```

3. Sprawdź status:
```bash
python -m auto_coder.cli status
```

### Przykład 2: Debugowanie konfiguracji
```bash
# Sprawdź status systemu
python -m auto_coder.cli doctor

# Wyświetl dostępne zadania
python -m auto_coder.cli list

# Sprawdź postępy
python -m auto_coder.cli status
```

### Przykład 3: Praca z istniejącym projektem
```bash
# Skonfiguruj ścieżkę do projektu
export PROJECT_ROOT=/path/to/existing/project

# Uruchom z istniejącą dokumentacją
python -m auto_coder.manager --tick-interval 30
```

## Komendy CLI

| Komenda | Opis |
|---------|------|
| `doctor` | Diagnoza systemu i providerów |
| `status` | Status bieżących zadań |
| `list` | Lista zadań |
| `validate` | Walidacja briefu |
