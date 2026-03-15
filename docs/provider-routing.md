# Routing providerów i sondy kwotów

## Przegląd

System automatycznie wykrywa dostępność providerów i routuje zadania do tych z dostępnymi kwotami.

## Sondy kwotów

Sondy sprawdzają dostępność przed wysłaniem zadania:

```python
# auto_coder/probes/quota.py
def probe_anthropic():
    """Sprawdź dostępność Anthropic API i kwotę."""
    ...

def probe_codex():
    """Sprawdź dostępność Codex CLI i kwotę."""
    ...
```

## Routing

Router wybiera providera na podstawie:

1. Dostępności (sonda)
2. Dostępnej kwoty
3. Priorytetu taska

```python
# auto_coder/planner/routing.py
def route_task(task):
    # 1. Uruchom sondy
    # 2. Filtruj niedostępnych
    # 3. Wybierz z największą kwotą
    # 4. Zwróć providera
```

## Komenda doctor

`auto-coder doctor` wyświetla:

```
Provider Status:
  anthropic: AVAILABLE (quota: 85%)
  codex:     AVAILABLE (quota: 92%)
  qwen:      UNAVAILABLE (rate limited)
```

## Konfiguracja

W `.auto-coder/config.yaml`:

```yaml
providers:
  - name: anthropic
    enabled: true
    priority: 1
  - name: codex
    enabled: true
    priority: 2
  - name: qwen
    enabled: false
```
