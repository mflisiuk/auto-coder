"""Project root discovery and configuration loading."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

AUTO_CODER_DIR = ".auto-coder"
CONFIG_FILE = "config.yaml"
STATE_FILE = "state.json"
STATE_DB_FILE = "state.db"
TASKS_FILE = "tasks.yaml"
TASKS_GENERATED_FILE = "tasks.generated.yaml"
TASKS_LOCAL_FILE = "tasks.local.yaml"
USAGE_FILE = "usage.json"
REPORTS_DIR = "reports"

SUPPORTED_WORKERS = {"cc", "cch", "ccg", "codex", "qwen", "gemini"}
DEFAULT_MANAGER_MODELS = {
    "anthropic": "claude-opus-4-6",
    "codex": "gpt-5",
}


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start (default: cwd) until .auto-coder/ is found."""
    current = Path(start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / AUTO_CODER_DIR).exists():
            return candidate
    raise RuntimeError(
        f"No {AUTO_CODER_DIR}/ found in {current} or any parent. "
        "Run: auto-coder init"
    )


def auto_coder_dir(project_root: Path) -> Path:
    return project_root / AUTO_CODER_DIR


def resolve_manager_model(
    manager_backend: str,
    configured_model: str | None,
) -> str:
    backend = str(manager_backend or "anthropic").strip().lower()
    default_model = DEFAULT_MANAGER_MODELS.get(backend, DEFAULT_MANAGER_MODELS["anthropic"])
    if not configured_model:
        return default_model
    configured = str(configured_model).strip()
    if not configured:
        return default_model
    # Preserve seamless switching from the generated config template: if the user
    # only flips the backend to Codex, replace the Anthropic default automatically.
    if backend == "codex" and configured == DEFAULT_MANAGER_MODELS["anthropic"]:
        return DEFAULT_MANAGER_MODELS["codex"]
    return configured


def default_config(project_root: Path) -> dict[str, Any]:
    acd = auto_coder_dir(project_root)
    return {
        "enabled": True,
        "dry_run": True,
        "base_branch": "main",
        "remote_name": "origin",
        "worktree_base_ref": "origin/main",
        "fetch_before_run": True,
        "max_tasks_per_run": 1,
        "max_attempts_per_task_per_run": 3,
        "failure_block_threshold": 3,
        "agent_timeout_minutes": 45,
        "test_timeout_minutes": 20,
        "quota_cooldown_hours": 4,
        "stale_running_timeout_minutes": 120,
        "cleanup_worktree_older_than_days": 7,
        "cleanup_worktree_on_success": True,
        "cleanup_worktree_on_failure": False,
        "auto_commit": False,
        "auto_push": False,
        "auto_merge": False,
        "review_required": True,
        "manager_enabled": True,
        "manager_backend": "anthropic",
        "manager_model": DEFAULT_MANAGER_MODELS["anthropic"],
        "manager_timeout_seconds": 180,
        "codex_reasoning_effort": "medium",
        "default_worker": "cc",
        "fallback_worker": "cch",
        "setup_commands": [],
        "allowed_paths": [],
        "protected_paths": [],
        "providers": {
            "ccg": {"token_limit_daily": 100_000, "quota_threshold": 0.80, "fallback": "cch"},
            "cc":  {"token_limit_daily": 500_000, "quota_threshold": 0.90, "fallback": "cch"},
            "cch": {"token_limit_daily": None,    "quota_threshold": 1.00, "fallback": None},
            "codex": {"token_limit_daily": None, "quota_threshold": 1.00, "fallback": "cch"},
            "qwen": {"token_limit_daily": None, "quota_threshold": 1.00, "fallback": "cch"},
            "gemini": {"token_limit_daily": None, "quota_threshold": 1.00, "fallback": "cch"},
        },
        "cc_usage_command": [],
        "ccg_usage_command": [],
        # resolved paths (not in yaml — added at load time)
        "_project_root": str(project_root),
        "_auto_coder_dir": str(acd),
        "_tasks_path": str(acd / TASKS_FILE),
        "_tasks_generated_path": str(acd / TASKS_GENERATED_FILE),
        "_tasks_local_path": str(acd / TASKS_LOCAL_FILE),
        "_state_path": str(acd / STATE_FILE),
        "_state_db_path": str(acd / STATE_DB_FILE),
        "_usage_path": str(acd / USAGE_FILE),
        "_reports_root": str(acd / REPORTS_DIR),
        "_worktree_root": str(acd / "worktrees"),
        "_lock_path": str(acd / "runner.lock"),
    }


