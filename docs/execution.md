# Moduł wykonawczy

## Przegląd
Moduł wykonawczy odpowiada za realizację zadań w izolowanym środowisku.

## Komponenty

### Core Executor
```python
from auto_coder.execution.core import CoreExecutor

executor = CoreExecutor(config)
result = executor.execute(task)
```

### Sprint Handler
Obsługuje cykle sprintów:
- Sprint 1: Implementacja podstawowa
- Sprint 2: Poprawki i rozszerzenia

### Reviewer
Automatyczna recenzja artefaktów:
- Sprawdza kompletność
- Weryfikuje jakość kodu
- Zatwierdza lub odrzuca

## Użycie
```bash
python -m auto_coder.execution --task TASK_ID
```
