# Instalacja i konfiguracja

Kompletny przewodnik instalacji `auto-coder` krok po kroku.

## Wymagania systemowe

- **Python**: 3.10 lub nowszy
- **Git**: 2.30 lub nowszy
- **Node.js**: 18+ (dla Claude Code bridge)
- **Claude Code**: zainstalowane globalnie (`npm install -g @anthropic-ai/claude-code`)

## Instalacja globalna

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/mflisiuk/auto-coder
cd auto-coder

# 2. Zainstaluj pakiet Python
pip install -e .

# 3. Zweryfikuj instalację
auto-coder --version
```

## Instalacja Claude Code

```bash
# Zainstaluj Claude Code (wymaga subskrypcji Claude)
npm install -g @anthropic-ai/claude-code

# Zweryfikuj instalację
claude --version

# Zaloguj się (jeśli wymagane)
claude auth
```

## Inicjalizacja repozytorium

```bash
# Przejdź do repozytorium
cd /path/to/your-repo

# Zainicjalizuj auto-coder
auto-coder init
```

To tworzy strukturę:

```
your-repo/
├── .auto-coder/
│   ├── config.yaml        # Konfiguracja projektu
│   ├── tasks/             # Wygenerowane zadania
│   ├── reports/           # Raporty z wykonania
│   └── runtime.json       # Stan runtime (auto-generowany)
├── ROADMAP.md             # Twój brief projektu
├── PROJECT.md             # Dokumentacja projektu
└── PROGRESS.md            # Auto-generowany postęp
```

## Konfiguracja projektu

Edytuj `.auto-coder/config.yaml`:

```yaml
# Podstawowe
project_name: "My Project"
base_branch: "main"
auto_pr: false
auto_merge: true

# Manager (generuje zadania)
manager_model: "cc"  # cc, claude, anthropic, codex

# Worker (wykonuje zadania)
worker_model: "ccg"  # ccg, cc, cch, gemini, qwen, codex
fallback_workers: ["cc", "cch", "gemini", "qwen", "codex"]

# Testy
test_timeout_minutes: 10
baseline_timeout_minutes: 5

# Git
auto_commit: true
auto_push: true

# Powiadomienia (opcjonalne)
slack_webhook: null
```

## Weryfikacja konfiguracji

```bash
# Sprawdź czy auto-coder widzi wszystkie komponenty
auto-coder doctor --probe-live

# Oczekiwany output:
# ✓ Claude Code available
# ✓ Git worktree supported
# ✓ Python 3.10+
# ✓ Config valid
```

## Konfiguracja cron (opcjonalna)

Dla autonomicznego deploymentu:

```bash
# Edytuj crontab
crontab -e

# Dodaj wpis (uruchomienie co 20 minut)
*/20 * * * * cd /path/to/repo && PATH=$PATH:~/.nvm/versions/node/v22.22.0/bin auto-coder run --live >> /var/log/auto-coder.log 2>&1
```

## Rozwiązywanie problemów instalacji

### Claude Code nie wykryte

```bash
# Sprawdź gdzie jest zainstalowane
which claude

# Jeśli w ~/.nvm/versions/node/v22.22.0/bin/claude
# Dodaj do PATH w cron lub exportuj
export PATH=$PATH:~/.nvm/versions/node/v22.22.0/bin
```

### Błąd pip install

```bash
# Upewnij się że Python 3.10+
python --version

# Jeśli starszy, użyj python3.10
python3.10 -m pip install -e .
```

### Git worktree nie działa

```bash
# Sprawdź wersję gita
git --version  # Musi być >= 2.30

# Wyczyść stare worktree
git worktree prune
```
