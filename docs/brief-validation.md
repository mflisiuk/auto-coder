# Walidacja briefów

## Cel

Moduł walidacji briefów zapewnia, że zadania wejściowe są wystarczająco określone, aby mogły być wykonane automatycznie. Zapobiega to:
- Silently inventing missing requirements
- Niejasnym kryteriom akceptacji
- Zadaniom które nie mogą zostać zweryfikowane

## Zasady walidacji

### 1. ROADMAP.md musi zawierać
- Konkretne moduły lub feature'y
- Kryteria akceptacji dla każdego elementu
- Priorytety (high/medium/low) lub kolejność

**Poprawny przykład:**
```markdown
## Moduł: Płatności
- Integracja ze Stripe (high)
  - Obsługa kart Visa, Mastercard
  - Webhooki dla payment_intent.succeeded
  - Retry przy błędach sieciowych (max 3 próby)
```

**Niepoprawny przykład:**
```markdown
## Moduł: Płatności
- Zrób płatności
```

### 2. PROJECT.md musi zawierać
- Stack technologiczny
- Strukturę repozytorium
- Komendy test/build
- Chronione ścieżki (jeśli są)

### 3. CONSTRAINTS.md (opcjonalne)
- Twarde ograniczenia
- Zakazane zmiany
- Wymagane aprobaty

## Komendy walidacji

### Walidacja plików
```bash
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md
```

### Walidacja z CONSTRAINTS
```bash
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md CONSTRAINTS.md
```

### Walidacja pojedynczego zadania
```bash
python -m auto_coder.cli validate-task TASK-123
```

## Wynik walidacji

### Sukces
```
✓ Brief poprawny
- 5 zadań wykonalnych
- 0 ścieżek chronionych
- Kwota wystarczająca: 45/100 tokenów
```

### Błąd — brakujące informacje
```
✗ Brief niejasny - brakuje:
- Kryteriów akceptacji dla modułu Płatności
- Wymagań dotyczących obsługi błędów
- Określenia kompatybilności wstecz

Dodaj brakujące informacje do ROADMAP.md i uruchom ponownie.
```

### Błąd — sprzeczne wymagania
```
✗ Brief sprzeczny
- PROJECT.md wymaga Python 3.11, ale ROADMAP.md wspomina o Python 3.8
- CONSTRAINTS.md zabrania nowych zależności, ale feature wymaga stripe-python

Rozwiąż sprzeczności przed kontynuacją.
```

### Błąd — chronione ścieżki
```
⚠ Brief zawiera modyfikacje chronionych ścieżek
- /src/auth/ — wymaga manual review
- /config/secrets/ — zabronione

Zadania te zostaną oznaczone jako REQUIRE_REVIEW.
```

## Programmatic usage

```python
from auto_coder.planner import BriefValidator

validator = BriefValidator()

# Walidacja plików
result = validator.validate_files(
    roadmap_path="ROADMAP.md",
    project_path="PROJECT.md",
    constraints_path="CONSTRAINTS.md"
)

if result.valid:
    print("Brief poprawny")
    tasks = validator.generate_tasks(result)
else:
    print("Błędy walidacji:")
    for error in result.errors:
        print(f"  - {error}")
    
    if result.missing:
        print("Brakuje:")
        for item in result.missing:
            print(f"  - {item}")
```

## Retry po walidacji

Jeśli brief zostanie odrzucony:
1. Popraw pliki wejściowe zgodnie z feedbackiem
2. Uruchom walidację ponownie
3. Po sukcesie — zadania trafią do queue

```bash
# Pierwsza próba — odrzucona
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md
# ✗ Brief niejasny - brakuje: Kryteriów akceptacji...

# Naprawa
nano ROADMAP.md  # Dodaj kryteria akceptacji

# Druga próba — sukces
python -m auto_coder.cli validate-brief ROADMAP.md PROJECT.md
# ✓ Brief poprawny
```
