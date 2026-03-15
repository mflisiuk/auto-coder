# Walidacja briefów

`auto-coder` planuje tylko wtedy, gdy brief jest wystarczająco konkretny do wygenerowania mierzalnych tasków.

Jeśli brief jest zbyt luźny, planning jest odrzucany komunikatem w stylu:

```text
brief niejasny - missing sections: ROADMAP.md::Acceptance Criteria, PROJECT.md::Commands
```

## Co jest wymagane

### `ROADMAP.md`

Wymagane sekcje:

- `Project Goal`
- `Target User`
- `Ordered Milestones`
- `In Scope`
- `Out of Scope`
- `Acceptance Criteria`

### `PROJECT.md`

Wymagane sekcje:

- `Tech Stack`
- `Repo Structure`
- `Commands`
- `Editable Paths`
- `Protected Paths`
- `Environment Assumptions`

## Co jeszcze sprawdza walidator

- czy `PROJECT.md::Commands` zawiera deterministyczną komendę testową
- czy polityka ścieżek ma konkretne wpisy
- czy w briefie nie ma markerów typu `tbd`, `todo`, `later`, `maybe`

## Jak to uruchomić

Najprościej przez:

```bash
auto-coder doctor
auto-coder plan
```

Obie komendy pokażą błąd walidacji, jeśli brief nie przechodzi.

## Typowe powody odrzucenia

- brak `ROADMAP.md`
- brak `PROJECT.md`
- brak sekcji `Commands`
- brak sekcji `Editable Paths` / `Protected Paths`
- brak acceptance criteria
- brak deterministycznej komendy testowej
- niejednoznaczne markery w stylu `todo`, `somehow`, `maybe`

## Jak powinien wyglądać dobry brief

Dobry brief pozwala plannerowi bez zgadywania wyprowadzić:

- kolejność prac
- zakres ścieżek do zmian
- komendy bazowe i końcowe
- acceptance criteria per task

Referencja:

- `INPUT_SPEC.md`
- `example-project/`
