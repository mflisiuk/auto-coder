# Autonomous Auto-Coder Vision

## The Dream

**Auto-coder becomes a self-improving software development organism.**

Not just a task runner. Not just a repair system. An autonomous agent that:
- Understands goals, not just tasks
- Diagnoses its own failures
- Repairs its own configuration
- Learns from every attempt
- Improves its own prompts and strategies
- Eventually writes better code than we could

---

## Current State vs Autonomous State

| Capability | Current | Autonomous |
|------------|---------|------------|
| **Goal Understanding** | Follows tasks.yaml | Reads ROADMAP.md, infers next steps |
| **Task Generation** | Manual | Auto-generates from goals |
| **Failure Diagnosis** | Creates repair task | Classifies, learns, prevents |
| **Configuration Repair** | Manual edit | Auto-updates config.yaml |
| **Prompt Improvement** | Static | Evolves based on outcomes |
| **Knowledge Persistence** | None | Structured learning DB |
| **Self-Modification** | Dangerous | Safe with rollback |

---

## Four Levels of Autonomy

### Level 1: Reactive (Current)

```
User → tasks.yaml → Worker → Manager → Result
                          ↓
                    Failure? → Repair Task (wait for next run)
```

**Problems:**
- Repair tasks wait 30 minutes
- Same failures repeat across projects
- No learning across runs
- Manual config edits needed

### Level 2: Self-Healing

```
User → tasks.yaml → Worker → Manager → Result
                          ↓
                    Failure? → Classify → Auto-Fix → Retry
                          ↓
                    Unknown? → Capture → Human Review
```

**Improvements:**
- Known patterns auto-fixed
- Unknown patterns captured for review
- Learning database built

### Level 3: Self-Directing

```
User → ROADMAP.md → Planner → tasks.yaml → Worker → Manager → Result
                         ↑                           ↓
                         └─── Feedback Loop ──────────┘
```

**Improvements:**
- Reads ROADMAP.md, infers tasks
- Generates tasks.yaml automatically
- Prioritizes based on dependencies
- Updates ROADMAP.md with progress

### Level 4: Self-Improving

```
               ┌──────────────────────────────────────────┐
               │              AUTO-CODER BRAIN             │
               │                                          │
User → Goals → │  Planner → Tasks → Worker → Reviewer →  │ → Code
               │      ↑                              │    │
               │      └────── Learning Loop ─────────┘    │
               │                                          │
               │  • Analyzes own failures                 │
               │  • Rewrites own prompts                  │
               │  • Improves own strategies               │
               │  • Prunes ineffective approaches         │
               │                                          │
               └──────────────────────────────────────────┘
```

**Improvements:**
- Learns which prompts work best
- Discovers new patterns automatically
- Improves its own code
- Becomes more capable over time

---

## Core Components for Autonomy

### 1. Failure Classifier (The Doctor)

```python
class FailureClassifier:
    """
    Classifies failures into known patterns and suggests repairs.

    Pattern Types:
    - environment: python vs python3, missing deps
    - policy: files outside allowed_paths
    - syntax: YAML parse errors, invalid JSON
    - test: test failures, coverage gaps
    - logic: code doesn't do what was asked
    - unknown: new pattern to learn
    """

    KNOWN_PATTERNS = {
        "python_command_not_found": {
            "detect": lambda r: r.returncode == 127 and "python" in r.command,
            "category": "environment",
            "repair": "replace_python_with_python3",
            "prevention": "normalize_commands_in_config",
        },
        "coverage_outside_allowed": {
            "detect": lambda r: "outside_allowed:.coverage" in r.violations,
            "category": "policy",
            "repair": "add_coverage_to_protected",
            "prevention": "auto_protect_test_artifacts",
        },
        # ... more patterns
    }
```

### 2. Repair Executor (The Surgeon)

