# Specyfikacja: cc-manager bridge

## Cel

Dodanie `manager_backend: cc` do auto-codera, tak żeby Claude Code CLI
(`claude`) mógł pełnić rolę managera — analogicznie do istniejącego
`manager_backend: codex`.

Użytkownik jest już zalogowany do Claude Code przez subskrypcję Max (OAuth).
Nie potrzebuje API key. Implementacja jest wzorowana 1:1 na istniejącym
codex bridge — zmienia się tylko sposób wywołania CLI.

---

## Kontekst — jak działa codex bridge (wzorzec do skopiowania)

Obecna architektura dla `manager_backend: codex`:

```
orchestrator.py
  → _resolve_manager_backend()
    → CodexManagerBridge (auto_coder/managers/codex_bridge.py)
      → _run_bridge_action()
        → subprocess: node bridges/codex-manager/src/index.mjs <action> <payload.json>
          → spawn("codex", ["exec", "--json", "-", ...])
          → parsuje NDJSON z stdout
          → zwraca JSON do Python
```

Dla `cc` schemat jest identyczny — zmienia się tylko wywołanie CLI w bridge Node.js.

---

## Zmiany do wprowadzenia

### 1. `bridges/cc-manager/src/index.mjs` — NOWY PLIK

Kopia `bridges/codex-manager/src/index.mjs` z jedną zmianą: funkcja `runCc()`
zamiast `runCodex()`.

**Wywołanie CLI:**
```javascript
// codex (obecne):
spawn("codex", ["exec", "--json", "-", "--ephemeral", "--skip-git-repo-check",
                "-s", "read-only", "--output-schema", schemaPath,
                "-c", `model_reasoning_effort="${reasoningEffort}"`, ...modelArgs])

// cc (nowe):
spawn("claude", ["-p", prompt,
                 "--output-format", "json",
                 "--tools", "",
                 "--permission-mode", "bypassPermissions",
                 "--no-session-persistence",
                 ...modelArgs])
```

**Kluczowe flagi `claude`:**

| Flaga | Wartość | Powód |
|---|---|---|
| `-p` | `<prompt>` | tryb nieinteraktywny (print mode) |
| `--output-format` | `json` | ustrukturyzowany wynik do parsowania |
| `--tools` | `""` | manager tylko planuje, nie edytuje plików |
| `--permission-mode` | `bypassPermissions` | brak promptów "czy możesz to zrobić?" |
| `--no-session-persistence` | (flag) | każde wywołanie jest niezależne |
| `--model` | `claude-opus-4-6` | opcjonalne, z payload.model |

**Format wyjścia `claude --output-format json`:**

Claude Code w `--output-format json` zwraca jeden obiekt JSON na stdout:
```json
{
  "type": "result",
  "subtype": "success",
  "result": "<tekst odpowiedzi modelu>",
  "session_id": "...",
  "is_error": false
}
```

Tekst odpowiedzi (`result`) zawiera JSON wygenerowany przez model.
Bridge musi go sparsować jako `JSON.parse(parsed.result)` — analogicznie
do tego jak codex bridge parsuje `event.item.text`.

**JSON Schema dla structured output:**

`claude` nie ma flagi `--output-schema` jak codex. Zamiast tego schema
wstrzyknąć do system promptu:

```javascript
const systemPrompt = `You are the manager backend for auto-coder.
Return ONLY valid JSON matching this schema, no markdown, no explanation:
${JSON.stringify(schema, null, 2)}`;

spawn("claude", ["-p", prompt,
                 "--system-prompt", systemPrompt,
                 "--output-format", "json",
                 "--tools", "",
                 "--permission-mode", "bypassPermissions",
                 "--no-session-persistence"])
```

**Walidacja wyjścia** (taka sama jak w codex bridge):
```javascript
const missingFields = validateRequiredFields(parsedJson, schema);
if (missingFields.length > 0) {
  throw new Error(`cc bridge missing fields: ${missingFields.join(", ")}`);
}
```

**Obsługa `CLAUDECODE` env var:**

Claude Code nie pozwala uruchamiać się wewnątrz innej sesji Claude Code
(ustawia env var `CLAUDECODE`). Bridge musi ją usunąć przed spawn:

```javascript
const env = { ...process.env };
delete env.CLAUDECODE;

const child = spawn("claude", args, {
  cwd: payload.cwd || process.cwd(),
  stdio: ["pipe", "pipe", "pipe"],
  env,   // ← bez CLAUDECODE
});
```

**Plik `bridges/cc-manager/package.json`:**
```json
{
  "name": "cc-manager",
  "type": "module",
  "version": "1.0.0"
}
```

---

### 2. `auto_coder/managers/cc_bridge.py` — NOWY PLIK

Kopia `auto_coder/managers/codex_bridge.py` z trzema zmianami:

