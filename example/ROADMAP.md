# Przykładowy projekt: kalkulator walutowy

## Co buduję

Prosta aplikacja CLI do przeliczania walut. Pobiera kursy z publicznego API NBP,
cache'uje lokalnie na 1 godzinę, przelicza kwoty między walutami.

## Stos techniczny

Python 3.11, tylko biblioteka standardowa (bez requests — używamy urllib).
SQLite do cachowania kursów. Testy unittest.

## Priorytety

1. Pobieranie kursów z NBP API
2. Cache SQLite (TTL 1h)
3. CLI: `convert.py 100 USD PLN`
4. Testy jednostkowe

## Ograniczenia

- Brak zewnętrznych zależności (tylko stdlib)
- Nie dotykamy pliku config.py (tam będą klucze)
- Testy tylko unittest, bez pytest
