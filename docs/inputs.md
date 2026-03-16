# Input Pack

`auto-coder` działa dobrze tylko wtedy, gdy wejście jest wystarczająco konkretne.

## Wymagane pliki

- `ROADMAP.md`
- `PROJECT.md`

## Silnie zalecane

- `PLANNING_HINTS.md`
- `CONSTRAINTS.md`
- `ARCHITECTURE_NOTES.md`

## Co musi być dostarczone

### `ROADMAP.md`

Musi odpowiedzieć na pytania:

- co budujemy
- dla kogo
- co wchodzi do pierwszych milestone'ów
- co jest poza zakresem
- po czym poznać, że milestone jest dowieziony

### `PROJECT.md`

Musi odpowiedzieć na pytania:

- jaki jest stack i runtime
- jak wygląda repo
- jakie komendy są deterministyczne
- gdzie wolno edytować
- czego nie wolno ruszać
- jakie są założenia środowiskowe

### `CONSTRAINTS.md`

Najlepiej umieścić tu:

- dependency policy
- security boundaries
- forbidden changes
- test expectations

### `PLANNING_HINTS.md`

Tu warto dopisać rzeczy, których planner nie powinien zgadywać:

- istniejące nazewnictwo komend
- preferowane flagi i konwencje paginacji
- naming conventions dla modułów, endpointów i jobów
- wzorce, które repo już stosuje i które należy utrzymać

## Kiedy planner ma odrzucać brief

Planner powinien odrzucić planning, jeśli:

- brakuje pliku obowiązkowego
- brakuje sekcji obowiązkowej
- nie ma konkretnej komendy testowej
- nie ma policy ścieżek
- brief jest sprzeczny albo pełen `todo` / `tbd`

## Referencja

Najlepszym wzorcem jest:

- `INPUT_SPEC.md`
- `example-project/`
