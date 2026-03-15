# Pre-Mortem

Ten dokument zakłada, że system ma działać autonomicznie i zadaje pytanie: "jak to może się zepsuć zanim się zepsuje?".

## Założenie bazowe

`auto-coder` nie będzie bulletproof tylko dlatego, że ma LLM managera. Będzie bulletproof tylko wtedy, gdy:

- wejście jest ostre
- runtime jest deterministyczny
- stan jest trwały
- rollback i recovery są nudne, przewidywalne i częste

## 1. Brief jest za słaby

### Objaw

- planner generuje słabe taski
- taski są zbyt duże albo zbyt ogólne
- manager retryuje bez końca

### Dlaczego to się dzieje

- `ROADMAP.md` jest marketingowy zamiast wykonawczego
- `PROJECT.md` nie ma komend i policy ścieżek

### Zabezpieczenie

- trzymaj się `INPUT_SPEC.md`
- nie omijaj `doctor` i `plan`
- używaj `tasks.local.yaml` do ręcznych override'ów

## 2. Testy są za słabe

### Objaw

- manager zatwierdza złą zmianę
- kod "przechodzi", ale aplikacja jest popsuta

### Dlaczego to się dzieje

- `completion_commands` nie pokrywają ryzyka
- repo ma mało testów integracyjnych

### Zabezpieczenie

- dodaj smoke tests do krytycznych flow
- używaj zarówno `baseline_commands`, jak i `completion_commands`
- nie włączaj `auto_merge` dopóki test suite nie jest wiarygodny

## 3. Provider wchodzi w limit

### Objaw

- worker zwraca `429`
- taski stoją w `waiting_for_quota`

### Dlaczego to się dzieje

- taski są za duże
- ticki są za częste względem limitów
- brak fallbacków

### Zabezpieczenie

- tnij taski na mniejsze work orders
- ustaw fallback workers
- obserwuj usage i `retry_after`
- trzymaj `cch` albo innego "dużego" workera jako safety net

## 4. Repo nie ma poprawnej bazy do worktree

### Objaw

- `runner_failed`
- błąd typu `invalid reference`

### Dlaczego to się dzieje

- repo nie ma jeszcze commita
- `worktree_base_ref` wskazuje w zły branch

### Zabezpieczenie

- wymagaj co najmniej jednego commita
- uruchamiaj `auto-coder doctor`
- nie zakładaj ślepo `origin/main` przy lokalnych repo

## 5. Worker nic nie zostawia albo kłamie w raporcie

### Objaw

- brak `AGENT_REPORT.json`
- report mówi "done", a testy nie przechodzą

### Dlaczego to się dzieje

- worker nie respektuje kontraktu
- report nie jest jedyną bramką

### Zabezpieczenie

- traktuj report jako artefakt pomocniczy, nie źródło prawdy
- wymagaj policy checks i `completion_commands`
- retryuj brak raportu tylko ograniczoną liczbę razy

## 6. System zapętla się w retry

### Objaw

- ten sam task wraca stale do `waiting_for_retry`

### Dlaczego to się dzieje

- powtarza się ten sam typ błędu
- feedback managera nie zmienia problemu

### Zabezpieczenie

- `failure_block_threshold`
- podpisy awarii
- przejście do `blocked` po powtarzalnej porażce

## 7. Cron odpala się równolegle

### Objaw

- dwa procesy próbują ruszyć ten sam task
- dziwne lease conflicts

### Dlaczego to się dzieje

- ticki nachodzą na siebie
- poprzedni run jeszcze trwa

### Zabezpieczenie

- lock file
- leases w SQLite
- krótki, przewidywalny tick zamiast długiego demona

## 8. Maszyna padnie w trakcie runu

### Objaw

- task zostaje w `running`
- worktree zostaje na dysku

### Dlaczego to się dzieje

- kill procesu
- reboot maszyny
- crash CLI workera

### Zabezpieczenie

- recovery po starcie
- wygaszanie stale lease'ów
- cleanup worktrees

## 9. Agent dotknie nie tego, co trzeba

### Objaw

- zmiany poza zakresem
- dotknięte chronione ścieżki

### Dlaczego to się dzieje

- prompt jest za szeroki
- task ma zbyt szerokie `allowed_paths`

### Zabezpieczenie

- wąskie `allowed_paths`
- jawne `protected_paths`
- deterministic path policy przed review managera

## 10. Sekrety albo środowisko wyciekną do workera

### Objaw

- agent czyta rzeczy, których nie powinien
- w commitach lądują sekrety

### Dlaczego to się dzieje

- uruchamiasz system na zbyt uprzywilejowanej maszynie
- worker ma zbyt szeroki dostęp

### Zabezpieczenie

- osobny user/system account dla auto-coder
- ograniczone env vars
- protected paths dla `.env`, `secrets/`, `infra/`
- nie używaj `danger-full-access` poza kontrolowanym środowiskiem

## 11. Zewnętrzne zależności są niestabilne

### Objaw

- flaky tests
- plan albo review działa raz tak, raz tak

### Dlaczego to się dzieje

- testy zależą od sieci
- repo wymaga usług, których nie ma lokalnie

### Zabezpieczenie

- w `PROJECT.md` wpisz environment assumptions
- stubuj albo mockuj integracje
- do `completion_commands` dawaj tylko deterministyczne checki

## 12. Dokumentacja operatora i runtime się rozjadą

### Objaw

- instrukcja mówi jedno, CLI robi drugie

### Dlaczego to się dzieje

- docs nie są utrzymywane razem z kodem

### Zabezpieczenie

- trzymaj runbook w repo
- po każdej większej zmianie CLI aktualizuj docs i smoke testuj flow:
  - `doctor`
  - `plan`
  - `run --dry-run`
  - `status`

## Rekomendacja końcowa

Jeśli chcesz system naprawdę "bulletproof", nie zaczynaj od pełnej autonomii na `main`.

Zacznij od:

1. `dry_run`
2. `run --live` z `auto_commit: true`, `auto_push: true`, `auto_merge: false`
3. osobnej gałęzi integracyjnej albo repo stagingowego
4. dopiero potem pełna automatyzacja na ważnym repo
