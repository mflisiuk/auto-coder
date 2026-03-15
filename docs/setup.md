# Instalacja i konfiguracja

## Wymagania
- Python 3.9+
- Git
- Dostęp do providerów AI (Anthropic Claude, OpenAI GPT, lub lokalne modele)

## Instalacja krok po kroku

### 1. Klonowanie repozytorium
```bash
git clone https://github.com/auto-coder/auto-coder.git
cd auto-coder
```

### 2. Instalacja zależności
```bash
pip install -r requirements.txt
```

### 3. Konfiguracja środowiska
```bash
cp .env.example .env
```

Edytuj plik `.env` i ustaw wymagane zmienne:

```bash
# Provider AI (wybierz jeden)
ANTHROPIC_API_KEY=sk-ant-...
# LUB
OPENAI_API_KEY=sk-...
# LUB
LOCAL_MODEL_URL=http://localhost:11434

# Konfiguracja projektu
PROJECT_ROOT=/path/to/your/project
USAGE_PATH=/path/to/usage.json

# Opcjonalne
TICK_INTERVAL=15  # Interwał pętli wykonawczej w minutach
```

### 4. Weryfikacja instalacji
```bash
python -m auto_coder.cli doctor
```

Komenda `doctor` sprawdzi:
- Dostępność plików konfiguracyjnych
- Status providerów AI (sondy kwotów)
- Istnienie ROADMAP.md i PROJECT.md
- Poprawność środowiska

## Konfiguracja zaawansowana

### Wielu providerów
System obsługuje routing do wielu providerów. Dodaj w `.env`:

```bash
PRIMARY_PROVIDER=anthropic
FALLBACK_PROVIDER=openai
```

### Izolowane środowisko
Każde zadanie pracuje w osobnym git worktree:

```bash
WORKTREE_BASE=/tmp/auto-coder-worktrees
```
