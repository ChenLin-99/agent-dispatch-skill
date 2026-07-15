# Install and share

## Contents

- Repository layout
- Project installation
- User installation
- GitHub sharing
- Fresh-agent test setup

## Repository layout

Keep the source tree intact:

```text
agent-dispatch-skill/
└── skill/agent-dispatch/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── bin/dispatch-agent
    ├── scripts/
    └── references/
```

The helper locates the dispatcher bundled inside the skill. Both symlink and standard GitHub skill installations therefore preserve zero-configuration discovery. `AGENT_DISPATCH_BIN` remains available only as an explicit development override.

## Project installation

From a clone of this repository:

```bash
python3 skill/agent-dispatch/scripts/install_skill.py --project /path/to/project
```

This links one source skill into both:

- `/path/to/project/.agents/skills/agent-dispatch` for Codex.
- `/path/to/project/.claude/skills/agent-dispatch` for Claude Code.

Codex officially scans `.agents/skills` from the current directory to the repository root and supports symlinked skill folders. Claude Code resolves the same open-agent `SKILL.md` through its project skill directory.

## User installation

Install for all projects owned by the current user:

```bash
python3 skill/agent-dispatch/scripts/install_skill.py --user
```

This links to `~/.agents/skills/agent-dispatch` and `~/.claude/skills/agent-dispatch`. Restart an already-open agent if the new skill does not appear.

## GitHub sharing

Yes: create a GitHub repository and push this complete project. Recipients can:

```bash
git clone https://github.com/OWNER/agent-dispatch.git
cd agent-dispatch
python3 skill/agent-dispatch/scripts/install_skill.py --user
```

For project-only use, replace `--user` with `--project /path/to/project`.

Direct GitHub clone is appropriate for source distribution and development. For polished one-click distribution to a wider ChatGPT/Codex workspace, package the skill and dispatcher as a plugin later; official Codex guidance recommends plugins for reusable distribution beyond one repository.

## Fresh-agent test setup

1. Create an empty Git repository with an initial commit.
2. Install the skill with `--project`.
3. Export `AGENT_DISPATCH_BIN` only if the skill was copied instead of linked.
4. Start a new Codex CLI session and a new Claude Code session from the project root.
5. Explicitly invoke `$agent-dispatch` or `/agent-dispatch` for the first smoke test.
6. Run `doctor` from each top-level launcher. Confirm that the launcher can write the reported Git common directory and that a nested target CLI retains its normal authentication. These are real parent-process prerequisites; the skill does not widen its own sandbox or credentials.
7. Keep dispatcher in the foreground with the outer tool timeout above the envelope budget. A background dispatcher is not durable after a one-shot agent process exits.
8. Keep one orchestrator active at a time. Test Codex→Claude, finish it, then transfer ownership and test Claude→Codex.
9. Verify Git commits, result envelopes, queue cleanup, and session identity from files rather than agent claims.

For a fresh shared-session smoke test, first start each agent normally in the project, capture its real session id, register it with `register-shared`, and verify the returned evidence. Registration does not establish App idleness; every shared call still needs a fresh human idle confirmation.
