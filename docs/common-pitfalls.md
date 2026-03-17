# Typowe problemy i rozwiazania

**Uniwersalne lekcje wynikniete z wdrozen auto-codera**

Ten dokument opisuje najczestsze bledy ktore blokuja auto-codera. To sa "oczywiste" bledy ktere zjadaja godziny,
ale maja proste rozwiazania.

---

## 🔥 TOP 3 KRYTYCZNE BLEY DZISIEJSZEJ SESJI

### Bleedy #1: Cron ma ubogi PATH — `claude`/`ccg` niedostepne

**Problem:**
```
RuntimeError: Manager backends unavailable: cc (primary), anthropic (fallback)
```

**Przyczyna:**
- `claude` CLI jest zainstalowane w `~/.nvm/versions/node/v22.22.0/bin/`
- Cron nie laduje `~/.bashrc` ani `~/.nvm/nvm.sh` — PATH jest minimalistyczny
- Auto-coder nie moze znalesc `claude` — `is_available()` zwraca False

**Rozwiazanie (kod):**
Naprawione w auto-coder v1.0.5+:
- `cc_bridge.py`: `is_available()` sprawdza hardcoded sciezki
- `worker.py`: rozszerza PATH przed uruchomieniem workera
- `bridges/cc-manager/index.mjs`: rozszerza PATH przed spawnowaniem `claude`

**Rozwiazanie (cron):**
Uzyj pelnej sciezki w cronie:
```bash
# ZLE:
*/30 * * * * cd /repo && auto-coder run --live

# DOBRZE:
*/30 * * * * /usr/bin/flock -n /tmp/lock bash -c \
  "cd /repo && env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live"
```

---

### Bleedy #2: Zombie `runner.lock` po zabitym procesie

**Problem:**
```
RuntimeError: auto-coder already running: /path/to/.auto-coder/runner.lock
```

**Przyczyna:**
- Proces auto-coder zostal zabity (SIGKILL, timeout, restart VPS)
- Plik locka zostal z PID nieistniejacego procesu
- Kolejny run widzi lock i rezygnuje

**Rozwiazanie:**
Czyszc lock przed kazdym runem w cronie:
```bash
*/30 * * * * bash -c "cd /repo && rm -f .auto-coder/runner.lock && auto-coder run --live"
```

---

### Bleedy #3: Stale lease w `state.db` blokuje kolejne runy

**Problem:**
```
note: Task already leased by another run.
status: blocked
```

**Przyczyna:**
- Run zostal przerwany (SIGKILL) przed `finally` block
- Lease w `state.db` zostal z `expires_at` 2h w przyszlosci
- `recover_interrupted_runs()` markowal run jako `interrupted` ale NIE usuwal lease

**Rozwiazanie (kod):**
Naprawione w auto-coder v1.0.5+:
```python
# storage.py: recover_interrupted_runs()
if stale_run_ids:
    # Release leases held by interrupted runs
    conn.executemany(
        "DELETE FROM leases WHERE run_tick_id = ?",
        [(run_id,) for run_id in stale_run_ids],
    )
```

**Rozwiazanie (reczne):**
```bash
sqlite3 .auto-coder/state.db "DELETE FROM leases"
```

---

## KONFIGURACJA

### Bleedy #4: `allowed_paths` nie zawiera wszystkich potrzebnych plikow

**Problem:**
```
Policy violations:
  - outside_allowed:gacli/errors.py
status: waiting_for_retry
```

**Przyczyna:**
- Agent potrzebuje zmodyfikowac plik ktory nie jest w `allowed_paths` zadania
- Np. task `m1-auth` potrzebuje dodac `AuthError` do `gacli/errors.py`
- Manager (AI) czasem wybiera zbyt waskie `allowed_paths` w work order

**Rozwiazanie:**
Po `auto-coder plan` sprawdz `tasks.yaml` i rozszerz `allowed_paths` jesli plik jest wspolny:
```yaml
- id: m1-auth
  allowed_paths:
    - gacli/auth.py
    - gacli/errors.py    # DODANE — wspolny plik
    - tests/test_auth.py
```

---

### Bleedy #5: Manager/Worker wybieraja zly backend

**Problem:**
Worker to `cc` zamiast `ccg`, manager to `anthropic` zamiast `cc`.

**Rozwiazanie:**
```yaml
# .auto-coder/config.yaml
manager_backend: cc
default_worker: ccg
fallback_worker: cc
```

---

## Z INNYCH DNI

### Bleedy #6: Komendy w `PROJECT.md` uzywaja `python` zamiast `python3`

**Problem:**
```
bash: python: command not found
```

**Rozwiazanie:**
Zawsze uzywaj `python3` w `PROJECT.md`:
```yaml
baseline_commands:
  - python3.12 -m pytest tests/ -q
```

---

### Bleedy #7: API key w wrong env var

**Problem:**
```bash
ANTHROPIC_AUTH_TOKEN=sk-ant-...  # ❌
```
Ale auto-coder szuka `ANTHROPIC_API_KEY`.

**Rozwiazanie:**
Uzywaj `cc` backend (subskrypcja Claude Max) lub ustaw poprawna nazwe zmiennej.

---

## CHECKLIST PRZED PIERWSZYM RUNEM

- [ ] `PROJECT.md` ma `python3` nie `python`
- [ ] `ROADMAP.md`, `PROJECT.md`, `CONSTRAINTS.md`, `PLANNING_HINTS.md`, `ARCHITECTURE_NOTES.md` istnieja
- [ ] Po `auto-coder plan` sprawdz `tasks.yaml` — czy `allowed_paths` sa poprawne
- [ ] `auto-coder doctor` bez bledow
- [ ] `auto-coder doctor --probe-live` sukces (test managera)
- [ ] Git remote ma uprawnienia do push (SSH key lub token)
- [ ] Cron ma pelna sciezke do `auto-coder`

---

## EMERGENCY RESET

```bash
# Stop
pkill -f auto-coder

# Clean locks
rm -f .auto-coder/runner.lock .auto-coder/cron.lock

# Reset state
sqlite3 .auto-coder/state.db "DELETE FROM leases"
sqlite3 .auto-coder/state.db "UPDATE run_ticks SET status='interrupted' WHERE status='running'"

# Restart
env -u CLAUDECODE auto-coder run --live
```

---

**Ostatnia aktualizacja:** 2026-03-17 (rzeczywiste bledy z produkcji)
