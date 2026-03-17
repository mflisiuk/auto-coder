# Changelog

## [2026-03-17] - CC/Claude Backend Support in Probe Dispatch
### Co się zmieniło
- **Rozszerzono `_probe_manager_backend`** w `cli.py` o obsługę backendów `cc` i `claude` — teraz `doctor --probe-live` poprawnie sprawdza dostępność Claude Code jako managera
- **Dodano import `CcManagerBridge`** dla aliasów `cc`/`claude` — spójne z `DEFAULT_MANAGER_MODELS`
### Poprawki błędów
- Naprawiono brak obsługi `cc`/`claude` w ścieżce probe — wcześniej `doctor --probe-live` zgłaszał błąd dla tych backendów mimo że były wspierane w `DEFAULT_MANAGER_MODELS`

## [2026-03-17] - Default CC Manager + CCG Worker + Auto-Merge
### Co się zmieniło
- **Domyślny manager backend** zmieniony z `anthropic` na `cc` (Claude Code subscription — nie wymaga API key)
- **Domyślny worker** zmieniony z `cc` na `ccg` (Claude Code z Google subscription)
- **Fallback worker** zmieniony z `cch` na `cc` (Claude Code subscription jako backup)
- **Auto-commit i auto-push** domyślnie włączone (`true`)
- **Auto-merge** domyślnie włączony (`true`) — bezpośredni merge do `base_branch` gdy `auto_pr=false`
- **Dodano obsługę aliasów** w `DEFAULT_MANAGER_MODELS`: `cc` i `claude` → `claude-opus-4-6`
- **work_progress.md** automatycznie pushowany do `main` po każdym zakończonym tasku

### Poprawki błędów
- Naprawiono 5 błędów wykrytych podczas rzeczywistego uruchomienia `ga-cli` (szczegóły w commit `3ad9e6d`)
- Ujednolicono domyślne wartości w `default_config()` z wartościami w przykładowej konfiguracji YAML

## [2026-03-16] - CC-Manager Bridge Integration
### Co się zmieniło
- Dodano mostek `cc-manager` integrujący Claude Code jako backend menedżera
- Zaimplementowano obsługę Claude Code w roli managera do generowania i zarządzania zadaniami
- Rozszerzono dostępne opcje workerów o `cc` (Claude Code) jako domyślny i `cch` (Claude Code paid) jako fallback

### Poprawki błędów
- Naprawiono zawieszanie się procesu przez zamknięcie stdin w moście cc-manager

## [2026-03-16] - Autonomous execution hardening and setup orchestration
### Co się zmieniło
- Dodano w pełni autonomiczne wykonanie zadań z izolowanymi workerami w git worktrees
- Zaimplementowano orchestrator z setup-aware task contracts (setup_commands, baseline_tests, main_test)
- Dodano automatyczne zadania naprawcze (repair tasks) gdy baseline testy nie przejdą
- Wprowadzono deduplikację blockerów środowiskowych i auto-kwarantannę dla baseline blockerów
- Rozbudowano obsługę błędów kwotowych — 429 nie jest zaliczane jako failure, task czeka w `waiting_for_quota`
- Dodano fallback chain workerów: cc → cch → gemini → qwen → codex
- Ulepszono system lease z heartbeatem dla długotrwałych workerów
- Dodano tryb `--loop` do ciągłego działania aż do ukończenia wszystkich tasków
- Zaktualizowano `PROGRESS.md` z emoji statusów i szczegółowymi sekcjami błędów
- Poprawiono komendę `doctor --probe-live` o realny health check API

### Poprawki błędów
- Naprawiono normalizację python → python3 w komendach baseline dla repair tasks
- Naprawiono odblokowywanie zawieszonych łańcuchów naprawczych i stripowanie setup_commands z repair tasks
- Ujednolicono stan SQLite i retry leases po restartach
- Naprawiono hardening wykonania workerów i artefaktów runtime

## [2026-03-16] - Hardening operator workflows and progress reporting
### Co się zmieniło
- Rozszerzono `INPUT_SPEC.md` o rekomendowany plik `PLANNING_HINTS.md` dla konwencji repozytorium
- Dodano `bootstrap-brief` jako opcjonalną komendę dla istniejących repozytoriów
- Zaktualizowano flow startowe w README o `doctor --probe-live`, `plan` i `run --dry-run`
- Dodano `work_progress.md` aktualizowany przy domknięciu taska
- Rozbudowano dokumentację operatora o hardened workflows i progress reporting

### Poprawki błędów (jesli sa)
- Brak poprawek błędów w tej iteracji

## [2026-03-15] - Sondy kwotów i synteza planera
### Co się zmieniło
- Dodano sondy dostępności kwotów dla providerów (quota probes)
- Zaimplementowano syntezę planera zadań
- Rozszerzono komendę `doctor` o wyświetlanie statusu providerów
- Dodano routing providerów z automatycznym wykrywaniem dostępności

### Poprawki błędów (jesli sa)
- Brak poprawek błędów w tej iteracji

## [2026-03-15] - Sondy kwotów i synteza planera
### Co się zmieniło
- Dodano sondy dostępności kwotów dla providerów (quota probes)
- Zaimplementowano syntezę planera zadań
- Rozszerzono komendę `doctor` o wyświetlanie statusu providerów
- Dodano routing providerów z automatycznym wykrywaniem dostępności

### Poprawki błędów (jesli sa)
- Brak poprawek błędów w tej iteracji

## [2026-03-15] - Implementacja pętli wykonawczej i walidacja briefów
### Co się zmieniło
- Dodano implementację pętli wykonawczej dla sprintów 1 i 2
- Wydzielono moduły wykonawcze (execution core modules)
- Podpięto orchestrator pod wydzielone moduły
- Dodano walidację briefów i pakiet wejściowy projektu
- Utworzono dokumentację architektury (ARCHITECTURE.md)

### Poprawki błędów (jesli sa)
- Brak poprawek błędów w tej iteracji

