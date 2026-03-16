"""CLI entry point: auto-coder init / plan / run / status / doctor."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from auto_coder.bootstrap_brief import bootstrap_brief
from auto_coder.config import (
    AUTO_CODER_DIR,
    CONFIG_YAML_TEMPLATE,
    TASKS_FILE,
    find_project_root,
    load_config,
)
from auto_coder.operator import (
    apply_go_live_profile,
    apply_task_override,
    install_cron_job,
    install_systemd_units,
    load_latest_report_dir,
    now_iso,
)
from auto_coder.storage import (
    ensure_database,
    export_state,
    force_task_retry,
    get_task_runtime,
    list_attempts_for_task,
    list_run_ticks,
    list_tables,
    list_task_runtime,
    list_task_specs,
    list_work_orders_for_task,
    sync_tasks,
)
from auto_coder.brief_validator import validate_project_brief


# ═══════════════════════════════════════════════════════════════════════ commands

def _load_runtime_state(config: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {"tasks": {}, "runs": []}
    state_path = config["state_path"]
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {"tasks": {}, "runs": []}
    if config["state_db_path"].exists():
        state = export_state(config["state_db_path"])
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state



def _load_task_specs(config: dict[str, Any], yaml_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not config["state_db_path"].exists():
        return list(yaml_tasks)
    specs = list_task_specs(config["state_db_path"])
    if specs:
        return specs
    return list(yaml_tasks)

def _probe_manager_backend(config: dict[str, Any]) -> str:
    backend = str(config.get("manager_backend", "anthropic")).strip().lower()
    if backend == "anthropic":
        from auto_coder.managers.anthropic import AnthropicManagerBackend

        return AnthropicManagerBackend.probe_live(config)
    if backend == "codex":
        from auto_coder.managers.codex_bridge import CodexManagerBridge

        return CodexManagerBridge.probe_live(config)
    raise RuntimeError(f"Unsupported manager backend: {backend}")

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
    ensure_database(acd / "state.db")

    gitignore = acd / ".gitignore"
    gitignore.write_text(
        "# auto-coder runtime files — do not commit\n"
        "state.json\n"
        "state.db\n"
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
    print("     or run: auto-coder bootstrap-brief")
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
          f"(backend={config.get('manager_backend')}, model={config.get('manager_model')})")
    print(f"default worker: {config.get('default_worker')}")
    print()

    from auto_coder.git_ops import resolve_worktree_base_ref
    checks: dict[str, bool] = {}
    checks["git available"] = shutil.which("git") is not None
    remote_result = subprocess.run(
        ["git", "remote", "-v"], cwd=str(project_root), capture_output=True
    )
    remote_configured = remote_result.returncode == 0 and bool(remote_result.stdout.strip())
    checks["git remote configured"] = remote_configured or not bool(config.get("auto_push"))
    checks["state.db present"] = config["state_db_path"].exists()
    try:
        resolved_base_ref = resolve_worktree_base_ref(
            project_root,
            config.get("worktree_base_ref"),
            str(config.get("base_branch", "main")),
        )
        checks[f"worktree base ref ({resolved_base_ref})"] = True
    except RuntimeError:
        checks["worktree base ref"] = False
    manager_backend = str(config.get("manager_backend", "anthropic")).strip().lower()
    if manager_backend == "anthropic":
        checks["manager:anthropic key"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    elif manager_backend == "codex":
        checks["manager:codex cli"] = shutil.which("codex") is not None
        checks["manager:node"] = shutil.which("node") is not None

    workers = ["cc", "cch", "ccg", "codex"]
    for w in workers:
        checks[f"worker:{w}"] = shutil.which(w) is not None

    for name, ok in checks.items():
        status = "OK  " if ok else "FAIL"
        print(f"  {status}  {name}")

    from auto_coder.router import ProviderRouter
    router = ProviderRouter(config, config["usage_path"])
    probe_info = router.probe_availability()
    if probe_info:
        print()
        print("Quota probes:")
        for provider, source in sorted(probe_info.items()):
            print(f"  {provider:<8} {source}")

    validation = validate_project_brief(project_root)
    print()
    print("Brief validation:")
    if validation.ok:
        print("  OK    input brief is sufficient for planning")
    else:
        print(f"  FAIL  {validation.summary()}")
        for item in validation.next_actions:
            print(f"    - {item}")

    probe_ok = True
    if getattr(args, "probe_live", False):
        print()
        print("Live probe:")
        try:
            probe_output = _probe_manager_backend(config)
        except Exception as exc:
            probe_ok = False
            print(f"  FAIL  manager live probe failed: {exc}")
        else:
            print(f"  OK    manager live probe succeeded: {probe_output[:200]}")

    print()
    overall_ok = all(checks.values()) and validation.ok and probe_ok
    if overall_ok:
        print("All checks passed.")
        return 0
    else:
        missing = [k for k, v in checks.items() if not v]
        if not validation.ok:
            missing.append("brief validation")
        if not probe_ok:
            missing.append("manager live probe")
        print(f"Some checks failed: {', '.join(missing)}")
        return 1


def cmd_bootstrap_brief(args: argparse.Namespace) -> int:
    project_root = Path(args.path or Path.cwd()).resolve()
    try:
        created = bootstrap_brief(project_root, force=bool(args.force))
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"Bootstrapped brief files in {project_root}:")
    for name, path in created.items():
        print(f"  {name:<22} {path}")
    print("Review the generated docs, then run: auto-coder init && auto-coder doctor && auto-coder plan")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate .auto-coder/tasks.yaml from ROADMAP.md via Claude API."""
    from auto_coder.planner import Planner

    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    roadmap_path = project_root / "ROADMAP.md"
    if not roadmap_path.exists():
        print(f"FAIL: ROADMAP.md not found in {project_root}")
        print("Create it first — see example/ROADMAP.md")
        return 1

    validation = validate_project_brief(project_root)
    if not validation.ok:
        print(f"FAIL: {validation.summary()}")
        for item in validation.next_actions:
            print(f"  - {item}")
        return 1

    print(f"Reading {roadmap_path} ...")
    print(
        "Planner backend: "
        f"{config.get('manager_backend')} "
        f"(timeout={int(config.get('manager_timeout_seconds', 180))}s)"
    )
    planner = Planner(config)
    if not planner.backend_available():
        print(f"FAIL: manager backend unavailable for planning ({config.get('manager_backend')}).")
        return 1
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
    state_db_path = config["state_db_path"]

    tasks: list[dict] = []
    if tasks_path.exists():
        raw = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
        tasks = raw.get("tasks", [])

    # Progress summary
    from auto_coder.storage import count_tasks_by_status
    status_counts = count_tasks_by_status(state_db_path) if state_db_path.exists() else {}
    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0) + status_counts.get("quarantined", 0)
    remaining = total - completed - failed

    print(f"Progress: {completed}/{total} completed ({failed} failed, {remaining} remaining)")
    print("-" * 85)


    state = _load_runtime_state(config)

    task_state = state.get("tasks", {})
    print(f"{'ID':<35} {'STATUS':<18} {'ATTEMPTS':<10} {'LAST RUN'}")
    print("-" * 85)
    from auto_coder.storage import list_task_runtime_with_attempts
    db_rows = list_task_runtime_with_attempts(state_db_path) if state_db_path.exists() else []
    if db_rows:
        for row in db_rows:
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            attempts = payload.get("attempt_count", 0)
            # Use last_attempt_at if available, otherwise fall back to task.updated_at
            last_run = (row.get("last_attempt_at") or row.get("updated_at") or "")[:16]
            enabled = "" if payload.get("enabled", True) else " [disabled]"
            print(f"{str(row['id']) + enabled:<35} {str(row['status']):<18} {str(attempts):<10} {last_run}")
    else:
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
            quota_str = f"{data['quota_state']} via {data['probe_source']}"
            retry_after = f" retry_after={data['retry_after']}" if data.get("retry_after") else ""
            print(
                f"  {provider:<8} {data['tokens_today']:>8,} tokens{limit_str}{ratio_str}"
                f"  ({data['calls_today']} calls)  {quota_str}{retry_after}"
            )

    if state_db_path.exists():
        print()
        print(f"SQLite storage: {state_db_path}")
        print(f"Tables: {', '.join(list_tables(state_db_path))}")
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
    if getattr(args, "loop", False):
        config["_loop_mode"] = True
        config["_max_ticks"] = getattr(args, "max_ticks", 100)

    if not config.get("enabled", True):
        print("auto-coder is disabled in config.yaml")
        return 2

    # auto-refresh tasks if ROADMAP changed
    from auto_coder.planner import Planner
    planner = Planner(config)
    if planner.backend_available():
        try:
            refreshed = planner.refresh_if_changed()
        except Exception as exc:
            print(f"FAIL: could not refresh tasks from ROADMAP.md: {exc}")
            return 1
        if refreshed:
            print("ROADMAP.md changed — tasks regenerated.")

    tasks_path = config["tasks_path"]
    if not tasks_path.exists():
        print(f"No tasks.yaml found at {tasks_path}")
        print("Run: auto-coder plan")
        return 1

    raw = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
    yaml_tasks = list(raw.get("tasks", []))
    if not yaml_tasks:
        print("tasks.yaml has no tasks.")
        return 0
    sync_tasks(config["state_db_path"], yaml_tasks)
    tasks = _load_task_specs(config, yaml_tasks)

    state = _load_runtime_state(config)

    # filter to requested task if given
    requested = config.get("_requested_task")
    if requested:
        tasks = [t for t in tasks if t.get("id") == requested]
        if not tasks:
            print(f"Task not found: {requested}")
            return 2

    from auto_coder.orchestrator import run_batch

    exit_code = run_batch(config, tasks, state)
    if exit_code != 0 and config["state_db_path"].exists():
        latest = list_run_ticks(config["state_db_path"], limit=1)
        if latest:
            row = latest[0]
            try:
                payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            except Exception:
                payload = {}
            print()
            print("Last run failure summary:")
            print(f"  run_id    : {row['id']}")
            print(f"  status    : {row['status']}")
            print(f"  task_id   : {payload.get('task_id', '-')}")
            print(f"  note      : {payload.get('note', '-')}")
            print(f"  report_dir: {payload.get('report_dir', '-')}")
    return exit_code


