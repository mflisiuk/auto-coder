# Jak używać auto-coder

Ten dokument opisuje typowe przypadki użycia `auto-coder` dla użytkowników końcowych.

## Przypadek 1: Pierwsze uruchomienie w nowym repozytorium

```bash
# 1. Przejdź do repozytorium
cd /path/to/your-project

# 2. Zainicjalizuj auto-coder
auto-coder init

# 3. Sprawdź konfigurację i dostępność providerów
auto-coder doctor --probe-live

# 4. Wygeneruj backlog z ROADMAP.md / PROJECT.md
auto-coder plan

# 5. Przejrzyj wygenerowany plan
cat .auto-coder/BACKLOG.md

# 6. Uruchom w trybie dry-run (symulacja)
auto-coder run --dry-run

# 7. Uruchom w trybie live (autonomiczne wykonanie)
auto-coder run --live
```

**Co się dzieje:**
- Manager AI generuje zadania z briefu
- Workery wykonują zadania w izolowanych git worktrees
- Po każdym tasku `work_progress.md` jest aktualizowany i pushowany do `main`
- Po wszystkich taskach następuje auto-commit, auto-push i auto-merge (domyślnie włączone)

## Przypadek 2: Ciągłe działanie z pętlą (--loop)

```bash
# Uruchom w trybie ciągłym aż do ukończenia wszystkich tasków
auto-coder run --live --loop
```

**Zachowanie:**
- System działa w pętli co ~20 minut (rekomendowany interwał cron)
- Po każdym ticku aktualizuje `PROGRESS.md` i `work_progress.md`
- Błędy kwotowe (429) nie przerywają działania — task czeka w `waiting_for_quota`
- Po ukończeniu wszystkich tasków proces się kończy

## Przypadek 3: Praca z istniejącym repozytorium (bootstrap)

```bash
# 1. Jeśli repozytorium już ma kod, wygeneruj brief
auto-coder bootstrap-brief

# 2. Przejrzyj i edytuj wygenerowany brief
cat .auto-coder/PROJECT.md

# 3. Wygeneruj plan
auto-coder plan

# 4. Uruchom
auto-coder run --live
```

## Przydatne komendy

```bash
# Sprawdź status providerów i kwot
auto-coder doctor --probe-live

# Wyświetl aktualny postęp
cat .auto-coder/PROGRESS.md
cat work_progress.md

# Ręczne odblokowanie taska po błędzie
auto-coder unblock <task-id>

# Wyczyść stan i zacznij od nowa
auto-coder reset-state
```

## Konfiguracja domyślna (po `auto-coder init`)

```yaml
# Manager AI
manager_enabled: true
manager_backend: cc          # Claude Code subscription (brak API key)
manager_model: claude-opus-4-6

# Worker AI
default_worker: ccg          # Claude Code z Google subscription
fallback_worker: cc          # Claude Code subscription jako backup

# Git automation
auto_commit: true
auto_push: true
auto_merge: true             # bezpośredni merge do base_branch
auto_pr: false               # wyłączony (włącz jeśli potrzebne PR)

# Review
review_required: true
```

## Tryby pracy

| Tryb | Komenda | Opis |
|------|---------|------|
| Symulacja | `--dry-run` | Pokazuje co zostanie zrobione, nie wykonuje |
| Live | `--live` | Autonomiczne wykonanie wszystkich tasków |
| Pętla | `--live --loop` | Ciągłe działanie aż do ukończenia |
| Pojedynczy task | `--task <id>` | Wykonaj tylko określony task |
