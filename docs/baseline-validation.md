# Baseline Validation

Dokument opisuje mechanizm walidacji baseline commands — jak poprawnie konfigurować taski tworzące i modyfikujące pliki.

## Problem

Taski tworzące pliki od zerca często miały błędnie skonfigurowane `baseline_commands` — odnosiły się do plików, które jeszcze nie istniały. To powodowało:
- Niepotrzebne failure baseline testów
- Blokowanie tasków rodziców
- Wymaganie ręcznej interwencji

## Rozwiązanie

### Taski tworzące pliki od zera

Użyj pustej listy `baseline_commands`:

```json
{
  "id": "create-auth-module",
  "title": "Create new authentication module",
  "allowed_paths": ["src/auth/**"],
  "baseline_commands": [],
  "test_commands": ["pytest tests/auth/"]
}
```

To całkowicie pomija fazę baseline tests — task jest walidowany tylko przez `test_commands` po wykonaniu.

### Taski modyfikujące istniejące pliki

Użyj standardowych `baseline_commands`:

```json
{
  "id": "fix-auth-bug",
  "title": "Fix authentication bug in login",
  "allowed_paths": ["src/auth/**"],
  "baseline_commands": ["pytest tests/auth/test_login.py"],
  "test_commands": ["pytest tests/auth/test_login.py"]
}
```

Baseline testy są uruchamiane przed zmianą — jeśli failują, task jest odrzucany z ostrzeżeniem.

## validate_baseline_spec()

Funkcja `validate_baseline_spec(task, repo_root)` zwraca listę ostrzeżeń gdy:
- `baseline_commands` odnosi się do plików z `allowed_paths` które nie istnieją
- Task tworzy pliki od zera ale ma niepuste `baseline_commands`

Przykładowe ostrzeżenia:

```
[task-spec WARNING] baseline_commands reference files that don't exist yet: src/auth/new_module.py
[task-spec WARNING] Task creates files from scratch but has baseline_commands — consider using baseline_commands: []
```

## Naprawa tasków rodziców

Poprawiono mechanizm blokowania tasków rodziców:

- **Missing runtime dependency** — task rodzica nie jest już permanentnie blokowany; system czeka na dostępność dependency
- **Quarantined repair task** — repair task w kwarantannie nie blokuje permanentnie rodzica; po timeout rodzica jest odblokowany

## Przykłady konfiguracji

### Przykład 1: Nowy feature — całkowicie nowe pliki

```json
{
  "id": "add-payment-gateway",
  "title": "Add Stripe payment gateway integration",
  "allowed_paths": ["src/payments/**", "tests/payments/**"],
  "baseline_commands": [],
  "test_commands": [
    "pytest tests/payments/",
    "mypy src/payments/"
  ]
}
```

### Przykład 2: Refactor — modyfikacja istniejących plików

```json
{
  "id": "refactor-auth-service",
  "title": "Refactor AuthService to use dependency injection",
  "allowed_paths": ["src/auth/service.py"],
  "baseline_commands": [
    "pytest tests/auth/test_service.py",
    "ruff check src/auth/service.py"
  ],
  "test_commands": [
    "pytest tests/auth/test_service.py",
    "ruff check src/auth/service.py"
  ]
}
```

### Przykład 3: Bugfix — mała zmiana z testem regresji

```json
{
  "id": "fix-login-timeout",
  "title": "Fix login timeout not being respected",
  "allowed_paths": ["src/auth/login.py"],
  "baseline_commands": ["pytest tests/auth/test_login.py::test_timeout"],
  "test_commands": ["pytest tests/auth/test_login.py::test_timeout"]
}
```

## Best practices

1. **Zawsze używaj `baseline_commands: []` dla nowych plików** — unikniesz false positive failures
2. **Testuj baseline na istniejących plikach** — baseline ma wykryć regresje, nie failure nieistniejących plików
3. **Dodawaj testy regresji** — dla bugfixów dodawaj konkretne testy które failują przed fixem
4. **Używaj allowed_paths restrykcyjnie** — ograniczaj task do minimalnej potrzebnej ścieżki
