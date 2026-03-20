"""Spawn coding agent subprocesses (cc, cch, ccg, codex, ...)."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


SUPPORTED_WORKERS = {"cc", "cch", "ccg", "codex", "qwen", "gemini"}


def run_worker(
    *,
    provider: str,
    prompt: str,
    worktree: Path,
    report_dir: Path,
    model: str | None = None,
    max_budget_usd: float | None = None,
    timeout_minutes: int = 45,
) -> subprocess.CompletedProcess[str]:
    """Spawn a coding agent and wait for completion."""
    cmd = _build_cmd(provider, model=model, max_budget_usd=max_budget_usd)
    result = _run(cmd, cwd=worktree, stdin_text=prompt, timeout=timeout_minutes * 60)
    _save(report_dir, "worker.stdout.log", result.stdout)
    _save(report_dir, "worker.stderr.log", result.stderr)
    return result


def _build_cmd(
    provider: str,
    *,
    model: str | None,
    max_budget_usd: float | None,
) -> list[str]:
    if provider in {"cc", "cch", "ccg"}:
        cmd = [provider, "-p", "--dangerously-skip-permissions", "--output-format", "json"]
        if model:
            cmd += ["--model", model]
        if max_budget_usd is not None:
            cmd += ["--max-budget-usd", str(max_budget_usd)]
        return cmd

    if provider == "codex":
        cmd = [
            "codex",
            "-a", "never",
            "-s", "workspace-write",
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
        ]
        if model:
            cmd += ["-m", model]
        return cmd

    # Generic fallback: treat provider name as CLI command, pass prompt via stdin
    return [provider]


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    stdin_text: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    # Augment PATH so workers (claude, ccg) are found in cron/minimal environments.
    home = os.path.expanduser("~")
    extra = ":".join([
        f"{home}/.nvm/versions/node/v22.22.0/bin",
        f"{home}/.local/bin",
        "/usr/local/bin",
    ])
    env["PATH"] = f"{extra}:{env.get('PATH', '/usr/bin:/bin')}"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


def _save(report_dir: Path, filename: str, content: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / filename).write_text(content, encoding="utf-8")


def extract_token_usage(stdout: str) -> int:
    """Parse token usage from agent JSON output. Returns 0 if not found."""
    import json, re
    for match in re.finditer(r"\{", stdout):
        try:
            obj = json.loads(stdout[match.start():])
            usage = obj.get("usage") or obj.get("token_usage") or {}
            total = usage.get("total_tokens") or (
                (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
            )
            if total:
                return int(total)
        except Exception:
            continue
    return 0


def is_quota_error(stderr: str, stdout: str, *, returncode: int | None = None) -> bool:
    """Detect genuine quota/rate-limit failures from agent output."""
    # Always try to parse JSON output regardless of returncode.
    # Claude Code (cc/cch/ccg) may set is_error:true in JSON with any returncode.
    quota_phrases = (
        "hit your limit",
        "usage limit",
        "rate limit",
        "too many requests",
        "quota",
        "overloaded",
        "subscription limit",
        "limit reached",
    )
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if parsed.get("is_error") and parsed.get("result"):
            result_text = str(parsed["result"]).lower()
            if any(phrase in result_text for phrase in quota_phrases):
                return True

    # Fallback: check for common error patterns in stderr/stdout text.
    text = f"{stderr}\n{stdout}".lower()
    patterns = (
        r"\b429\b",
        r"rate[\s_-]?limit",
        r"too many requests",
        r"insufficient_quota",
        r"billing_hard_limit",
        r"quota(?:\s+has\s+been)?\s+(?:exceeded|exhausted|reached)",
        r"\boverloaded\b",
        r"hit\s+(?:your\s+)?limit",
        r"subscription\s+limit",
    )
    return any(re.search(pattern, text) for pattern in patterns)
