#!/usr/bin/env python3
"""Deterministic wrapper for audited Codex/Claude dispatch workflows."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def locate_dispatcher() -> Path:
    override = os.environ.get("AGENT_DISPATCH_BIN")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_file():
            return path
        raise SystemExit(f"AGENT_DISPATCH_BIN is not a file: {path}")
    source = Path(__file__).resolve()
    for parent in source.parents:
        candidate = parent / "bin" / "dispatch-agent"
        if candidate.is_file():
            return candidate
    found = shutil.which("dispatch-agent")
    if found:
        return Path(found).resolve()
    raise SystemExit(
        "Cannot locate bin/dispatch-agent. Keep the skill symlinked to its clone, "
        "put dispatch-agent on PATH, or set AGENT_DISPATCH_BIN.")


def call_dispatcher(args: List[str], live_stderr: bool = False) -> Tuple[int, str, str]:
    command = [sys.executable, str(locate_dispatcher()), *args]
    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=None if live_stderr else subprocess.PIPE,
        # Preserve AGENT_CALL_DEPTH. Removing it here would turn this helper into
        # a one-hop guard bypass; dispatcher must see and enforce the caller depth.
        env=dict(os.environ),
    )
    return proc.returncode, proc.stdout, "" if live_stderr else (proc.stderr or "")


def parse_json(text: str, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} did not return JSON: {exc}: {text[:500]}")
    if not isinstance(value, dict):
        raise SystemExit(f"{label} returned non-object JSON")
    return value


def git_head(worktree: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"Cannot read HEAD for {worktree}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def git_common_dir(worktree: Path) -> Path:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-common-dir"],
        text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"Cannot read Git common directory for {worktree}: {proc.stderr.strip()}")
    value = Path(proc.stdout.strip())
    if not value.is_absolute():
        value = worktree / value
    return value.resolve()


def safe_task_id(raw: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if len(normalized) <= 64:
        return normalized
    suffix = hashlib.sha256(normalized.encode()).hexdigest()[:8]
    return normalized[:55].rstrip("-") + "-" + suffix


def load_envelope(path: Path) -> Dict[str, Any]:
    value = parse_json(path.read_text(encoding="utf-8"), f"envelope {path}")
    return value


def run_preflight(envelope_path: Path) -> Dict[str, Any]:
    code, stdout, stderr = call_dispatcher(["--preflight", str(envelope_path)])
    result = parse_json(stdout, "preflight")
    if code != 0 or not result.get("ready"):
        if stderr:
            print(stderr, file=sys.stderr, end="")
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def make_handback_envelope(original: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    worktree = Path(original["worktree"]).resolve()
    result_path = None
    if result.get("events_path"):
        candidate = Path(result["events_path"]) / "result-envelope.json"
        if candidate.is_file():
            result_path = str(candidate)
    workflow = original.get("workflow") or {}
    target = original["target"]
    prompt = (
        "Read-only automatic handback. Do not modify files, commit, or call another agent. "
        f"Read the completed dispatcher result at {result_path or 'the primary result supplied below'}. "
        f"Record task_id={original['task_id']}, status={result.get('status')}, "
        f"verdict={result.get('verdict')}, head={result.get('head_commit')} in the registered "
        f"{target} App shared context. Preserve warnings and boundaries; acknowledge with HANDOFF_OK."
    )
    return {
        "task_id": safe_task_id(original["task_id"] + "-shared-handback"),
        "caller": original.get("caller", "codex"),
        "target": target,
        "role": "analyst",
        "mode": "read_only",
        "worktree": str(worktree),
        "base_commit": git_head(worktree),
        "session": "shared",
        "shared_app_idle_confirmed": True,
        "workflow": {
            "id": workflow.get("id", original["task_id"]),
            "phase": "analyze",
            "iteration": int(workflow.get("iteration", 1)) + 1,
            "review_of": result.get("head_commit") or original.get("base_commit"),
        },
        "routing": {"profile": "simple"},
        "queue": {"on_conflict": "wait", "timeout_s": 300, "poll_ms": 250},
        "budget": {"timeout_s": 600, "max_turns": 40},
        "prompt": prompt,
    }


def execute_run(args: argparse.Namespace) -> int:
    envelope_path = args.envelope.expanduser().resolve()
    original = load_envelope(envelope_path)
    preflight = None if args.no_preflight else run_preflight(envelope_path)
    command = [str(envelope_path)]
    if args.queue:
        command.append("--queue")
    if args.live_text:
        command.append("--live-text")
    code, stdout, stderr = call_dispatcher(command, live_stderr=args.live_text)
    if stderr:
        print(stderr, file=sys.stderr, end="")
    primary = parse_json(stdout, "dispatcher")
    handback = None
    handback_required = bool(
        (primary.get("session_visibility") or {}).get("shared_handoff_required"))
    if args.auto_handback and handback_required:
        if not args.shared_idle_confirmed:
            handback = {
                "status": "pending_human_idle_confirmation",
                "reason": "registered App shared idleness is not observable; rerun with a fresh human confirmation",
            }
        else:
            envelope = make_handback_envelope(original, primary)
            with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", prefix="agent-dispatch-handback-",
                    encoding="utf-8", delete=False) as stream:
                json.dump(envelope, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                handback_path = Path(stream.name)
            try:
                handback_preflight = run_preflight(handback_path)
                handback_args = [str(handback_path), "--queue"]
                if args.live_text:
                    handback_args.append("--live-text")
                hb_code, hb_stdout, hb_stderr = call_dispatcher(
                    handback_args, live_stderr=args.live_text)
                if hb_stderr:
                    print(hb_stderr, file=sys.stderr, end="")
                handback = {
                    "preflight": handback_preflight,
                    "result": parse_json(hb_stdout, "handback"),
                    "exit_code": hb_code,
                }
            finally:
                handback_path.unlink(missing_ok=True)
    output = {
        "wrapper_status": "ok" if code == 0 else "primary_failed",
        "preflight": preflight,
        "primary": primary,
        "handback": handback,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if code != 0:
        return code
    if handback and handback.get("status") == "pending_human_idle_confirmation":
        return 20
    if handback and handback.get("exit_code", 0) != 0:
        return int(handback["exit_code"])
    return 0


def add_make_envelope(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("make-envelope", help="Create a validated-shape envelope")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--caller", choices=("codex", "claude"), required=True)
    parser.add_argument("--target", choices=("codex", "claude"), required=True)
    parser.add_argument("--role", choices=("implementer", "reviewer", "analyst", "recorder"), required=True)
    parser.add_argument("--mode", choices=("read_only", "write", "verify"), required=True)
    parser.add_argument("--phase", choices=("implement", "review", "revise", "analyze", "record"), required=True)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--review-of")
    parser.add_argument("--profile", choices=("simple", "standard", "critical"), default="standard")
    parser.add_argument("--session", choices=("auto", "shared", "task", "fresh", "project"), default="auto")
    parser.add_argument("--session-isolation-reason")
    parser.add_argument("--shared-idle-confirmed", action="store_true")
    parser.add_argument("--allowed-path", action="append", default=[])
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--prompt-file", type=Path)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--max-turns", type=int, default=100)


def execute_make_envelope(args: argparse.Namespace) -> int:
    worktree = args.worktree.expanduser().resolve()
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    workflow: Dict[str, Any] = {
        "id": safe_task_id(args.task_id + "-workflow"),
        "phase": args.phase,
        "iteration": args.iteration,
    }
    if args.review_of:
        workflow["review_of"] = args.review_of
    envelope: Dict[str, Any] = {
        "task_id": safe_task_id(args.task_id),
        "caller": args.caller,
        "target": args.target,
        "role": args.role,
        "mode": args.mode,
        "worktree": str(worktree),
        "base_commit": git_head(worktree),
        "session": args.session,
        "workflow": workflow,
        "routing": {"profile": args.profile},
        "queue": {"on_conflict": "wait", "timeout_s": 900, "poll_ms": 250},
        "budget": {"timeout_s": args.timeout, "max_turns": args.max_turns},
        "prompt": prompt.strip(),
    }
    if args.allowed_path:
        envelope["allowed_paths"] = args.allowed_path
    if args.shared_idle_confirmed:
        envelope["shared_app_idle_confirmed"] = True
    if args.session_isolation_reason:
        envelope["session_isolation_reason"] = args.session_isolation_reason
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output),
                      "envelope": envelope}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--worktree", type=Path, required=True)

    subparsers.add_parser(
        "selftest", help="Run a zero-cost dispatcher test with a temporary Git repo and stub CLI")

    status = subparsers.add_parser("status")
    status.add_argument("worktree", type=Path)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("envelope", type=Path)

    run = subparsers.add_parser("run")
    run.add_argument("envelope", type=Path)
    run.add_argument("--queue", action="store_true")
    run.add_argument("--live-text", action="store_true")
    run.add_argument("--no-preflight", action="store_true")
    run.add_argument("--auto-handback", action="store_true")
    run.add_argument("--shared-idle-confirmed", action="store_true")

    register = subparsers.add_parser("register-shared")
    register.add_argument("worktree", type=Path)
    register.add_argument("target", choices=("codex", "claude"))
    register.add_argument("session_id")
    register.add_argument("cwd", type=Path)

    add_make_envelope(subparsers)
    args = parser.parse_args()

    if args.command == "make-envelope":
        return execute_make_envelope(args)
    if args.command == "run":
        return execute_run(args)
    if args.command == "selftest":
        code, stdout, stderr = call_dispatcher(["--selftest"])
        if stderr:
            print(stderr, file=sys.stderr, end="")
        # Fail closed if a corrupted dispatcher stops honoring the JSON contract.
        parse_json(stdout, "selftest")
        print(stdout, end="")
        return code
    if args.command == "doctor":
        worktree = args.worktree.expanduser().resolve()
        dispatcher = locate_dispatcher()
        common_dir = git_common_dir(worktree)
        code, stdout, stderr = call_dispatcher(["--status", str(worktree)])
        status_value = parse_json(stdout, "status") if stdout.strip() else None
        print(json.dumps({
            "status": "ok" if code == 0 else "failed",
            "dispatcher": str(dispatcher),
            "worktree": str(worktree),
            "head": git_head(worktree),
            "git_common_dir": str(common_dir),
            "agent_call_depth": os.environ.get("AGENT_CALL_DEPTH"),
            "runtime_status": status_value,
            "launcher_requirements": {
                "git_runtime_write": (
                    f"the top-level launcher must permit dispatcher writes under {common_dir}"),
                "nested_target_auth": (
                    "the nested target CLI must retain access to its ordinary authentication"),
                "observation_boundary": (
                    "doctor reports requirements and paths only; it does not mutate files or "
                    "claim that an OS sandbox or credential store is accessible"),
            },
            "stderr": stderr or None,
        }, ensure_ascii=False, indent=2))
        return code
    if args.command == "status":
        code, stdout, stderr = call_dispatcher(["--status", str(args.worktree.resolve())])
    elif args.command == "preflight":
        code, stdout, stderr = call_dispatcher(["--preflight", str(args.envelope.resolve())])
    else:
        code, stdout, stderr = call_dispatcher([
            "--register-shared", str(args.worktree.resolve()), args.target,
            args.session_id, str(args.cwd.resolve())])
    if stderr:
        print(stderr, file=sys.stderr, end="")
    print(stdout, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
