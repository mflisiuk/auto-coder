# Instalacja i konfiguracja

## Wymagania

- Python 3.10+
- Git
- Dostęp do Claude Code (subscription) — domyślny provider
- Opcjonalnie: API keys dla innych providerów (Anthropic, OpenAI, Gemini, Qwen)

## Instalacja krok po kroku

### 1. Klonowanie i instalacja

```bash
# Sklonuj repozytorium
git clone https://github.com/mflisiuk/auto-coder && cd auto-coder

# Zainstaluj w trybie editable
pip install -e .
```

### 2. Weryfikacja instalacji

```bash
# Sprawdź czy komenda jest dostępna
auto-coder --help

# Sprawdź doctor (bez probe)
auto-coder doctor
```

### 3. Inicjalizacja w repozytorium

```bash
# Przejdź do repozytorium
cd /path/to/your-repo

# Zainicjalizuj auto-coder
auto-coder init
```

To tworzy:
- `.auto-coder/config.yaml` — konfiguracja projektu
- `.auto-coder/ROADMAP.md` — szablon roadmapy
- `.auto-coder/PROJECT.md` — szablon briefu projektu
- `.auto-coder/PLANNING_HINTS.md` — konwencje repozytorium

### 4. Konfiguracja providerów

**Domyślna konfiguracja (po `init`):**

```yaml
# .auto-coder/config.yaml

# Manager AI
manager_backend: cc
manager_model: claude-opus-4-6

# Worker AI
default_worker: ccg
fallback_worker: cc
```

**Jeśli używasz innych providerów:**

```yaml
# Anthropic (wymaga ANTHROPIC_API_KEY)
manager_backend: anthropic
manager_model: claude-opus-4-6

# OpenAI Codex (wymaga OPENAI_API_KEY)
manager_backend: codex
manager_model: gpt-5

# Qwen (wymaga DASHSCOPE_API_KEY)
default_worker: qwen

# Gemini (wymaga GOOGLE_API_KEY)
default_worker: gemini
```

### 5. Sprawdzenie dostępności providerów

```bash
# Sprawdź status wszystkich providerów
auto-coder doctor --probe-live
```

Przykładowy output:
```
Provider Status:
  cc:      ✓ available (subscription)
  ccg:     ✓ available (subscription)
  cch:     ✓ available (paid)
  anthropic: ✓ available (API key)
  codex:   ✗ unavailable (no API key)
  gemini:  ? unknown
  qwen:    ? unknown
```

## Zmienne środowiskowe

```bash
# Claude Code — brak wymagań (używa lokalnej instalacji)

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI Codex
export OPENAI_API_KEY="sk-..."

# Google Gemini
export GOOGLE_API_KEY="..."

# Alibaba Qwen/Dashscope
export DASHSCOPE_API_KEY="..."
```

## Konfiguracja zaawansowana

### Timeouty i retry

```yaml
manager_timeout_seconds: 180
quota_cooldown_hours: 4
```

### Ścieżki

```yaml
# Polecenia uruchamiane przed każdym worktree
setup_commands:
  - "npm install"
  - "pip install -r requirements.txt"

# Dozwolone ścieżki (puste = wszystkie)
allowed_paths: []

# Chronione ścieżki (nie mogą być modyfikowane)
protected_paths:
  - ".auto-coder/"
  - "docs/"
```

### Auto-merge i PR

```yaml
# Domyślnie: bezpośredni merge do base_branch
auto_commit: true
auto_push: true
auto_merge: true
auto_pr: false

# Jeśli chcesz otwierać PR przed merge:
auto_pr: true
auto_merge: false  # merge dopiero po review
```

## Rozwiązywanie problemów

### Problem: `cc` worker niedostępny

```bash
# Sprawdź czy Claude Code jest zainstalowane
which cc

# Jeśli nie, zainstaluj:
npm install -g @anthropic-ai/claude-code
```

### Problem: Błędy kwotowe (429)

System automatycznie czeka na reset kwoty. Możesz:
- Poczekać `quota_cooldown_hours` (domyślnie 4h)
- Przełączyć na inny provider w `config.yaml`
- Użyć `--loop` trybu dla ciągłego retry

### Problem: Task zawieszony

```bash
# Sprawdź status
cat .auto-coder/PROGRESS.md

# Ręczne odblokowanie
auto-coder unblock <task-id>

# Reset stanu (ostateczność)
auto-coder reset-state
```
