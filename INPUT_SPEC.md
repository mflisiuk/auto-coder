# auto-coder - Input Specification

## Purpose

This document defines the minimum input quality required for `auto-coder` to start planning and executing work safely.

If the input is below this bar, the system should reject it instead of guessing.

Expected rejection style:

- `brief niejasny - brakuje X, Y, Z`

## Required Files

The planner must refuse to start if any of these are missing:

- `ROADMAP.md`
- `PROJECT.md`

## Recommended Files

These are not mandatory for the first planning pass, but they materially improve quality:

- `CONSTRAINTS.md`
- `ARCHITECTURE_NOTES.md`
- `tasks.local.yaml`

## Required Structure

### ROADMAP.md

`ROADMAP.md` must define the product and the order of delivery.

Required sections:

- `Project Goal`
- `Target User`
- `Ordered Milestones` or `Modules`
- `In Scope`
- `Out of Scope`
- `Acceptance Criteria`

Minimum acceptable content:

- what the app does
- who it is for
- what gets built first, second, third
- what explicitly is not part of v1
- how to recognize that a milestone is done

Reject if:

- the roadmap is only aspirational, e.g. "build something modern and clean"
- milestones are missing ordering
- there is no out-of-scope section
- acceptance criteria are purely aesthetic or vague

### PROJECT.md

`PROJECT.md` must define the engineering environment and repo rules.

Required sections:

- `Tech Stack`
- `Repo Structure`
- `Commands`
- `Editable Paths`
- `Protected Paths`
- `Environment Assumptions`

Minimum acceptable content:

- runtime and language versions
- expected repo folders
- exact commands for test, run, lint, build if applicable
- which paths the agent is allowed to modify
- which paths are forbidden
- whether external services, env vars, or databases are needed

Reject if:

- commands are missing
- repo structure is absent
- there is no path policy
- required services or env vars are implied but not named

### CONSTRAINTS.md

Recommended, but in many repos this should effectively be treated as required.

Suggested sections:

- `Dependency Policy`
- `Testing Policy`
- `Forbidden Changes`
- `Security Boundaries`
- `Operational Boundaries`

### ARCHITECTURE_NOTES.md

Optional, but useful when multiple valid implementations exist.

Suggested sections:

- domain model notes
- required interfaces
- non-functional requirements
- known tradeoffs already decided by the human

## Minimum Quality Bar

The brief is considered acceptable only if the planner can derive:

- concrete backlog items
- execution order
- allowed file scope
- deterministic verification commands
- acceptance criteria per task

If any of the above cannot be derived safely, planning must stop.

## Reject Conditions

Reject the brief if any of these are true:

- missing required file
- missing required section
- no deterministic test or verification command
- no editable or protected path policy
- roadmap contains contradictory priorities
- architecture is undecided where that decision affects implementation
- commands refer to tools or services not described anywhere
- success criteria cannot be translated into testable tasks

## Rejection Output Contract

The planner should emit both human-readable and machine-readable rejection output.

Suggested JSON:

```json
{
  "status": "rejected",
  "summary": "brief niejasny - brakuje wymaganych informacji",
  "missing_files": [],
  "missing_sections": [],
  "ambiguous_points": [],
  "contradictions": [],
  "next_actions": []
}
```

Suggested human-readable output:

```text
brief niejasny - brakuje wymaganych informacji:
- PROJECT.md::Commands
- ROADMAP.md::Acceptance Criteria
- brak editable/protected paths
```

## What Good Input Looks Like

A good brief answers:

- what exactly is being built
- what the first release includes
- how the repo is structured
- how code is tested
- where the agent may and may not edit
- what constraints it must not violate

See:

- [example-project/README.md](/home/ubuntu/auto-coder/example-project/README.md)
- [example-project/ROADMAP.md](/home/ubuntu/auto-coder/example-project/ROADMAP.md)
- [example-project/PROJECT.md](/home/ubuntu/auto-coder/example-project/PROJECT.md)
- [example-project/CONSTRAINTS.md](/home/ubuntu/auto-coder/example-project/CONSTRAINTS.md)
- [example-project/ARCHITECTURE_NOTES.md](/home/ubuntu/auto-coder/example-project/ARCHITECTURE_NOTES.md)
