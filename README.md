# auto-coder
> Autonomiczny system dostarczania oprogramowania, który zamienia roadmapę w zadania i wykonuje je bez nadzoru.

## Co to robi
`auto-coder` to system, który przyjmuje dokumentację produktu (ROADMAP.md, PROJECT.md) i automatycznie generuje zadania, wybiera wykonawców, uruchamia pracę w izolowanym środowisku, recenzuje wyniki i commituje gotową pracę. Rozwiązuje problem ręcznego tłumaczenia wymagań na kod — dla zespołów chcących automatyzować dostarczanie feature'ów.

## Szybki start
```bash
git clone https://github.com/auto-coder/auto-coder.git
cd auto-coder
pip install -r requirements.txt
cp .env.example .env
python -m auto_coder.manager --tick-interval 15
```

## Funkcjonalności
- **Planowanie** — automatyczne generowanie zadań z ROADMAP.md i PROJECT.md
- **Walidacja briefów** — odrzucanie niejasnych wymagań z listą braków
- **Pętla wykonawcza** — cykliczne wzbudzanie managera co N minut
- **Izolacja** — praca w git worktree dla każdego zadania
- **Recenzja** — automatyczna weryfikacja artefaktów przed commit
- **Retry z feedbackiem** — pętle naprawcze aż do sukcesu lub blokady
- [Architektura systemu](ARCHITECTURE.md)

## Dokumentacja
- [Instalacja i konfiguracja](docs/setup.md)
- [Jak używać](docs/usage.md)
- [Architektura](docs/architecture.md)
- [Moduł wykonawczy](docs/execution.md)
- [Walidacja briefów](docs/brief-validation.md)

## Changelog
[Zobacz CHANGELOG.md](CHANGELOG.md)
