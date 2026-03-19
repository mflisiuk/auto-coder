# Walidacja YAML

`auto-coder` zawiera wbudowane narzędzia do walidacji plików YAML używanych w projekcie. Komenda `auto-coder validate` pomaga wykryć typowe błędy składniowe i logiczne przed uruchomieniem workflow.

## Użycie

```bash
# Waliduj tasks.yaml w bieżącym repozytorium
auto-coder validate

# Waliduj konkretny plik YAML
auto-coder validate tasks.yaml

# Waliduj plik z kontekstem
auto-coder validate path/to/file.yaml --context "project brief"
```

## Co jest walidowane

### 1. Składnia YAML

Funkcja `safe_load_yaml()` wykrywa i raportuje:

- **Niecytowane stringi z backtickami** — np. `` value: `command` `` powinno być `value: "`command`"`
- **Niecytowane stringi z dwukropkami** — np. `key: value: extra` powinno być `key: "value: extra"`
- **Błędy indentacji** — niepoprawne wcięcia w strukturze YAML

Przykład błędu:
```
FAIL: YAML syntax error in tasks.yaml
  while scanning a simple key
    in "<unicode string>", line 5, column 1
      could not find expected ':'
    in "<unicode string>", line 6, column 1

Common fixes:
  - Quote strings containing backticks: `value` → "`value`"
  - Quote strings containing colons: key: value → "key: value"
  - Check line 5
```

### 2. Struktura tasks.yaml

Funkcja `validate_tasks_yaml()` sprawdza:

- **Istnienie pliku** — czy `tasks.yaml` istnieje
- **Poprawność YAML** — czy plik jest poprawnym YAML
- **Struktura root** — czy root to mapping z kluczem `tasks`
- **Typ tasks** — czy `tasks` to lista
- **Pusta lista** — ostrzeżenie jeśli lista zadań jest pusta
- **Struktura zadań** — czy każde zadanie to mapping
- **Pole ID** — czy każde zadanie ma pole `id`
- **Duplikaty ID** — czy wszystkie ID są unikalne
- **Backticki w stringach** — czy stringi z backtickami są zacytowane

## Przykłady typowych błędów

### Błąd: Niecytowany backtick

```yaml
# ŹLE
tasks:
  - id: task-1
    description: Run `npm install` w katalogu projektu

# DOBRZE
tasks:
  - id: task-1
    description: "Run `npm install` w katalogu projektu"
```

### Błąd: Duplikat ID

```yaml
# ŹLE
tasks:
  - id: task-1
    description: First task
  - id: task-1  # duplikat!
    description: Second task

# DOBRZE
tasks:
  - id: task-1
    description: First task
  - id: task-2
    description: Second task
```

### Błąd: Brakujące pole ID

```yaml
# ŹLE
tasks:
  - description: Task without ID
    commands: [...]

# DOBRZE
tasks:
  - id: task-1
    description: Task with ID
    commands: [...]
```

## Integracja z workflow

Walidacja jest automatycznie uruchamiana przed:

- `auto-coder plan` — walidacja briefu projektu
- `auto-coder run` — walidacja `tasks.yaml`

Jeśli walidacja nie powiedzie się, workflow zostanie zatrzymany z komunikatem błędu.

## API

### `safe_load_yaml(path, context)`

Bezpieczne ładowanie pliku YAML.

```python
from pathlib import Path
from auto_coder.cli import safe_load_yaml

data = safe_load_yaml(Path("tasks.yaml"), context="tasks.yaml")
```

### `validate_tasks_yaml(path)`

Walidacja struktury `tasks.yaml`. Zwraca tuple `(is_valid, issues)`.

```python
from pathlib import Path
from auto_coder.cli import validate_tasks_yaml

is_valid, issues = validate_tasks_yaml(Path("tasks.yaml"))
if not is_valid:
    for issue in issues:
        print(f"Issue: {issue}")
```

## Zobacz też

- [Brief Validation](brief-validation.md) — walidacja briefu projektu
- [Common Pitfalls](common-pitfalls.md) — typowe problemy i rozwiązania
