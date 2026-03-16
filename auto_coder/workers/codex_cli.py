"""Worker adapter for Codex CLI."""
from __future__ import annotations

import shutil
from pathlib import Path

from auto_coder.worker import extract_token_usage, is_quota_error, run_worker
from auto_coder.workers.base import WorkerAdapter, WorkerRunResult


class CodexCliWorker(WorkerAdapter):
    @classmethod
    def name(cls) -> str:
        return "codex"

    @classmethod
    def is_installed(cls) -> bool:
        return shutil.which("codex") is not None

    def run(
        self,
        *,
        prompt: str,
        worktree: Path,
        report_dir: Path,
        model: str | None,
        timeout_minutes: int,
        max_budget_usd: float | None = None,
    ) -> WorkerRunResult:
        result = run_worker(
            provider="codex",
            prompt=prompt,
            worktree=worktree,
            report_dir=report_dir,
            model=model,
            max_budget_usd=max_budget_usd,
            timeout_minutes=timeout_minutes,
        )
        return WorkerRunResult(
            worker_name="codex",
            command=["codex"],
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            token_usage=extract_token_usage(result.stdout),
            quota_exhausted=is_quota_error(result.stderr, result.stdout, returncode=result.returncode),
            metadata={},
        )
