# Instalacja i konfiguracja

## Wymagania

- Python 3.8+
- Git 2.23+ (dla worktrees)
- Dostęp do internetu (API providerów)
- Opcjonalnie: `gh` CLI do automatycznych PR

## Instalacja globalna

```bash
# Sklonuj repozytorium
git clone https://github.com/mflisiuk/auto-coder && cd auto-coder

# Zainstaluj w trybie edytowalnym
pip install -e .
```

## Inicjalizacja w repozytorium

```bash
# Przejdź do repozytorium
cd /path/to/your-repo

# Zainicjalizuj auto-coder
auto-coder init
```

To utworzy strukturę `.auto-coder/`:
```
.auto-coder/
├── config.yaml      # Konfiguracja
├── tasks.yaml       # Backlog zadań (generowany przez plan)
├── logs/            # Logi wykonania
└── state.json       # Stan wykonania
```

## Konfiguracja

### Podstawowa konfiguracja (`.auto-coder/config.yaml`)

```yaml
# Manager backend: cc, claude, anthropic, codex
manager_backend: cc

# Worker backend: ccg, cc, cch, gemini, qwen, codex
default_worker: ccg
fallback_worker: cc

# Ustawienia retry
max_retries: 3
quota_cooldown_hours: 4

# Auto-commit/push/merge
auto_commit: true
auto_push: true
auto_merge: true
auto_pr: false

# Base branch dla merge
base_branch: main
```

### Zmienne środowiskowe

```bash
# Claude Code (domyślny)
export ANTHROPIC_API_KEY=sk-ant-...

# Opcjonalnie: GitHub CLI dla PR
export GITHUB_TOKEN=ghp_...
```

## Weryfikacja instalacji

```bash
# Sprawdź czy auto-coder jest dostępny
auto-coder --help

# Sprawdź konfigurację i dostępność providerów
auto-coder doctor --probe-live
```

Oczekiwany output:
```
✓ Manager backend: cc (available)
✓ Worker backend: ccg (available)
✓ Fallback worker: cc (available)
```

## Następne kroki

1. [Jak używać](usage.md) — generowanie backlogu i uruchamianie
2. [CC-Manager Bridge](cc-manager-bridge-spec.md) — szczegóły konfiguracji managera
3. [Operator runbook](operator-runbook.md) — codzienne operacje
