# Moduł wykonawczy (Execution Core)

## Przegląd

Moduł wykonawczy odpowiada za realizację zadań w pętli sprintów. Został wydzielony z głównego orchestratora w celu ułatwienia testowania i rozszerzalności.

## Komponenty

### Work Order
Jednostka wykonania — konkretna praca do zrobienia:
```python
@dataclass
class WorkOrder:
    task_id: str
    description: str
    acceptance_criteria: List[str]
    protected_paths: List[str]
    max_tokens: int
    timeout_seconds: int
```

### Sprint Loop
Cykl wykonawczy sprintu:
1. Pobierz work order z queue
2. Sprawdź kwotę i dostępność workera
3. Uruchom workera w git worktree
4. Poczekaj na raport końcowy
5. Zweryfikuj artefakty
6. Zwróć wynik (success/failure/retry)

### Worker Adapter
Abstrakcja nad providerem AI:
```python
class WorkerAdapter(ABC):
    @abstractmethod
    def execute(self, work_order: WorkOrder) -> ExecutionResult:
        pass
    
    @abstractmethod
    def get_quota(self) -> QuotaInfo:
        pass
    
    @abstractmethod
    def estimate_tokens(self, prompt: str) -> int:
        pass
```

## Przykład użycia

```python
from auto_coder.execution import WorkOrder, SprintLoop, ClaudeWorker

# Konfiguracja
worker = ClaudeWorker(api_key="...")
sprint = SprintLoop(worker=worker, max_retries=3)

# Utworzenie work order
work_order = WorkOrder(
    task_id="TASK-123",
    description="Dodaj endpoint /payments/refund",
    acceptance_criteria=[
        "Endpoint przyjmuje POST z payment_id i amount",
        "Zwraca 200 przy sukcesie, 400 przy błędzie",
        "Loguje wszystkie operacje do audit log"
    ],
    protected_paths=["/src/auth/", "/config/"],
    max_tokens=4000,
    timeout_seconds=600
)

# Wykonanie
result = sprint.execute(work_order)

if result.success:
    print(f"Zadanie wykonane: {result.commit_hash}")
elif result.retry:
    print(f"Potrzebna poprawka: {result.feedback}")
else:
    print(f"Zadanie zablokowane: {result.error}")
```

## Raport końcowy

Worker musi wygenerować raport w formacie:
```json
{
  "status": "success|failure|partial",
  "commit_hash": "abc123",
  "files_changed": ["src/api/payments.py", "tests/test_payments.py"],
  "tests_passed": true,
  "acceptance_criteria_met": [
    "Endpoint przyjmuje POST z payment_id i amount",
    "Zwraca 200 przy sukcesie, 400 przy błędzie"
  ],
  "acceptance_criteria_failed": [
    "Loguje wszystkie operacje do audit log"
  ],
  "feedback": "Brakuje logowania do audit log - dodaj w next iteration"
}
```

## Retry loop

Pętla naprawcza:
1. Pierwsza próba → failure z feedbackiem
2. Druga próba → worker dostaje feedback i poprawia
3. Trzecia próba → ostateczna weryfikacja
4. Po 3 nieudanych próbach → BLOCKED

```python
def execute_with_retry(self, work_order: WorkOrder) -> ExecutionResult:
    last_error = None
    
    for attempt in range(self.max_retries):
        result = self.worker.execute(work_order)
        
        if result.success:
            return result
        
        last_error = result.feedback
        work_order = self.enhance_with_feedback(work_order, result)
        
        # Backoff
        time.sleep(self.backoff_seconds * (2 ** attempt))
    
    return ExecutionResult(
        success=False,
        retry=False,
        error=f"Max retries exceeded. Last feedback: {last_error}"
    )
```

## Izolacja (git worktree)

Każde zadanie wykonuje się w osobnym worktree:
```bash
# Utworzenie worktree
git worktree add .worktrees/TASK-123 -b feature/TASK-123

# Wykonanie pracy
cd .worktrees/TASK-123
# ... worker działa tutaj ...

# Cleanup po zakończeniu
git worktree remove .worktrees/TASK-123
git branch -D feature/TASK-123
```

## Integracja z orchestratorem

Orchestrator łączy moduły:
```python
class Orchestrator:
    def __init__(self):
        self.planner = Planner()
        self.scheduler = Scheduler()
        self.worker = ClaudeWorker()
        self.sprint = SprintLoop(self.worker)
        self.state = StateManager()
    
    def tick(self):
        # Sprawdź czy są zadania do wykonania
        tasks = self.planner.get_pending_tasks()
        
        for task in tasks:
            # Sprawdź kwotę
            if not self.worker.has_quota():
                self.scheduler.pause(task)
                continue
            
            # Utwórz work order
            work_order = self.planner.create_work_order(task)
            
            # Wykonaj
            result = self.sprint.execute(work_order)
            
            # Zaktualizuj stan
            self.state.update(task.id, result)
```
