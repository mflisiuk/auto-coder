# Instalacja i konfiguracja

## Wymagania

- Python 3.10+
- Git
- Node.js (tylko dla backendu codex)
- Dostęp do API (Anthropic lub Codex)

## Instalacja

```bash
git clone <twoje-repo-z-auto-coderem>
cd auto-coder
pip install -e .
```

## Inicjalizacja projektu

W repozytorium, które ma być rozwijane:

```bash
auto-coder init
```

Tworzy to strukturę:

```text
.auto-coder/
  config.yaml      # Konfiguracja
  state.db         # SQLite z taskami
  .gitignore       # Ignorowane pliki
```

## Konfiguracja backendu

### Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

W `.auto-coder/config.yaml`:

```yaml
manager_backend: anthropic
manager_model: claude-sonnet-4-20250514
default_worker: anthropic
```

### Codex

Wymagania:
- Zainstalowany `codex` CLI
- Zainstalowany `node`
- Aktywna autoryzacja CLI

W `.auto-coder/config.yaml`:

```yaml
manager_backend: codex
manager_model: ""   # pusty = backend-specific default
default_worker: codex
```

## Wymagania briefu

W katalogu repo muszą istnieć:

- `ROADMAP.md` - roadmapa projektu
- `PROJECT.md` - opis projektu

Szczególe w [INPUT_SPEC.md](../INPUT_SPEC.md).

## Weryfikacja

```bash
auto-coder doctor
```

Komenda wyświetli:
- Status providerów
- Dostępne kwoty (quota)
- Wykryte problemy
