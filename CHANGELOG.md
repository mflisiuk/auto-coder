# Changelog

## [2026-03-20] - Quota Error Detection Improvement
### Co się zmieniło
- **Zrefaktoryzowano `is_quota_error()`** w `worker.py` — wykrywa błędy kwotowe niezależnie od `returncode`, parsując JSON z `is_error:true` dla dowolnego kodu wyjścia
- **Rozszerzono listę fraz kwotowych** — dodano "subscription limit", "limit reached" oraz wzorce regex `hit\s+(?:your\s+)?limit` i `subscription\s+limit`
- **Uproszczono logikę** — usunięto specjalne przetwarzanie dla `returncode == 0`, jednolita pętla dla wszystkich przypadków

### Poprawki błędów
- Naprawiono niewykrywanie błędów "hit your limit" gdy Claude Code zwraca niezerowy returncode
- Naprawiono zależność detekcji od konkretnego kodu wyjścia — teraz liczy się treść błędu, nie returncode

## [2026-03-19] - Auto-Generated Artifacts Ignore Policy
### Co się zmieniło
- **Dodano `IGNORED_PATTERNS`** w `policy.py` — lista wzorców plików auto-generowanych (`__pycache__`, `.pyc`, `.pyo`, `.pyd`, `.so`, `.dll`, `.egg-info`)
- **Dodano `_should_ignore()`** w `policy.py` — funkcja sprawdzająca czy ścieżka pasuje do wzorców ignorowanych
- **Zaktualizowano `validate_changed_files()`** — pomija pliki auto-generowane przed walidacją protected/allowed paths

### Poprawki błędów
- Naprawiono błędne flagowanie plików `__pycache__` i innych artifactów jako naruszenia protected paths
- Naprawiono konieczność ręcznego dodawania wyjątków dla auto-generowanych plików w konfiguracji policy

## [2026-03-19] - YAML Validation Command
### Co się zmieniło
- **Dodano `safe_load_yaml()`** w `cli.py` — bezpieczne ładowanie YAML z pomocnymi komunikatami błędów dla typowych problemów (niezacytowane stringi z backtickami, dwukropkami, błędy indentacji)
- **Dodano `validate_tasks_yaml()`** w `cli.py` — walidacja struktury i zawartości `tasks.yaml` (sprawdzenie duplikatów ID, brakujących pól, niezacytowanych backticków)
- **Dodano komendę `auto-coder validate`** — CLI command do walidacji plików YAML projektu
- **Zintegrowano walidację z flow** — automatyczne ostrzeżenia przy typowych błędach YAML

### Poprawki błędów
- Naprawiono konieczność ręcznego debugowania błędów YAML — teraz system podpowiada konkretne linie i rozwiązania
- Naprawiono brak walidacji duplikatów ID w taskach — teraz wykrywane i raportowane

## [2026-03-18] - Auto-Validate and Fix Pytest -k Syntax
### Co się zmieniło
- **Dodano `validate_pytest_k_syntax()`** w `policy.py` — wykrywa typowe błędy składniowe w wyrażeniach pytest `-k` (użycie `|`, `&`, `!` zamiast `or`, `and`, `not`)
- **Dodano `fix_pytest_k_syntax()`** w `policy.py` — automatycznie naprawia wykryte błędy zamieniając operatory regex na operatory Pythona
- **Zintegrowano walidację z `run_one_task()`** w `orchestrator.py` — przed uruchomieniem baseline testów sprawdzana jest składnia `-k` i automatycznie aplikowane są poprawki
- **Dodano logowanie ostrzeżeń** — komunikaty `[pytest-k WARNING]` i `[pytest-k AUTO-FIX]` informują o wykrytych problemach i naprawach

### Poprawki błędów
- Naprawiono błędy uruchomieniowe pytest gdy w task-spec użyto składni regex (`test_a|test_b`) zamiast Python boolean expressions (`test_a or test_b`)
- Naprawiono konieczność ręcznej korekty tasków — teraz system sam wykrywa i naprawia typowe pomyłki składniowe

## [2026-03-18] - Pytest Exit Code 5 Handling
### Co się zmieniło
- **Dodano stałą `PYTEST_NO_TESTS_COLLECTED = 5`** w `executor.py` — jawna definicja exit code pytest oznaczającego "brak testów do uruchomienia"
- **Rozszerzono `run_tests()`** o parametr `skip_no_tests: bool = False` — pozwala traktować exit code 5 jako sukces
- **Zaktualizowano `orchestrator.py`** — setup i baseline testy używają `skip_no_tests=True` domyślnie

### Poprawki błędów
- Naprawiono błędne oznaczanie tasków jako failed gdy pytest nie znalazł testów (exit 5) — dla baseline/setup runs jest to oczekiwane zachowanie (testy mają zostać utworzone przez task)

## [2026-03-17] - Wildcard Support in Allowed Paths
### Co się zmieniło
- **Dodano obsługę wildcardów** w `policy.py` — `**` lub `*` w `allowed_paths` zezwala na wszystkie ścieżki bez sprawdzania prefiksów

### Poprawki błędów
- Naprawiono konieczność ręcznego dodawania każdego prefiksu — teraz jeden `**` wystarcza dla wszystkich ścieżek

## [2026-03-17] - Baseline Validation & Branch Cleanup
### Co się zmieniło
- **Dodano `validate_baseline_spec()`** w `policy.py` — ostrzeżenia gdy komendy baseline odnoszą się do plików, które task ma dopiero utworzyć
- **Smart baseline skip** — taski tworzące pliki od zera mogą ustawić `baseline_commands: []` aby pominąć baseline
- **Automatyczne usuwanie branchy** — feature branch jest usuwany z origin i lokalnie po udanym merge do base branch
- **Naprawiono blokowanie tasków rodziców** — brakujące runtime dependency i quarantined repair task nie blokują już permanentnie rodzica

### Poprawki błędów
- Naprawiono permanentne blokowanie tasków rodziców przez missing runtime dependency
- Naprawiono permanentne blokowanie tasków rodziców przez quarantined repair task
- Naprawiono pozostawianie branchy feature po merge — teraz są automatycznie usuwane
- Naprawiono heurystykę baseline — zastąpiono jawną walidacją task-spec

## [2026-03-17] - PATH Augmentation for Cron/Minimal Environments
### Co się zmieniło
- **Rozszerzono `CcManagerBridge.is_available()`** w `cc_bridge.py` o sprawdzanie common install locations (`~/.nvm/versions/node/v22.22.0/bin/claude`, `~/.local/bin/claude`, `/usr/local/bin/claude`) — działa w cron środowiskach bez sourcing ~/.bashrc
- **Dodano augmentację PATH** w `worker.py` — workerzy (ccg, cc) są odnajdywani nawet w minimalnych środowiskach cron
- **Zaktualizowano `bridges/cc-manager/src/index.mjs`** o augmentację PATH z common install locations — spójne zachowanie w Node.js bridge

### Poprawki błędów
- Naprawiono niewykrywalność Claude Code w cron/minimal environments gdzie PATH nie zawiera ~/.nvm/versions/node/v22.22.0/bin
- Naprawiono failure workerów ccg/cc uruchamianych przez cron — teraz PATH jest poprawnie ustawiane przed spawnem subprocessów

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

