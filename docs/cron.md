# Cron i tryb unattended

`auto-coder` nie działa jako daemon. Uruchamiasz go tickami przez zewnętrzny scheduler.

## Minimalny cron

Co godzinę:

```cron
0 * * * * cd /path/to/repo && /usr/bin/env auto-coder run --live >> .auto-coder/cron.log 2>&1
```

Co 15 minut:

```cron
*/15 * * * * cd /path/to/repo && /usr/bin/env auto-coder run --live >> .auto-coder/cron.log 2>&1
```

## Zalecany flow

Po zmianie briefu:

```cron
*/15 * * * * cd /path/to/repo && /usr/bin/env auto-coder plan >> .auto-coder/cron.log 2>&1
*/15 * * * * cd /path/to/repo && /usr/bin/env auto-coder run --live >> .auto-coder/cron.log 2>&1
```

W praktyce zwykle wystarczy samo `run`, bo i tak robi `refresh_if_changed()`.

## Kiedy wybrać jaki interwał

- `10-15 min`
  Najlepsze, jeśli chcesz sensownie wykorzystywać limity providerów.

- `60 min`
  Bezpieczny, prosty start.

- `>60 min`
  Tylko jeśli limity są bardzo ciasne albo repo jest uruchamiane okazjonalnie.

## Dobre praktyki

- zaczynaj od `dry_run: true`
- nie włączaj `auto_merge` na start
- trzymaj `auto_push: true` dopiero po przejściu stabilnych testów
- zapisuj output do stałego logu
- trzymaj repo na maszynie z działającym `git`, manager backendem i workerami CLI
