# Example Project Input Pack

Ten katalog pokazuje minimalny poziom szczegółu, przy którym `auto-coder plan` powinien przejść bez odrzucenia briefu.

## Co tu jest

- `ROADMAP.md`
  Produkt, kolejność modułów, scope i acceptance criteria.

- `PROJECT.md`
  Stack, struktura repo, konkretne komendy i policy ścieżek.

- `CONSTRAINTS.md`
  Twarde ograniczenia wykonawcze.

- `ARCHITECTURE_NOTES.md`
  Dodatkowe decyzje architektoniczne, które planner ma respektować.

## Jak tego używać

Potraktuj ten katalog jako wzorzec dla własnego repo.

Jeśli Twój brief jest mniej konkretny niż ten przykład, `auto-coder` powinien raczej odrzucić planning niż zgadywać.

## Co musi być jasne

Planner musi dać radę wyprowadzić z briefu:

- kolejność tasków
- `allowed_paths`
- `baseline_commands`
- `completion_commands`
- acceptance criteria per task

Jeśli tego nie da się wyciągnąć bez halucynowania wymagań, brief powinien zostać odrzucony komunikatem w stylu:

```text
brief niejasny - brakuje X, Y, Z
```

## Uwaga

To nie jest wygenerowany backlog i nie jest to przykładowe `.auto-coder/tasks.yaml`.

To jest dokładnie ten ludzki wsad wejściowy, który manager dostaje na start.
