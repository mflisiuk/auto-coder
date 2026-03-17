# auto-coder

> Autonomiczny manager kodowania: otrzymuje brief projektu, generuje zadania, uruchamia AI workerów w izolowanych git worktrees, recenzuje wyniki, commituje, pushuje i otwiera PR-y — bez ręcznej interwencji.

## Co to robi

`auto-coder` to Pythonowy workflow engine dla zespołów chcących automatyzować dostarczanie feature'ów. Czyta dokumentację produktu (`ROADMAP.md`, `PROJECT.md`), generuje backlog przez AI managera, uruchamia workerów w izolowanych środowiskach, recenzuje wyniki i merge'uje do main.

**Kluczowe właściwości:**
- Domyślnie używa **Claude Code subscription** (manager: `cc`, worker: `ccg`) — nie wymaga API key
- Jedna instalacja działa dla dowolnej liczby repozytoriów
- Błędy kwotowe (429) nie są zaliczane jako failure — system czeka na reset kwoty
- `PROGRESS.md` i `work_progress.md` aktualizowane po każdym ticku — zawsze widoczny na GitHub
- Cron co 20 min to rekomendowany model deploymentu (bez persistent daemon)

## Szybki start

```bash
# 1. Instalacja globalna
git clone https://github.com/mflisiuk/auto-coder && cd auto-coder
pip install -e .

# 2. Inicjalizacja w repozytorium
cd /path/to/your-repo
auto-coder init

# 3. Sprawdź czy działa
auto-coder doctor --probe-live

# 4. Wygeneruj backlog
auto-coder plan

# 5. Uruchom (najpierw dry-run)
auto-coder run --dry-run
auto-coder run --live
```

## Funkcjonalności

- **AI Manager** — generuje zadania z briefu (`cc`, `claude`, `anthropic`, `codex`)
- **AI Workers** — wykonują zadania w izolowanych worktrees (`ccg`, `cc`, `cch`, `gemini`, `qwen`, `codex`)
- **Fallback Chain** — automatyczne przełączanie przy błędach kwotowych: `ccg` → `cc` → `cch` → `gemini` → `qwen` → `codex`
- **Auto PR/merge** — automatyczne otwieranie PR i merge po przejściu testów (domyślnie włączone)
- **Progress tracking** — `PROGRESS.md` i `work_progress.md` z emoji statusami
- **Repair tasks** — automatyczne zadania naprawcze gdy baseline testy nie przejdą

## Dokumentacja

- [Instalacja i konfiguracja](docs/setup.md)
- [Jak używać](docs/usage.md)
- [Architektura](docs/architecture.md)
- [CC-Manager Bridge](docs/cc-manager-bridge-spec.md)
- [Provider routing](docs/provider-routing.md)
- [Operator runbook](docs/operator-runbook.md)
- [Typowe problemy](docs/common-pitfalls.md)

## Changelog

[Zobacz CHANGELOG.md](CHANGELOG.md)
