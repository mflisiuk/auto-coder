# Instalacja i konfiguracja

## Wymagania
- Python 3.10+
- Git 2.23+ (dla worktree)
- Dostęp do API managera backendu (np. Jira, GitHub Projects)
- Dostęp do API workerów (np. Claude, GPT, lokalne modele)

## Krok po kroku

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

Edytuj `.env` i ustaw wymagane zmienne:

```ini
# Manager backend
MANAGER_BACKEND=jira
JIRA_URL=https://your-instance.atlassian.net
JIRA_API_KEY=your-api-key

# Worker
WORKER_BACKEND=claude
CLAUDE_API_KEY=your-api-key
WORKER_QUOTA_DAILY=100

# Git
GIT_REMOTE_ORIGIN=https://github.com/your-org/your-repo.git
PROTECTED_BRANCHES=main,master
PROTECTED_PATHS=src/auth/,config/secrets/

# Harmonogram
TICK_INTERVAL_MINUTES=15
MAX_CONCURRENT_TASKS=3

# Retry
MAX_RETRY_ATTEMPTS=3
RETRY_BACKOFF_SECONDS=300
```

### 4. Przygotowanie plików wejściowych
Utwórz w katalogu projektu:

**ROADMAP.md** — luźna roadmapa produktu:
```markdown
# Roadmapa Q1 2026

## Moduł: Płatności
- Integracja ze Stripe
- Webhooki dla zdarzeń płatności
- Panel administracyjny do zwrotów

## Moduł: Użytkownicy
- Rejestracja przez email
- Reset hasła
```

**PROJECT.md** — specyfikacja techniczna:
```markdown
# Projekt

## Stack
- Backend: Python 3.11, FastAPI
- Frontend: React 18, TypeScript
- Baza: PostgreSQL 15

## Struktura repo
/src
  /api - endpointy REST
  /core - logika biznesowa
  /db - modele i migracje

## Komendy
- Testy: pytest tests/
- Build: npm run build
- Lint: ruff check src/

## Zabronione ścieżki
- /src/auth/ - nie modyfikuj
- /config/ - tylko przez infra team
```

**CONSTRAINTS.md** (opcjonalne) — twarde ograniczenia:
```markdown
# Ograniczenia
- Nie dodawaj nowych zależności bez aprobaty
- Nie modyfikuj konfiguracji auth
- Zero zmian infrastrukturalnych
```

### 5. Uruchomienie
```bash
# Tryb ciągły (co TICK_INTERVAL_MINUTES)
python -m auto_coder.manager

# Tryb jednorazowy (jeden tick)
python -m auto_coder.manager --once

# Tryb debug (verbose logging)
python -m auto_coder.manager --debug
```

### 6. Weryfikacja
```bash
# Sprawdź status managera
python -m auto_coder.cli status

# Lista aktywnych zadań
python -m auto_coder.cli tasks list

# Historia wykonania
python -m auto_coder.cli tasks history
```

## Rozwiązywanie problemów

### Błąd: "No quota available"
- Zwiększ `WORKER_QUOTA_DAILY` w `.env`
- Poczekaj na reset kwoty (zwykle o północy)
- Skonfiguruj fallback do innego workera

### Błąd: "Protected path modified"
- Zadanie próbowało zmodyfikować chronioną ścieżkę
- Sprawdź `PROTECTED_PATHS` w `.env`
- Zgłoś zadanie do manual review

### Błąd: "Brief validation failed"
- ROADMAP.md lub PROJECT.md są niejasne
- Sprawdź logi: `tail -f logs/manager.log`
- Uzupełnij brakujące wymagania w plikach wejściowych
