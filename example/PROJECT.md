# Kontekst projektu

## Struktura repo

```
src/                  główny kod
  nbp.py              klient NBP API
  cache.py            SQLite cache
  convert.py          CLI entry point
tests/
  test_nbp.py
  test_cache.py
  test_convert.py
data/                 dane lokalne (nie commitować)
```

## Jak uruchomić

```bash
python3 src/convert.py 100 USD PLN
```

## Jak testować

```bash
python3 -m unittest discover tests/
```

## Zakazane ścieżki

- `config.py`
- `secrets/`
- `.env`

## Tech stack

- Python 3.11
- SQLite (stdlib)
- urllib (stdlib)
- unittest (stdlib)
