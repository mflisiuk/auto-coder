"""ManagerBrain: evaluates agent attempts via Anthropic API with persistent history."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AttemptResult:
    attempt_no: int
    worker_returncode: int
    changed_files: list[str]
    policy_violations: list[str]
    test_results: list[dict]
    test_stdout: dict[str, str]
    test_stderr: dict[str, str]
    diff_patch: str
    diff_stat: str
    worker_stdout_excerpt: str
    quota_error: bool = False


@dataclass
class ManagerDecision:
    verdict: str                    # "approve" | "retry" | "abandon"
    feedback: str
    blockers: list[str] = field(default_factory=list)


class ManagerBrain:
    SYSTEM_PROMPT = (
        "You are an engineering manager overseeing an autonomous coding agent. "
        "Evaluate each attempt and provide specific, actionable feedback. "
        "Be concrete: name the exact file, function, and change needed. "
        "Respond in JSON only:\n"
        '{"verdict": "approve"|"retry"|"abandon", "feedback": str, "blockers": [str]}'
    )

    def __init__(
        self,
        task_id: str,
        task: dict[str, Any],
        config: dict[str, Any],
        state_path: Path,
        model: str = "claude-opus-4-6",
    ):
        self.task_id = task_id
        self.task = task
        self.config = config
        self.state_path = state_path
        self.model = model
        self.messages: list[dict] = self._load_messages()
        self._last_decision: ManagerDecision | None = None

        # Restore last decision from history if available
        if self.messages and self.messages[-1]["role"] == "assistant":
            self._last_decision = self._parse_decision(self.messages[-1]["content"])

    # ------------------------------------------------------------------ public

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def has_feedback(self) -> bool:
        return self._last_decision is not None

    def evaluate_attempt(self, result: AttemptResult) -> ManagerDecision:
        import anthropic

        client = anthropic.Anthropic()
        user_text = self._format_request(result)
        self.messages.append({"role": "user", "content": user_text})

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.SYSTEM_PROMPT,
                messages=self.messages,
            )
            assistant_text = response.content[0].text
        except Exception as exc:
            decision = ManagerDecision(
                verdict="retry",
                feedback=f"Manager API error: {exc}. Retrying with previous context.",
                blockers=[f"manager_api_error: {exc}"],
            )
            self._last_decision = decision
            self._save_messages()
            return decision

        self.messages.append({"role": "assistant", "content": assistant_text})
        decision = self._parse_decision(assistant_text)
        self._last_decision = decision
        self._save_messages()
        return decision

    def build_worker_feedback(self) -> str:
        if not self._last_decision:
            return ""
        d = self._last_decision
        lines = ["MANAGER FEEDBACK (from previous attempt):", d.feedback]
        if d.blockers:
            lines += ["", "Blockers to fix:"] + [f"- {b}" for b in d.blockers]
        return "\n".join(lines).strip()

    # ----------------------------------------------------------------- private

    def _load_messages(self) -> list[dict]:
        if not self.state_path.exists():
            return []
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            return list(state.get("tasks", {}).get(self.task_id, {}).get("manager_messages", []))
        except Exception:
            return []

    def _save_messages(self) -> None:
        state: dict[str, Any] = {}
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        state.setdefault("tasks", {}).setdefault(self.task_id, {})["manager_messages"] = self.messages
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _format_request(self, result: AttemptResult) -> str:
        allowed = list(self.task.get("allowed_paths") or self.config.get("allowed_paths", []))
        protected = list(self.config.get("protected_paths", []))
        passed = [r["command"] for r in result.test_results if r.get("passed")]
        failed = [r["command"] for r in result.test_results if not r.get("passed")]

        output_sections = []
        for cmd in failed:
            out = result.test_stdout.get(cmd, "")
            err = result.test_stderr.get(cmd, "")
            if out or err:
                output_sections.append(
                    f"=== FAILED: {cmd} ===\n"
                    f"--- stdout ---\n{out[:1500]}\n"
                    f"--- stderr ---\n{err[:1500]}"
                )

        lines = [
            f"TASK: {self.task_id} — {self.task.get('title', '')}",
            f"ATTEMPT: {result.attempt_no}",
            f"WORKER EXIT CODE: {result.worker_returncode}",
            f"QUOTA ERROR: {result.quota_error}",
            "",
            f"ALLOWED PATHS: {', '.join(allowed) or '(none)'}",
            f"PROTECTED PATHS: {', '.join(protected) or '(none)'}",
            "",
            f"CHANGED FILES: {', '.join(result.changed_files) or '(none)'}",
        ]
        if result.policy_violations:
            lines += ["", "POLICY VIOLATIONS:"] + [f"  - {v}" for v in result.policy_violations]
        lines.append("")
        if passed:
            lines.append(f"PASSED ({len(passed)}): {', '.join(passed)}")
        if failed:
            lines += [f"FAILED ({len(failed)}): {', '.join(failed)}", "", "TEST OUTPUT:"]
            lines.extend(output_sections)
        if result.diff_stat:
            lines += ["", "DIFF STAT:", result.diff_stat]
        if result.diff_patch:
            lines += ["", "DIFF PATCH:", result.diff_patch[:6000]]
        if result.worker_stdout_excerpt:
            lines += ["", "WORKER STDOUT:", result.worker_stdout_excerpt[:2000]]
        lines += [
            "",
            "Verdict rules: approve if tests pass + no violations. "
            "retry if fixable. abandon if fundamentally broken.",
        ]
        return "\n".join(lines)

    def _parse_decision(self, text: str) -> ManagerDecision:
        text = (text or "").strip()
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and "verdict" in obj:
                return ManagerDecision(
                    verdict=str(obj.get("verdict", "retry")),
                    feedback=str(obj.get("feedback", "")),
                    blockers=list(obj.get("blockers", [])),
                )
        except Exception:
            pass
        for m in re.finditer(r"\{", text):
            try:
                obj = json.loads(text[m.start():])
                if isinstance(obj, dict) and "verdict" in obj:
                    return ManagerDecision(
                        verdict=str(obj.get("verdict", "retry")),
                        feedback=str(obj.get("feedback", "")),
                        blockers=list(obj.get("blockers", [])),
                    )
            except Exception:
                continue
        return ManagerDecision(
            verdict="retry",
            feedback=f"Could not parse manager response: {text[:200]}",
            blockers=["malformed_manager_response"],
        )
