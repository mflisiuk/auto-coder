"""CLI entry point: auto-coder init / plan / run / status / doctor."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from auto_coder.config import (
    AUTO_CODER_DIR,
    CONFIG_YAML_TEMPLATE,
    TASKS_FILE,
    find_project_root,
    load_config,
)


# ═══════════════════════════════════════════════════════════════════════ commands

def cmd_init(args: argparse.Namespace) -> int:
    """Create .auto-coder/ scaffold in the current (or given) directory."""
    target = Path(args.path or Path.cwd()).resolve()
    acd = target / AUTO_CODER_DIR
    config_path = acd / "config.yaml"

    if config_path.exists() and not args.force:
        print(f"Already initialised: {config_path}")
        print("Use --force to overwrite.")
        return 0

    acd.mkdir(parents=True, exist_ok=True)
    config_path.write_text(CONFIG_YAML_TEMPLATE, encoding="utf-8")

    gitignore = acd / ".gitignore"
    gitignore.write_text(
        "# auto-coder runtime files — do not commit\n"
        "state.json\n"
        "usage.json\n"
        "worktrees/\n"
        "reports/\n"
        "runner.lock\n"
        ".roadmap_hash\n",
        encoding="utf-8",
    )

    print(f"Initialised auto-coder in {acd}")
    print()
    print("Next steps:")
    print(f"  1. Create ROADMAP.md in {target}")
    print(f"  2. Create PROJECT.md in {target}")
    print(f"  3. Edit {config_path} (set dry_run: false when ready)")
    print(f"  4. Run: auto-coder plan")
    print(f"  5. Run: auto-coder run")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check environment: API key, worker CLIs, git remote."""
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"project_root : {project_root}")
    print(f"auto_coder_dir: {config['auto_coder_dir']}")
    print(f"base_branch  : {config['base_branch']}")
    print(f"dry_run      : {config['dry_run']}")
    print(f"manager      : {'enabled' if config.get('manager_enabled') else 'disabled'} "
          f"(model={config.get('manager_model')})")
    print(f"default worker: {config.get('default_worker')}")
    print()

    import subprocess
    checks: dict[str, bool] = {}
    checks["ANTHROPIC_API_KEY set"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    checks["git available"] = shutil.which("git") is not None
    checks["git remote reachable"] = subprocess.run(
        ["git", "remote", "-v"], cwd=str(project_root), capture_output=True
    ).returncode == 0

    workers = ["cc", "cch", "ccg", "codex"]
    for w in workers:
        checks[f"worker:{w}"] = shutil.which(w) is not None

    for name, ok in checks.items():
        status = "OK  " if ok else "FAIL"
        print(f"  {status}  {name}")

    print()
    if all(checks.values()):
        print("All checks passed.")
        return 0
    else:
        missing = [k for k, v in checks.items() if not v]
        print(f"Some checks failed: {', '.join(missing)}")
        return 1


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate .auto-coder/tasks.yaml from ROADMAP.md via Claude API."""
    from auto_coder.planner import Planner

    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    if not Planner.is_available():
        print("FAIL: ANTHROPIC_API_KEY not set.")
        return 1

    roadmap_path = project_root / "ROADMAP.md"
    if not roadmap_path.exists():
        print(f"FAIL: ROADMAP.md not found in {project_root}")
        print("Create it first — see example/ROADMAP.md")
        return 1

    print(f"Reading {roadmap_path} ...")
    planner = Planner(config)
    try:
        tasks = planner.generate()
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"\nGenerated {len(tasks)} task(s):")
    for t in tasks:
        print(f"  [{t.get('priority', '?'):>3}] {t.get('id')} — {t.get('title')}")
    print(f"\nEdit if needed: {config['tasks_path']}")
    print("Then run: auto-coder run --dry-run   (to preview)")
    print("     or:  auto-coder run --live       (to execute)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show current task states and provider usage."""
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    # tasks
    tasks_path = config["tasks_path"]
    state_path = config["state_path"]

    tasks: list[dict] = []
    if tasks_path.exists():
        raw = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
        tasks = raw.get("tasks", [])

    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    task_state = state.get("tasks", {})
    print(f"{'ID':<35} {'STATUS':<18} {'ATTEMPTS':<10} {'UPDATED'}")
    print("-" * 85)
    for task in sorted(tasks, key=lambda t: int(t.get("priority", 100))):
        tid = task.get("id", "?")
        ts = task_state.get(tid, {})
        status = ts.get("status", "queued")
        attempts = ts.get("attempt_count", 0)
        updated = (ts.get("updated_at") or "")[:16]
        enabled = "" if task.get("enabled", True) else " [disabled]"
        print(f"{tid + enabled:<35} {status:<18} {str(attempts):<10} {updated}")

    # usage
    from auto_coder.router import ProviderRouter
    router = ProviderRouter(config, config["usage_path"])
    summary = router.summary()
    if summary:
        print()
        print("Provider usage today:")
        for provider, data in summary.items():
            limit = data["limit"]
            limit_str = f"/{limit:,}" if limit else "/∞"
            ratio_str = f" ({data['ratio']*100:.0f}%)" if limit else ""
            print(f"  {provider:<8} {data['tokens_today']:>8,} tokens{limit_str}{ratio_str}"
                  f"  ({data['calls_today']} calls)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run one batch (one cron tick). Picks next eligible task and attempts it."""
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.live:
        config["dry_run"] = False
    if args.dry_run:
        config["dry_run"] = True
    if args.task:
        config["_requested_task"] = args.task

    if not config.get("enabled", True):
        print("auto-coder is disabled in config.yaml")
        return 2

    # auto-refresh tasks if ROADMAP changed
    from auto_coder.planner import Planner
    if Planner.is_available():
        planner = Planner(config)
        refreshed = planner.refresh_if_changed()
        if refreshed:
            print("ROADMAP.md changed — tasks regenerated.")

    tasks_path = config["tasks_path"]
    if not tasks_path.exists():
        print(f"No tasks.yaml found at {tasks_path}")
        print("Run: auto-coder plan")
        return 1

    raw = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
    tasks = list(raw.get("tasks", []))
    if not tasks:
        print("tasks.yaml has no tasks.")
        return 0

    state_path = config["state_path"]
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # filter to requested task if given
    requested = config.get("_requested_task")
    if requested:
        tasks = [t for t in tasks if t.get("id") == requested]
        if not tasks:
            print(f"Task not found: {requested}")
            return 2

    from auto_coder.orchestrator import run_batch
    return run_batch(config, tasks, state)


# ═══════════════════════════════════════════════════════════════════════ main

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="auto-coder",
        description="Autonomous coding agent orchestrator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialise auto-coder in current directory")
    p_init.add_argument("path", nargs="?", help="Target directory (default: cwd)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config")

    # doctor
    sub.add_parser("doctor", help="Check environment (API key, CLIs, git)")

    # plan
    sub.add_parser("plan", help="Generate tasks.yaml from ROADMAP.md via Claude API")

    # status
    sub.add_parser("status", help="Show task states and provider usage")

    # run
    p_run = sub.add_parser("run", help="Execute one batch (one cron tick)")
    p_run.add_argument("--task", help="Run a specific task id")
    p_run.add_argument("--live", action="store_true", help="Execute agents (overrides dry_run)")
    p_run.add_argument("--dry-run", action="store_true", dest="dry_run",
                       help="Force dry run (overrides config)")

    args = parser.parse_args()

    handlers = {
        "init": cmd_init,
        "doctor": cmd_doctor,
        "plan": cmd_plan,
        "status": cmd_status,
        "run": cmd_run,
    }
    sys.exit(handlers[args.command](args))
