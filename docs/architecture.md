# Architektura

## Struktura plików
```
auto-coder/
├── auto_coder/
│   ├── __init__.py
│   ├── cli.py          # Interfejs linii komend
│   ├── manager.py      # Główna pętla wykonawcza
│   ├── router.py       # Routing providerów AI
│   ├── validator.py    # Walidacja briefów
│   ├── planner.py      # Synteza planera zadań
│   └── execution/      # Moduły wykonawcze
│       ├── __init__.py
│       ├── core.py     # Rdzeń wykonawczy
│       ├── sprint.py   # Obsługa sprintów
│       └── reviewer.py # Recenzja artefaktów
├── docs/               # Dokumentacja
├── ROADMAP.md          # Plan produktu
├── PROJECT.md          # Specyfikacja projektu
├── requirements.txt    # Zależności Python
└── .env.example        # Szablon konfiguracji
```

## Jak działa kod

### 1. Pętla wykonawcza
Manager działa w cyklu:
```
READ (ROADMAP/PROJECT) → PLAN → EXECUTE → REVIEW → COMMIT
```

### 2. Routing providerów
`ProviderRouter` wybiera dostępnego providera:
- Sprawdza kwoty API (quota probes)
- Wybiera primary lub fallback
- Loguje źródło dostępności

### 3. Walidacja briefów
Validator odrzuca niejasne wymagania:
- Brak kryteriów akceptacji
- Nieokreślony zakres
- Brakujące zależności

### 4. Izolacja zadań
Każde zadanie pracuje w:
- Osobnym git worktree
- Izolowanym środowisku Python
- Oddzielnym kontekście AI

## Jak rozbudować

### Dodanie nowego providera
1. Dodaj klasę w `auto_coder/providers/`
2. Zarejestruj w `ProviderRouter`
3. Dodaj sondę kwotów

### Dodanie nowego modułu wykonawczego
1. Utwórz plik w `auto_coder/execution/`
2. Zaimplementuj interfejs `Executor`
3. Podłącz do orbitratora

### Rozszerzenie walidacji
1. Dodaj regułę w `auto_coder/validator.py`
2. Zaktualizuj `docs/brief-validation.md`
3. Dodaj testy
