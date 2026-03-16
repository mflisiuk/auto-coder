# Instalacja i konfiguracja

## Wymagania

- Python 3.9+
- Dostęp do API: Anthropic lub Codex
- Git (dla worktree)

## Instalacja krok po kroku

### 1. Klonowanie repozytorium

```bash
git clone <twoje-repo-z-auto-coderem>
cd auto-coder
```

### 2. Instalacja w trybie development

```bash
pip install -e .
```

### 3. Konfiguracja providerów

#### Anthropic (zalecane)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

#### Codex (alternatywa)

Skonfiguruj dostęp zgodnie z dokumentacją Codex API.

### 4. Inicjalizacja projektu

```bash
auto-coder init
```

### 5. Weryfikacja konfiguracji

```bash
auto-coder doctor --probe-live
```

Komenda `doctor` sprawdzi:
- Dostępność API providerów
- Status kwot (quota)
- Konfigurację środowiska
- Gotowość do pracy

## Konfiguracja zaawansowana

### Git worktree dla worker CLI

Auto-coder używa osobnego git worktree dla izolowanego środowiska pracy:

```bash
# Worktree jest tworzone automatycznie przy pierwszym uruchomieniu
# Możesz sprawdzić status:
git worktree list
```

### Pliki konfiguracyjne

Umieść w root projektu:

- `ROADMAP.md` - cele i kamienie milowe
- `PROJECT.md` - specyfikacja funkcjonalna
- `PLANNING_HINTS.md` - konwencje repozytorium (nazewnictwo, style API)
- `CONSTRAINTS.md` - ograniczenia techniczne
- `ARCHITECTURE_NOTES.md` - notatki architektoniczne

### Zmienne środowiskowe

| Zmienna | Opis | Przykład |
|---------|------|----------|
| `ANTHROPIC_API_KEY` | Klucz API Anthropic | `sk-ant-...` |
| `CODEX_API_KEY` | Klucz API Codex | `...` |
| `AUTO_CODER_DEBUG` | Tryb debugowania | `1` |

## Rozwiązywanie problemów

### Brak kwoty API

Uruchom `auto-coder doctor --probe-live` aby sprawdzić dostępność kwot.

### Błędy walidacji briefu

Sprawdź [Brief validation](docs/brief-validation.md) dla szczegółów.

### Problemy z git worktree

```bash
# Usuń istniejące worktree i zainicjalizuj ponownie
git worktree remove <path>
auto-coder init
```