```python
class RepairExecutor:
    """
    Safely executes repairs with rollback capability.
    """

    def repair(self, failure: Failure, pattern: Pattern) -> RepairResult:
        # Create checkpoint
        checkpoint = self.checkpoint_manager.create()

        try:
            # Apply repair
            if pattern.repair == "replace_python_with_python3":
                self._fix_python_commands()
            elif pattern.repair == "add_coverage_to_protected":
                self._add_to_protected_paths([".coverage", "__pycache__/"])

            # Verify repair worked
            if self._verify_repair():
                return RepairResult(success=True)
            else:
                raise RepairFailedError()

        except Exception:
            # Rollback
            self.checkpoint_manager.restore(checkpoint)
            return RepairResult(success=False, needs_human=True)
```

### 3. Learning Database (The Memory)

```python
# SQLite schema for learning

CREATE TABLE failure_patterns (
    id TEXT PRIMARY KEY,
    signature TEXT UNIQUE,  -- e.g., "exit_127:python_command"
    category TEXT,          -- environment, policy, syntax, test, logic
    first_seen TEXT,
    last_seen TEXT,
    occurrence_count INTEGER,
    auto_repair_enabled BOOLEAN,
    repair_success_rate REAL
);

CREATE TABLE repair_attempts (
    id INTEGER PRIMARY KEY,
    pattern_id TEXT,
    task_id TEXT,
    repair_applied TEXT,
    success BOOLEAN,
    created_at TEXT,
    FOREIGN KEY (pattern_id) REFERENCES failure_patterns(id)
);

CREATE TABLE prompt_variants (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    prompt_text TEXT,
    success_count INTEGER,
    failure_count INTEGER,
    avg_attempts INTEGER,
    created_at TEXT
);
```

### 4. Prompt Evolver (The Teacher)

```python
class PromptEvolver:
    """
    Improves prompts based on outcomes.

    Process:
    1. Track prompt variants and their success rates
    2. When prompt fails repeatedly, generate variant
    3. A/B test variants
    4. Promote winners, retire losers
    """

    def evolve_prompt(self, task_type: str, current_prompt: str,
                      failures: list[Failure]) -> str:
        # Analyze what went wrong
        failure_modes = self._analyze_failures(failures)

        # Generate improvement suggestions
        improvements = self._suggest_improvements(failure_modes)

        # Create variant
        variant = self._create_variant(current_prompt, improvements)

        # Track for A/B testing
        self._track_variant(task_type, variant)

        return variant
```

### 5. Task Generator (The Planner)

```python
class TaskGenerator:
    """
    Generates tasks from high-level goals.

    Input: ROADMAP.md with milestones
    Output: tasks.yaml with concrete tasks
    """

    def generate_from_roadmap(self, roadmap: Roadmap) -> list[Task]:
        tasks = []

        for milestone in roadmap.milestones:
            # Check if milestone is complete
            if self._is_milestone_complete(milestone):
                continue

            # Find first incomplete acceptance criterion
            for criterion in milestone.acceptance_criteria:
                if not self._is_criterion_met(criterion):
                    # Generate task to satisfy criterion
                    task = self._generate_task(milestone, criterion)
                    tasks.append(task)
                    break  # One task per milestone per run

        return tasks
```

---

## Safety Model

### The Three Laws of Auto-Coder

1. **Preservation**: Never modify files outside allowed_paths
2. **Reversibility**: Every mutation has a checkpoint for rollback
3. **Transparency**: Every decision is logged with reasoning

### Autonomy Levels (Configurable)

```yaml
# config.yaml
autonomy:
  level: 2  # 1=reactive, 2=self-healing, 3=self-directing, 4=self-improving

  safety:
    max_auto_repair_attempts: 3
    require_human_approval_for:
      - modifying_auto_coder_config
      - deleting_files
      - production_deploys
    auto_rollback_on:
      - test_failures
      - policy_violations
      - syntax_errors
```

### The Quarantine Zone

When auto-coder encounters unknown failures:

