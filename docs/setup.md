# Instalacja i konfiguracja

## Wymagania

- Python 3.10+
- Git 2.23+ (dla worktrees)
- Node.js 18+ (dla cc-manager bridge)
- `claude` CLI zainstalowane i zalogowane (`claude` lub `ccg`)
- Git remote skonfigurowany z uprawnieniami do push (SSH deploy key lub token)

## Instalacja globalna

```bash
git clone https://github.com/mflisiuk/auto-coder
cd auto-coder
pip install -e .
```

Weryfikacja:

```bash
which auto-coder          # powinno zwrocic ~/.local/bin/auto-coder
auto-coder --help
```

## Inicjalizacja w repozytorium

```bash
cd /path/to/your-repo
auto-coder init
```

Tworzy strukture `.auto-coder/`:

```
.auto-coder/
├── config.yaml      # konfiguracja
├── tasks.yaml       # backlog (generowany przez auto-coder plan)
├── state.db         # stan SQLite
└── reports/         # raporty z kazdego runu
```

## Wymagane pliki projektowe

Auto-coder czyta dokumentacje projektu zeby wygenerowac backlog. Musisz stworzyc:

| Plik | Co zawiera |
|------|-----------|
| `ROADMAP.md` | Cel projektu, milestony, kryteria akceptacji |
| `PROJECT.md` | Stack techniczny, struktura repo, komendy (install/test/lint) |
| `CONSTRAINTS.md` | Zakazane zmiany, granice bezpieczenstwa |
| `PLANNING_HINTS.md` | Konwencje nazewnictwa, wzorce, wskazowki dla agenta |
| `ARCHITECTURE_NOTES.md` | Decyzje architektoniczne, schematy JSON, kody wyjscia |

**Krytyczne:** Wszystkie komendy w `PROJECT.md` musza byc sprawdzone recznie przed pierwszym runem.
Jesli komenda failuje — wszystkie zadania wygenerowane na jej podstawie beda failowac.

## Konfiguracja (`.auto-coder/config.yaml`)

Domyslna konfiguracja dziala na subskrypcji Claude Max bez API key:

```yaml
# Manager (planuje i recenzuje zadania)
manager_backend: cc        # uzywa claude CLI — brak API key potrzebny
manager_model: ""          # domyslnie claude-opus-4-6

# Worker (pisze kod)
default_worker: ccg        # ccg = Claude Code z Google
fallback_worker: cc        # fallback na standardowy cc

# Git
auto_commit: true
auto_push: true
auto_pr: false             # wymaga gh CLI
auto_merge: true           # bezposredni merge do main (bez PR)
base_branch: main
```

Jesli uzywasz Anthropic API key:

```yaml
manager_backend: anthropic
manager_model: claude-opus-4-6
# + ustaw ANTHROPIC_API_KEY w srodowisku
```

## Generowanie backlogu

```bash
auto-coder plan
```

Generuje `tasks.yaml` na podstawie `ROADMAP.md` + `PROJECT.md`.

**Sprawdz po wygenerowaniu** — szczegolnie `allowed_paths` w kazdym zadaniu.
Agent moze modyfikowac TYLKO pliki wymienione w `allowed_paths`. Jesli brakuje pliku
(np. `gacli/errors.py`) — agent dostanie policy violation i task sie nie powiedzie.

## Weryfikacja

```bash
auto-coder doctor
auto-coder doctor --probe-live    # test live wywolania managera (wymaga sieci)
```

Oczekiwany wynik:

```
OK    git available
OK    worker:cc
OK    worker:ccg
OK    manager live probe succeeded
```

## Pierwsze uruchomienie

```bash
# Najpierw dry-run — sprawdz co by zrobil bez pisania kodu
auto-coder run --dry-run

# Live — pisze kod, commituje, pushuje
auto-coder run --live
```

## Cron (autonomiczny tryb)

Pelna, odporna na bleedy konfiguracja crona:

```bash
*/30 * * * * /usr/bin/flock -n /tmp/myrepo-autocoder.lock bash -c \
  "cd /path/to/your-repo && rm -f .auto-coder/runner.lock && \
   env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live" \
  >> /path/to/your-repo/.auto-coder/cron.log 2>&1
```

Kluczowe elementy:
- **Pelna sciezka** do `auto-coder` — cron ma ubogi PATH
- **`rm -f runner.lock`** — czysci zombie lock po zabitym procesie
- **`env -u CLAUDECODE`** — pozwala `claude`/`ccg` uruchomic sie wewnatrz crona
- **`flock`** — zapobiega rownoczesnemu uruchomieniu dwoch instancji

Szczegoly w [docs/cron.md](cron.md).

## Nastepne kroki

- [Jak uzywac](usage.md)
- [Typowe problemy i rozwiazania](common-pitfalls.md)
- [Cron i tryb autonomiczny](cron.md)
- [Operator runbook](operator-runbook.md)
