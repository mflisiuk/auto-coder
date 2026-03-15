"""Worker adapters for coding CLIs."""

from auto_coder.workers.base import WorkerAdapter
from auto_coder.workers.claude_code import ClaudeCodeWorker
from auto_coder.workers.codex_cli import CodexCliWorker
from auto_coder.workers.generic_cli import GenericCliWorker


def build_worker_adapter(provider: str) -> WorkerAdapter:
    if provider in {"cc", "cch", "ccg"}:
        return ClaudeCodeWorker(binary_name=provider)
    if provider == "codex":
        return CodexCliWorker()
    return GenericCliWorker(provider)
