# CC-Manager Bridge

## Przegląd

CC-Manager Bridge to moduł integrujący **Claude Code** jako backend menedżera zadań w auto-coder. Umożliwia wykorzystanie Claude Code do generowania backlogu zadań na podstawie briefu projektu oraz zarządzania cyklem życia zadań.

## Dlaczego CC-Manager?

- **Darmowy tier** — Claude Code oferuje darmowy dostęp z limitami
- **Lepszy kontekst** — Claude Code ma dostęp do struktury repozytorium
- **Elastyczność** — możliwość przełączania między managerami (anthropic/codex/cc)

## Architektura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  auto-coder     │────▶│  cc-manager      │────▶│  Claude Code    │
│  (orchestrator) │     │  (bridge)        │     │  (API)          │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Komponenty

1. **Bridge Layer** — tłumaczy kontrakty auto-coder na komendy Claude Code
2. **Stdin Handler** — zamyka stdin aby zapobiec zawieszaniu procesu
3. **Output Parser** — parsuje output Claude Code do struktury zadań

## Konfiguracja

W `.auto-coder/config.yaml`:

```yaml
# Ustaw cc-manager jako domyślny backend
manager_backend: cc

# Opcjonalnie: fallback do innego providera
fallback_manager: anthropic

# Worker settings
default_worker: cc      # Claude Code jako worker
fallback_worker: cch    # Claude Code paid jako fallback
```

## Tryby pracy

### CC (Claude Code - free)
Darmowy tier z limitami kwot. Przy 429 system czeka w `waiting_for_quota`.

### CCH (Claude Code - paid)
Płatny tier z wyższymi limitami, używany jako fallback.

## Fallback Chain

Gdy domyślny worker zwróci błąd kwotowy (429), auto-coder automatycznie przechodzi przez łańcuch:

```
cc → cch → gemini → qwen → codex
```

Każdy provider jest sprawdzany przed użyciem przez `doctor --probe-live`.

## Przykłady użycia

### Sprawdzenie dostępności providerów
```bash
auto-coder doctor --probe-live
```

### Generowanie zadań z cc-manager
```bash
# Upewnij się że ANTHROPIC_API_KEY jest ustawiony
export ANTHROPIC_API_KEY=sk-ant-...

# Wygeneruj backlog
auto-cader plan

# Uruchom z cc-manager
auto-coder run --manager=cc
```

## Rozwiązywanie problemów

### Zawieszanie się procesu
**Problem:** Proces Claude Code wisi po zakończeniu zadania.

**Przyczyna:** Otwarty stdin blokuje zakończenie procesu potomnego.

**Rozwiązanie:** Mostek cc-manager automatycznie zamyka stdin przed uruchomieniem Claude Code. Jeśli problem występuje, sprawdź:
```bash
# Włącz debug logging
auto-coder run --verbose
```

### Błędy kwotowe (429)
**Problem:** Claude Code zwraca 429 Too Many Requests.

**Rozwiązanie:**
1. System automatycznie czeka `quota_cooldown_hours` (domyślnie 4h)
2. Task przechodzi w stan `waiting_for_quota`
3. Po ochłonięciu task jest automatycznie wznawiany

### Brak odpowiedzi API
```bash
# Sprawdź health check
auto-coder doctor --probe-live

# Sprawdź logi
tail -f ~/.auto-coder/logs/manager.log
```

## Wymagania

- Python 3.8+
- Git
- Dostęp do Claude Code API (ANTHROPIC_API_KEY)
- Opcjonalnie: `gh` CLI do automatycznych PR

## Zobacz też

- [Provider Routing](provider-routing.md) — szczegółowy routing providerów
- [Setup](setup.md) — instalacja i konfiguracja
- [Common Pitfalls](common-pitfalls.md) — typowe problemy
