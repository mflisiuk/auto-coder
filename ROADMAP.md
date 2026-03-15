# auto-coder — Roadmap

## Co to jest

Autonomiczny system kodowania. Dajesz mu luźną roadmapę projektu, on sam:
1. Rozbija ją na konkretne taski (przez Claude API)
2. Spawuje agentów kodujących (cc, cch, ccg, codex, ...)
3. Ocenia wyniki (manager na Claude API)
4. Daje feedback i ponawia aż do skutku
5. Commituje i pushuje gdy zadanie dowiezione

Działa na cronie (co godzinę). Ty tylko rozrysowujesz co ma być zrobione.

## Wejście (co przygotowujesz TY)

```
twoje-repo/
├── ROADMAP.md       ← luźny opis co chcesz zbudować
└── PROJECT.md       ← tech stack, struktura repo, zakazane ścieżki
```

## Wyjście (co robi system automatycznie)

```
twoje-repo/
└── .auto-coder/
    ├── config.yaml  ← konfiguracja (generowana przez: auto-coder init)
    ├── tasks.yaml   ← backlog tasków (generowany przez: auto-coder plan)
    ├── state.json   ← stan wykonania
    ├── usage.json   ← zużycie tokenów per provider
    └── reports/     ← raporty z każdego runu
```

---

## Architektura

```
auto_coder/
├── cli.py           ← komendy: init / plan / run / status / doctor
├── config.py        ← odkrycie root projektu, ładowanie konfiguracji
├── orchestrator.py  ← główna pętla wykonania
├── manager.py       ← ManagerBrain: ocenia próby, persystuje historię
├── planner.py       ← ROADMAP.md → tasks.yaml (przez Claude API)
├── router.py        ← wybór providera, token counting, fallback
└── worker.py        ← spawowanie agenta (subprocess)
```

---

## Sprint 1 — Fundament i główna pętla ✅

**Cel:** Działający `auto-coder run` na prostym projekcie. Manager jeszcze bez API (fallback tekstowy), planner jeszcze nie istnieje (tasks.yaml piszesz ręcznie).

**Pliki do stworzenia:**
- `pyproject.toml` — instalacja pakietu
- `auto_coder/config.py` — odkrycie root, ładowanie config.yaml, brak hardkodowanych ścieżek
- `auto_coder/worker.py` — spawowanie agenta (cc/cch/ccg/codex) jako subprocess
- `auto_coder/orchestrator.py` — run_batch, run_one_task, run_tests, validate_changed_files
- `auto_coder/cli.py` — init, doctor, status, run
- `tests/test_orchestrator.py` — testy jednostkowe
- `tests/test_config.py` — testy konfiguracji
- `example/PROJECT.md` — przykładowy plik projektu
- `example/config.yaml` — przykładowy config

**Akceptacja sprintu:**
```bash
pip install -e .
auto-coder init          # tworzy .auto-coder/config.yaml
auto-coder doctor        # sprawdza środowisko
auto-coder status        # pokazuje stan tasków
python -m pytest tests/  # wszystkie testy zielone
```

---

## Sprint 2 — Manager z persystencją historii

**Cel:** ManagerBrain który pamięta całą historię rozmów między sesjami crona. Ocenia próby przez Anthropic API. Daje konkretny feedback agentowi.

**Problem który rozwiązuje:** Bez persystencji manager traci kontekst po każdym restarcie procesu (co godzinę przy cronie). Z persystencją widzi całą historię: "próba 1 zrobiła X, próba 2 zrobiła Y, teraz próba 3..."

**Pliki do stworzenia/modyfikacji:**
- `auto_coder/manager.py` — ManagerBrain z save/load messages do state.json
- `auto_coder/orchestrator.py` — integracja managera
- `tests/test_manager.py`

**Akceptacja sprintu:**
```bash
# Uruchom run — manager ocenia przez Claude API
# Zabij proces — uruchom ponownie
# Manager powinien pamiętać poprzednią ocenę
python -m pytest tests/test_manager.py
```

---

## Sprint 3 — Planner: ROADMAP → tasks.yaml

**Cel:** `auto-coder plan` czyta ROADMAP.md + PROJECT.md i generuje gotowy .auto-coder/tasks.yaml przez Claude API. Człowiek już nie musi pisać backlogu.

**Pliki do stworzenia/modyfikacji:**
- `auto_coder/planner.py` — Planner class, generate_backlog(), refresh_if_changed()
- `auto_coder/cli.py` — dodanie komendy `plan`
- `tests/test_planner.py`

**Akceptacja sprintu:**
```bash
# Stwórz ROADMAP.md z luźnym opisem projektu
auto-coder plan          # generuje .auto-coder/tasks.yaml
# Sprawdź czy tasks.yaml ma sensowne taski, test_commands, allowed_paths
auto-coder run           # uruchamia pierwszy task z wygenerowanego backlogu
```

---

## Sprint 4 — Provider router i quota tracking

**Cel:** System sam wie kiedy provider zbliża się do limitu i przełącza na inny. Token counting zamiast magicznego API.

**Pliki do stworzenia/modyfikacji:**
- `auto_coder/router.py` — ProviderRouter, token counter, fallback
- `auto_coder/orchestrator.py` — integracja routera
- `tests/test_router.py`

**Akceptacja sprintu:**
```bash
# Symuluj 80% usage na ccg → powinien przełączyć na cch
# Sprawdź .auto-coder/usage.json po kilku runach
python -m pytest tests/test_router.py
```

---

## Sprint 5 — Hardening i dokumentacja

**Cel:** System gotowy do użycia przez kogoś innego niż autor. Pełna dokumentacja, przykłady, migracja z agency-os.

**Co do zrobienia:**
- `README.md` — quickstart (5 minut do pierwszego runu)
- `example/` — kompletny przykładowy projekt
- Cron setup guide
- Obsługa błędów edge-case (brak ANTHROPIC_API_KEY, brak CC CLI, etc.)
- Migracja z `agency-os/scripts/nightly_ai_dev.py`
- `auto-coder migrate` — komenda importująca istniejący tasks.yaml z agency-os

---

## Parametry techniczne

| Co | Wartość |
|----|---------|
| Python | ≥ 3.11 |
| Jedyna zależność zewnętrzna MVP | `anthropic>=0.78`, `pyyaml>=6.0` |
| Manager backend (MVP) | Anthropic SDK (Claude) |
| Agenci (workers) | cc, cch, ccg, codex, qwen, gemini — CLI subprocess |
| Token limit threshold | 80% → fallback provider |
| Cron | co godzinę (`0 * * * *`) |
| Max prób na task / run | konfigurowalne (domyślnie 3) |
| Histora managera | persystowana w .auto-coder/state.json |

---

## Co NIE jest w zakresie MVP

- Równoległe agenty (2-3 developerów jednocześnie) — Sprint 6+
- Codex SDK backend dla managera — Sprint 6+
- Dashboard webowy — Sprint 7+
- Multi-projekt (jeden process, wiele repo) — Sprint 6+
- Z.ai quota REST API — nie istnieje, używamy token counting