def cmd_migrate(args: argparse.Namespace) -> int:
    """Import a legacy tasks YAML file into tasks.local.yaml."""
    from auto_coder.migrate import migrate_legacy_tasks

    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    source = Path(args.source).resolve()
    try:
        tasks = migrate_legacy_tasks(config, source)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"Imported {len(tasks)} task(s) into {config['tasks_local_path']}")
    print("Run: auto-coder plan")
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    rows = list_run_ticks(config["state_db_path"], limit=int(args.limit))
    print(f"{'RUN ID':<38} {'STATUS':<18} {'TASK':<30} {'UPDATED'}")
    print("-" * 105)
    for row in rows:
        try:
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        except Exception:
            payload = {}
        task_id = str(payload.get("task_id", ""))[:30]
        updated = str(row["updated_at"] or "")[:16]
        print(f"{str(row['id']):<38} {str(row['status']):<18} {task_id:<30} {updated}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    row = get_task_runtime(config["state_db_path"], args.task_id)
    if row is None:
        print(f"FAIL: task not found: {args.task_id}")
        return 1

    try:
        payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    except Exception:
        payload = {}
    print(f"Task      : {row['id']}")
    print(f"Title     : {row['title']}")
    print(f"Status    : {row['status']}")
    print(f"Priority  : {row['priority']}")
    print(f"Updated   : {row['updated_at']}")
    if payload.get("note"):
        print(f"Note      : {payload['note']}")
    if payload.get("retry_after"):
        print(f"Retry after: {payload['retry_after']}")
    print()

    work_orders = list_work_orders_for_task(config["state_db_path"], args.task_id)
    print("Work orders:")
    if not work_orders:
        print("  (none)")
    for work_order in work_orders[-5:]:
        try:
            work_payload = json.loads(work_order["payload_json"]) if work_order["payload_json"] else {}
        except Exception:
            work_payload = {}
        selected_worker = work_payload.get("selected_worker", "")
        print(
            f"  {work_order['id']}  status={work_order['status']}  seq={work_order['sequence_no']}"
            f"  worker={selected_worker}"
        )
    print()

    attempts = list_attempts_for_task(config["state_db_path"], args.task_id)
    print("Attempts:")
    if not attempts:
        print("  (none)")
    for attempt in attempts[-10:]:
        try:
            attempt_payload = json.loads(attempt["payload_json"]) if attempt["payload_json"] else {}
        except Exception:
            attempt_payload = {}
        note = str(attempt_payload.get("note", ""))[:80]
        print(
            f"  #{attempt['id']} status={attempt['status']} worker={attempt['worker_name'] or ''}"
            f" work_order={attempt['work_order_id'] or ''} note={note}"
        )
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    note = args.note or "Forced retry requested by operator."
    ok = force_task_retry(
        config["state_db_path"],
        args.task_id,
        note=note,
        retry_after=now_iso(),
    )
    if not ok:
        print(f"FAIL: task not found: {args.task_id}")
        return 1
    if config["state_db_path"].exists():
        config["state_path"].write_text(
            json.dumps(export_state(config["state_db_path"]), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Queued forced retry for {args.task_id}")
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    target = Path(args.file).resolve() if args.file else config["auto_coder_dir"] / "cron.log"
    if not target.exists():
        latest_report_dir = load_latest_report_dir(config)
        if latest_report_dir is not None:
            candidates = sorted(latest_report_dir.rglob("*.log"), key=lambda item: item.stat().st_mtime)
            if candidates:
                target = candidates[-1]
    if not target.exists():
        print("FAIL: no log file found. Create .auto-coder/cron.log or run a task first.")
        return 1

    print(f"Tailing: {target}")
    if args.follow:
        subprocess.run(["tail", "-n", str(args.lines), "-f", str(target)], check=False)
    else:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-int(args.lines):]:
            print(line)
    return 0


def cmd_pin(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    try:
        updated = apply_task_override(config, args.task_id, {"priority": int(args.priority), "enabled": True})
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"Pinned {updated['id']} to priority {updated['priority']}")
    return 0


def cmd_disable_task(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    try:
        updated = apply_task_override(config, args.task_id, {"enabled": False})
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"Disabled {updated['id']}")
    return 0


def cmd_prefer_worker(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    try:
        updated = apply_task_override(config, args.task_id, {"preferred_workers": [args.worker]})
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"Set preferred worker for {updated['id']} to {args.worker}")
    return 0


def cmd_go_live(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    manager_backend = args.manager_backend
    if args.codex:
        manager_backend = "codex"
    elif args.anthropic:
        manager_backend = "anthropic"
    default_worker = args.default_worker
    if not default_worker and manager_backend == "codex":
        default_worker = "codex"

    updated = apply_go_live_profile(
        config,
        manager_backend=manager_backend,
        default_worker=default_worker,
    )
    print("Updated config for go-live:")
    for key in ("manager_backend", "default_worker", "dry_run", "auto_commit", "auto_push", "auto_merge"):
        print(f"  {key}: {updated.get(key)}")

    if args.cron:
        block = install_cron_job(config, schedule=args.cron, with_plan=args.with_plan)
        print()
        print("Installed cron block:")
        print(block.rstrip())
    if args.systemd_interval:
        service_path, timer_path = install_systemd_units(
            config,
            interval_minutes=int(args.systemd_interval),
            enable=not args.write_only,
        )
        print()
        print(f"Wrote systemd service: {service_path}")
        print(f"Wrote systemd timer  : {timer_path}")
    return 0


def cmd_install_cron(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    block = install_cron_job(config, schedule=args.schedule, with_plan=args.with_plan)
    print("Installed cron block:")
    print(block.rstrip())
    return 0


def cmd_install_systemd(args: argparse.Namespace) -> int:
    try:
        project_root = find_project_root()
        config = load_config(project_root)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    service_path, timer_path = install_systemd_units(
        config,
        interval_minutes=int(args.interval_minutes),
        enable=not args.write_only,
    )
    print(f"Wrote systemd service: {service_path}")
    print(f"Wrote systemd timer  : {timer_path}")
    return 0


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
    p_doctor = sub.add_parser("doctor", help="Check environment (API key, CLIs, git)")
    p_doctor.add_argument("--probe-live", action="store_true", help="Run a minimal live manager backend probe")

    # bootstrap-brief
    p_bootstrap = sub.add_parser("bootstrap-brief", help="Generate a first-pass brief from an existing repository")
    p_bootstrap.add_argument("path", nargs="?", help="Repository path (default: cwd)")
    p_bootstrap.add_argument("--force", action="store_true", help="Overwrite existing brief files")

    # plan
    sub.add_parser("plan", help="Generate tasks.yaml from ROADMAP.md via Claude API")

    # status
    sub.add_parser("status", help="Show task states and provider usage")

    # runs
    p_runs = sub.add_parser("runs", help="Show recent run ticks")
    p_runs.add_argument("--limit", type=int, default=20, help="Number of runs to show")

    # inspect
    p_inspect = sub.add_parser("inspect", help="Inspect one task runtime, work orders, and attempts")
    p_inspect.add_argument("task_id", help="Task id")

    # retry
    p_retry = sub.add_parser("retry", help="Force a task back into waiting_for_retry")
    p_retry.add_argument("task_id", help="Task id")
    p_retry.add_argument("--note", help="Optional operator note")

    # tail
    p_tail = sub.add_parser("tail", help="Tail operator log or latest report log")
    p_tail.add_argument("--file", help="Explicit log file path")
    p_tail.add_argument("-n", "--lines", type=int, default=40, help="Number of lines")
    p_tail.add_argument("-f", "--follow", action="store_true", help="Follow the log")

    # run
    p_run = sub.add_parser("run", help="Execute one batch (one cron tick)")
    p_run.add_argument("--task", help="Run a specific task id")
    p_run.add_argument("--live", action="store_true", help="Execute agents (overrides dry_run)")
    p_run.add_argument("--dry-run", action="store_true", dest="dry_run",
                       help="Force dry run (overrides config)")
    p_run.add_argument("--loop", action="store_true",
                       help="Keep running ticks until all tasks complete or --max-ticks is reached")
    p_run.add_argument("--max-ticks", type=int, default=100, dest="max_ticks",
                       help="Maximum number of ticks in --loop mode (default: 100)")

    p_migrate = sub.add_parser("migrate", help="Import a legacy tasks.yaml into tasks.local.yaml")
    p_migrate.add_argument("source", help="Path to legacy YAML file with top-level tasks:")

    p_pin = sub.add_parser("pin", help="Promote a task by writing an override to tasks.local.yaml")
    p_pin.add_argument("task_id", help="Task id")
    p_pin.add_argument("--priority", type=int, default=10, help="Priority to set")

    p_disable = sub.add_parser("disable-task", help="Disable a task through tasks.local.yaml")
    p_disable.add_argument("task_id", help="Task id")

    p_prefer = sub.add_parser("prefer-worker", help="Set preferred worker for a task via tasks.local.yaml")
    p_prefer.add_argument("task_id", help="Task id")
    p_prefer.add_argument("worker", help="Worker name")

    p_go_live = sub.add_parser("go-live", help="Apply a live config profile and optionally install a scheduler")
    p_go_live.add_argument("--manager-backend", choices=["anthropic", "codex"], help="Manager backend to set")
    p_go_live.add_argument("--codex", action="store_true", help="Shortcut for --manager-backend codex")
    p_go_live.add_argument("--anthropic", action="store_true", help="Shortcut for --manager-backend anthropic")
    p_go_live.add_argument("--default-worker", help="Default worker to set")
    p_go_live.add_argument("--cron", help="Install/update a cron entry with the given schedule")
    p_go_live.add_argument("--with-plan", action="store_true", help="Include auto-coder plan in installed cron")
    p_go_live.add_argument("--systemd-interval", type=int, help="Write/install a user systemd timer in minutes")
    p_go_live.add_argument("--write-only", action="store_true", help="Only write scheduler files; do not enable them")

    p_install_cron = sub.add_parser("install-cron", help="Install/update a cron entry for auto-coder")
    p_install_cron.add_argument("schedule", help="Cron schedule, e.g. */20 * * * *")
    p_install_cron.add_argument("--with-plan", action="store_true", help="Also install auto-coder plan")

    p_install_systemd = sub.add_parser("install-systemd", help="Write/install a user systemd timer")
    p_install_systemd.add_argument("interval_minutes", type=int, help="Tick interval in minutes")
    p_install_systemd.add_argument("--write-only", action="store_true", help="Only write files; do not enable timer")

    args = parser.parse_args()

    handlers = {
        "init": cmd_init,
        "doctor": cmd_doctor,
        "bootstrap-brief": cmd_bootstrap_brief,
        "plan": cmd_plan,
        "status": cmd_status,
        "runs": cmd_runs,
        "inspect": cmd_inspect,
        "retry": cmd_retry,
        "tail": cmd_tail,
        "run": cmd_run,
        "migrate": cmd_migrate,
        "pin": cmd_pin,
        "disable-task": cmd_disable_task,
        "prefer-worker": cmd_prefer_worker,
        "go-live": cmd_go_live,
        "install-cron": cmd_install_cron,
        "install-systemd": cmd_install_systemd,
    }
    sys.exit(handlers[args.command](args))