1. **Capture** full context (command, output, files)
2. **Quarantine** the task (no more auto-attempts)
3. **Notify** human with structured report
4. **Wait** for human decision
5. **Learn** from human's fix

---

## Implementation Roadmap

### Phase 1: Self-Healing (2 weeks)

**Goal:** Auto-repair known failure patterns

- [ ] Implement FailureClassifier with 10 known patterns
- [ ] Add RepairExecutor with rollback
- [ ] Create learning database schema
- [ ] Add `--loop` to all cron jobs (DONE TODAY)

### Phase 2: Learning (2 weeks)

**Goal:** Capture and learn from failures

- [ ] Implement failure pattern discovery
- [ ] Add knowledge/failures/ capture
- [ ] Build failure pattern review UI
- [ ] Promote learned patterns to known patterns

### Phase 3: Self-Directing (4 weeks)

**Goal:** Generate tasks from ROADMAP.md

- [ ] Implement ROADMAP.md parser
- [ ] Add TaskGenerator
- [ ] Build acceptance criterion checker
- [ ] Create feedback loop to ROADMAP.md

### Phase 4: Self-Improving (6 weeks)

**Goal:** Improve prompts and strategies

- [ ] Implement PromptEvolver
- [ ] Add A/B testing framework
- [ ] Build prompt variant tracker
- [ ] Create strategy optimizer

---

## Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO-CODER AUTONOMY METRICS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Self-Healing Rate     ████████████████████░░░░  82%            │
│  (auto-repaired / total failures)                               │
│                                                                 │
│  Learning Rate         ████████████░░░░░░░░░░░░  45%            │
│  (new patterns captured / unknown failures)                     │
│                                                                 │
│  Task Success Rate     ██████████████████████░░  91%            │
│  (completed / attempted)                                        │
│                                                                 │
│  Human Interventions   ████████░░░░░░░░░░░░░░░░  2/day          │
│  (manual fixes required)                                        │
│                                                                 │
│  Prompt Improvement    ██████████████░░░░░░░░░░  34%            │
│  (better variants / total variants)                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Ultimate Vision

```
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    │                      AUTO-CODER                             │
    │                    (Autonomous Agent)                        │
    │                                                             │
    │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
    │  │ PLANNER │───▶│  DOER   │───▶│REVIEWER │───▶│LEARNER  │  │
    │  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘  │
    │       │              │              │              │        │
    │       └──────────────┴──────────────┴──────────────┘        │
    │                           │                                   │
    │                     FEEDBACK LOOP                            │
    │                           │                                   │
    │       ┌───────────────────┴───────────────────┐             │
    │       │                                       │             │
    │       ▼                                       ▼             │
    │  ┌─────────┐                           ┌─────────────┐      │
    │  │  ROADMAP │                           │   KNOWLEDGE  │      │
    │  │   (Goals)│                           │    (Lessons) │      │
    │  └─────────┘                           └─────────────┘      │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   CODE REPO     │
                    │  (Better Code)  │
                    └─────────────────┘
```

The auto-coder becomes a **learning organization** in software form - constantly improving, adapting, and delivering better results with less human intervention.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Auto-repair breaks things | Checkpoint + rollback on every repair |
| Learning captures bad patterns | Human review before promotion |
| Self-modification goes wrong | Cannot modify own core code |
| Endless retry loops | Max attempts + exponential backoff |
| Knowledge database corruption | Git-tracked, versioned |

---

## Conclusion

The path to autonomy is clear:

1. **Today**: Added `--loop` mode for continuous self-healing
2. **Next**: Implement FailureClassifier and RepairExecutor
3. **Then**: Add Learning Database and Prompt Evolver
4. **Finally**: Full self-directing, self-improving system

The key insight: **autonomy is not binary**. It's a spectrum from reactive → self-healing → self-directing → self-improving. We're moving up that spectrum incrementally, with safety at each step.

---

*Last updated: 2026-03-19*
