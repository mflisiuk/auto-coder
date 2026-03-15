# Jak używać auto-coder

## Przypadek 1: Codzienna praca z roadmapą

### Krok 1: Przygotuj dokumentację
```bash
# Edytuj ROADMAP.md z nowymi feature'ami
nano ROADMAP.md

# Upewnij się, że PROJECT.md jest aktualny
cat PROJECT.md
```

### Krok 2: Uruchom managera
```bash
# W tle, co 15 minut
python -m auto_coder.manager &

# Lub przez cron (co 15 minut)
crontab -e
# */15 * * * * cd /path/to/auto-coder && python -m auto_coder.manager --once
```

### Krok 3: Monitoruj postępy
```bash
# Status bieżący
python -m auto_coder.cli status

# Szczegóły zadania
python -m auto_coder.cli tasks show TASK-123

# Logi na żywo
tail -f logs/execution.log
```

### Krok 4: Review commitów
```bash
# Lista gotowych commitów
git log --oneline origin/feature-branch..HEAD

# Akceptacja
python -m auto_coder.cli review accept TASK-123

# Odrzucenie z feedbackiem
python -m auto_coder.cli review reject TASK-123 --reason "Nie przechodzi testów"
```

## Przypadek 2: Walidacja briefu przed wykonaniem

### Sprawdzenie czy brief jest wystarczający
```bash
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md
```

**Przykładowa odpowiedź (sukces):**
```
✓ Brief poprawny
- 3 zadania wykonalne
- 0 ścieżek chronionych
- Kwota wystarczająca: 45/100 tokenów
```

**Przykładowa odpowiedź (błąd):**
```
✗ Brief niejasny
Brakuje:
- Definicji kryteriów akceptacji dla modułu Płatności
- Wymagań dotyczących obsługi błędów
- Określenia kompatybilności wstecz
```

### Naprawa briefu
```bash
# Dodaj brakujące informacje do ROADMAP.md
cat >> ROADMAP.md << 'EOF'

## Kryteria akceptacji - Płatności
- Obsługa kart Visa, Mastercard
- Webhooki potwierdzające płatność
- Retry przy błędach sieciowych (max 3 próby)
EOF

# Ponowna walidacja
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md
```

## Przypadek 3: Praca z zadaniami blokowymi

### Sprawdzenie zablokowanych zadań
```bash
python -m auto_coder.cli tasks list --status blocked
```

### Analiza przyczyny blokady
```bash
python -m auto_coder.cli tasks show TASK-456 --verbose
```

**Typowe przyczyny:**
- `quota_exhausted` — czekaj na reset kwoty
- `protected_path` — zadanie wymaga manual review
- `validation_failed` — brief niejasny, potrzebne uzupełnienia
- `review_rejected` — worker odrzucił zadanie po review

### Odblokowanie zadania
```bash
# Po zwiększeniu kwoty
python -m auto_coder.cli tasks resume TASK-456

# Po ręcznej akceptacji zmian chronionych
python -m auto_coder.cli tasks approve-protected TASK-456

# Po uzupełnieniu briefu
python -m auto_coder.cli tasks retry TASK-456
```

## Tryby pracy

### Tryb ciągły (domyślny)
```bash
python -m auto_coder.manager
```
Manager działa w pętli, wzbudzany co `TICK_INTERVAL_MINUTES`.

### Tryb jednorazowy
```bash
python -m auto_coder.manager --once
```
Jeden tick, potem exit. Przydatne do testów i cron.

### Tryb debug
```bash
python -m auto_coder.manager --debug
```
Verbose logging, przydatne przy rozwiązywaniu problemów.

### Tryb suchy (dry-run)
```bash
python -m auto_coder.manager --dry-run
```
Symulacja bez rzeczywistego wykonywania zadań.
