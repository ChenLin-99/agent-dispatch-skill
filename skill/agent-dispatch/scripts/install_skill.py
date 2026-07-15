#!/usr/bin/env python3
"""Install the agent-dispatch skill for Codex and Claude from one source."""

import argparse
import json
import os
import shutil
from pathlib import Path


SKILL_NAME = "agent-dispatch"


def dispatcher_hint(source: Path) -> str:
    """Prefer a dispatcher bundled inside a standalone downloaded skill.

    Development clones keep the canonical binary at the repository root. A
    GitHub skill installer, however, downloads only the skill directory, so a
    distribution build may place the same binary at ``source/bin``.
    """
    candidates = [source / "bin" / "dispatch-agent"]
    candidates.extend(parent / "bin" / "dispatch-agent" for parent in source.parents)
    return str(next((candidate for candidate in candidates if candidate.is_file()),
                    "set AGENT_DISPATCH_BIN"))


def install_link(source: Path, destination: Path, copy_mode: bool) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() == source:
            return {"path": str(destination), "status": "already_installed", "mode": "symlink"}
        raise SystemExit(f"Refusing to replace unrelated symlink: {destination}")
    if destination.exists():
        raise SystemExit(f"Refusing to replace existing path: {destination}")
    if copy_mode:
        shutil.copytree(source, destination)
        mode = "copy"
    else:
        destination.symlink_to(source, target_is_directory=True)
        mode = "symlink"
    return {"path": str(destination), "status": "installed", "mode": mode}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--project", type=Path, help="Project root for repo-scoped installation")
    scope.add_argument("--user", action="store_true", help="Install for the current user")
    parser.add_argument("--copy", action="store_true",
                        help="Copy instead of symlink; copied installs may need AGENT_DISPATCH_BIN")
    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1]
    if not (source / "SKILL.md").is_file():
        raise SystemExit(f"Skill source is incomplete: {source}")

    if args.user:
        home = Path.home()
        destinations = [
            home / ".agents" / "skills" / SKILL_NAME,
            home / ".claude" / "skills" / SKILL_NAME,
        ]
        scope_name = "user"
    else:
        project = args.project.expanduser().resolve()
        if not project.is_dir():
            raise SystemExit(f"Project does not exist: {project}")
        destinations = [
            project / ".agents" / "skills" / SKILL_NAME,
            project / ".claude" / "skills" / SKILL_NAME,
        ]
        scope_name = "project"

    installed = [install_link(source, path, args.copy) for path in destinations]
    print(json.dumps({
        "status": "ok",
        "scope": scope_name,
        "source": str(source),
        "dispatcher_hint": dispatcher_hint(source),
        "installed": installed,
        "restart_if_missing": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
