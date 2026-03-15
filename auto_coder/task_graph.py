"""Task graph validation helpers."""
from __future__ import annotations

from typing import Any


def validate_task_graph(tasks: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    task_ids = [str(task.get("id", "")).strip() for task in tasks]
    duplicates = {task_id for task_id in task_ids if task_id and task_ids.count(task_id) > 1}
    for task_id in sorted(duplicates):
        errors.append(f"duplicate task id: {task_id}")

    known_ids = {task_id for task_id in task_ids if task_id}
    for task in tasks:
        task_id = str(task.get("id", "")).strip()
        for dependency in task.get("depends_on", []):
            if dependency not in known_ids:
                errors.append(f"{task_id}: unknown dependency {dependency}")
            if dependency == task_id:
                errors.append(f"{task_id}: self dependency")

    errors.extend(_find_cycles(tasks))
    return sorted(set(errors))


def _find_cycles(tasks: list[dict[str, Any]]) -> list[str]:
    graph = {str(task.get("id", "")): list(task.get("depends_on", [])) for task in tasks if task.get("id")}
    visiting: set[str] = set()
    visited: set[str] = set()
    errors: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        if node in visited or node not in graph:
            return
        if node in visiting:
            cycle = " -> ".join(stack + [node])
            errors.append(f"cycle detected: {cycle}")
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(str(dependency), stack + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return errors