def load_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load .auto-coder/config.yaml and merge with defaults."""
    if project_root is None:
        project_root = find_project_root()

    config_path = auto_coder_dir(project_root) / CONFIG_FILE
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    cfg = default_config(project_root)
    # shallow merge: user values override defaults
    for k, v in raw.items():
        if k in cfg and isinstance(cfg[k], dict) and isinstance(v, dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v

    # resolve Path objects for convenience
    cfg["manager_model"] = resolve_manager_model(
        cfg.get("manager_backend", "anthropic"),
        cfg.get("manager_model"),
    )
    cfg["project_root"] = project_root
    cfg["auto_coder_dir"] = Path(cfg["_auto_coder_dir"])
    cfg["tasks_path"] = Path(cfg["_tasks_path"])
    cfg["tasks_generated_path"] = Path(cfg["_tasks_generated_path"])
    cfg["tasks_local_path"] = Path(cfg["_tasks_local_path"])
    cfg["state_path"] = Path(cfg["_state_path"])
    cfg["state_db_path"] = Path(cfg["_state_db_path"])
    cfg["usage_path"] = Path(cfg["_usage_path"])
    cfg["reports_root"] = Path(cfg["_reports_root"])
    cfg["worktree_root"] = Path(cfg["_worktree_root"])
    cfg["lock_path"] = Path(cfg["_lock_path"])

    return cfg


CONFIG_YAML_TEMPLATE = """\
# auto-coder configuration
# Generated by: auto-coder init

enabled: true
dry_run: true          # set to false to actually run agents

base_branch: main
remote_name: origin
worktree_base_ref: "origin/main"
fetch_before_run: true

# Execution limits
max_tasks_per_run: 1
max_attempts_per_task_per_run: 3
failure_block_threshold: 3
agent_timeout_minutes: 45
test_timeout_minutes: 20
quota_cooldown_hours: 4

# Git automation (all false = safe defaults)
auto_commit: false
auto_push: false
auto_merge: false

# Review / manager
review_required: true
manager_enabled: true
manager_backend: anthropic
manager_model: ""        # empty = backend-specific default (anthropic=claude-opus-4-6, codex=gpt-5)
manager_timeout_seconds: 180
codex_reasoning_effort: medium

# Default worker CLI and fallback
default_worker: cc
fallback_worker: cch

# Commands run in every fresh worktree before baseline/completion commands
setup_commands: []

# Paths policy (override per task in tasks.yaml)
allowed_paths: []
protected_paths: []

# Per-provider quota thresholds and fallbacks
providers:
  ccg:
    token_limit_daily: 100000
    quota_threshold: 0.80
    fallback: cch
  cc:
    token_limit_daily: 500000
    quota_threshold: 0.90
    fallback: cch
  cch:
    token_limit_daily: null
    quota_threshold: 1.00
    fallback: null
  codex:
    token_limit_daily: null
    quota_threshold: 1.00
    fallback: cch
  qwen:
    token_limit_daily: null
    quota_threshold: 1.00
    fallback: cch
  gemini:
    token_limit_daily: null
    quota_threshold: 1.00
    fallback: cch

# Optional provider-specific quota commands
cc_usage_command: []
ccg_usage_command: []
"""