```python
# a) Nazwa klasy
class CcManagerBridge(ManagerBackend):

# b) name()
@classmethod
def name(cls) -> str:
    return "cc"

# c) is_available()
@classmethod
def is_available(cls) -> bool:
    return shutil.which("claude") is not None

# d) _bridge_path()
@classmethod
def _bridge_path(cls, config: dict[str, Any]) -> Path:
    return Path(
        config.get("cc_bridge_path")
        or (Path(__file__).resolve().parents[2] / "bridges" / "cc-manager" / "src" / "index.mjs")
    )

# e) probe_live() — zmień "codex" na "cc" w asercji
result = dict(response.get("result") or {})
if result.get("status") != "ok":
    raise RuntimeError(f"cc probe returned unexpected payload: {result}")
```

Wszystkie metody (`create_work_order`, `review_attempt`, `load_thread`,
`save_thread`, `_call_bridge`, `_run_bridge_action`) są identyczne jak
w `CodexManagerBridge` — nie zmieniać logiki, tylko zmienić wywołania
`_bridge_path` i `name()`.

---

### 3. `auto_coder/orchestrator.py` — 2 linie

```python
# Dodaj import (obok istniejących):
from auto_coder.managers.cc_bridge import CcManagerBridge

# Dodaj do słownika w _resolve_manager_backend():
MANAGER_BACKENDS = {
    "anthropic": AnthropicManagerBackend,
    "codex": CodexManagerBridge,
    "cc": CcManagerBridge,       # ← nowy wpis
    "claude": CcManagerBridge,   # ← alias (claude = cc)
}
```

---

### 4. `auto_coder/planner.py` — 2 linie

```python
def backend_available(self) -> bool:
    backend = str(self.config.get("manager_backend", "anthropic")).strip().lower()
    if backend == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if backend == "codex":
        return shutil.which("codex") is not None and shutil.which("node") is not None
    if backend in ("cc", "claude"):          # ← nowe
        return shutil.which("claude") is not None  # ← nowe
    return False
```

---

### 5. `auto_coder/config.py` — opcjonalne, ale rekomendowane

Dodać `"cc_bridge_path"` do domyślnego configu i dokumentacji:

```python
# W DEFAULT_CONFIG lub generowanym config.yaml:
# cc_bridge_path: ""   # leave empty to use built-in bridge
```

---

## Weryfikacja (jak sprawdzić że działa)

```bash
# 1. Upewnij się, że claude CLI jest dostępny
claude --version

# 2. Test bridge bezpośrednio
echo '{"cwd": "/tmp", "model": "claude-opus-4-6"}' > /tmp/probe.json
node bridges/cc-manager/src/index.mjs probe-live /tmp/probe.json
# oczekiwane: {"ok":true,"result":{"status":"ok","backend":"cc"},...}

# 3. auto-coder doctor
# W config.yaml projektu: manager_backend: cc
auto-coder doctor
# oczekiwane: OK  manager:cc cli

# 4. auto-coder plan
auto-coder plan
# oczekiwane: Planner backend: cc (timeout=180s) → wygenerowane taski
```

---

## Czego NIE zmieniać

- `auto_coder/managers/base.py` — interfejs się nie zmienia
- `auto_coder/managers/anthropic.py` — bez zmian
- `auto_coder/managers/codex_bridge.py` — bez zmian
- Istniejące testy — dodać nowe, nie modyfikować starych
- Format `tasks.yaml` — output managera musi spełniać ten sam schemat

---

## Testy do napisania

`tests/test_cc_manager_bridge.py`:

1. `test_is_available_when_claude_in_path` — mock `shutil.which("claude")` = `/usr/bin/claude`
2. `test_is_not_available_when_no_claude` — mock `shutil.which("claude")` = `None`
3. `test_probe_live_success` — mock subprocess, sprawdź że CLAUDECODE jest usunięte z env
4. `test_probe_live_bridge_not_found` — bridge path nie istnieje → `RuntimeError`
5. `test_create_work_order_returns_valid_structure` — mock subprocess zwraca poprawny JSON
6. `test_review_attempt_approve` — mock subprocess, verdict=approve

---

## Podsumowanie zmian

```
auto-coder/
├── bridges/
│   ├── codex-manager/          ← istniejący, nie dotykać
│   └── cc-manager/             ← NOWY
│       ├── package.json
│       └── src/
│           └── index.mjs       ← NOWY (~120 linii, kopia codex z innym spawn)
├── auto_coder/
│   └── managers/
│       ├── base.py             ← bez zmian
│       ├── anthropic.py        ← bez zmian
│       ├── codex_bridge.py     ← bez zmian
│       └── cc_bridge.py        ← NOWY (~140 linii, kopia codex z name="cc")
├── auto_coder/
│   ├── orchestrator.py         ← +1 import, +2 linie w słowniku
│   └── planner.py              ← +2 linie w backend_available()
└── tests/
    └── test_cc_manager_bridge.py  ← NOWY
```

**Szacowany nakład: 2-4 godziny.** Większość kodu to kopie istniejących plików.
Główna praca to obsługa formatu wyjścia `claude --output-format json`
i usunięcie `CLAUDECODE` z env przed spawnem.
