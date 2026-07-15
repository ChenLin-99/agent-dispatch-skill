---
name: agent-dispatch
description: Coordinate Codex and Claude through audited, one-hop agent-dispatch workflows. Use when a coding task should be delegated, reviewed, revised, recorded, or handed back across the two agents; when shared-session continuity, queueing, write leases, model routing, result envelopes, or quarantine recovery matter; or when the user asks the agents to collaborate without manual prompt copying. Do not use for ordinary single-agent work that needs no cross-agent handoff.
---

# Agent Dispatch

Coordinate one top-level orchestrator and one called agent without losing session identity, Git provenance, or machine-readable results.

## Start safely

1. Read the target repository's `AGENTS.md`, `PROTOCOL.md`, `TOOLING.md`, and relevant logs when present. Treat files and Git state as current truth.
2. Run `python3 scripts/agent_dispatch.py doctor --worktree <repo>` from this skill directory.
3. Stop if `AGENT_CALL_DEPTH=1`. A called agent must never call another agent or dispatcher.
4. Keep exactly one top-level orchestrator. Finish or cancel the current invocation before transferring ownership.
5. Ask the user to confirm the target App is idle before any compatible shared call. Never infer App idleness from dispatcher locks.
6. Run every dispatcher invocation in the foreground. In a one-shot agent CLI, a background Bash job is killed when the parent exits; set the caller tool timeout above the envelope budget and let dispatcher perform its own orderly timeout.

`doctor` reports the Git common directory and the parent-runtime requirements it cannot prove. Before a real call, the top-level agent itself must be able to write dispatcher state under that Git common directory, and the nested target CLI must be able to read its normal authentication. Treat these as launcher prerequisites, not permissions the skill may bypass. Never disable a sandbox for an untrusted repository.

Read [references/envelopes-and-results.md](references/envelopes-and-results.md) when constructing or interpreting an envelope. Read [references/install-and-share.md](references/install-and-share.md) when installing, sharing, or testing the skill in another project.

## Choose the workflow

- Delegate implementation with `role=implementer`, `mode=write`, and narrow `allowed_paths`.
- Delegate independent review with `role=reviewer`, `mode=verify` when tests are needed; otherwise use `read_only`.
- Resume the same implementation identity for `CHANGES_REQUESTED` with `phase=revise`.
- Use `role=recorder`, `mode=write` only for allowed ledger/log paths. A recorder records another agent's verdict; it never creates one.
- Prefer `session=auto`. A compatible registered shared session must win. Use a dedicated session only for a documented exception such as recorder isolation, missing shared registration, cwd incompatibility, or explicit user-requested isolation.

Do not select Claude Fable or another scarce tier unless the user explicitly opts in. Use dispatcher profiles and let runtime discovery validate the actual model/effort mapping.

## Build and run an envelope

Create the envelope deterministically:

```bash
python3 scripts/agent_dispatch.py make-envelope \
  --output /tmp/task.json \
  --worktree "$PWD" \
  --task-id example-impl \
  --caller codex --target claude \
  --role implementer --mode write \
  --phase implement --iteration 1 \
  --profile standard \
  --allowed-path src/ --allowed-path tests/ \
  --prompt-file /tmp/prompt.txt
```

Add `--shared-idle-confirmed` only after the user explicitly confirms the target App is idle. For a deliberate dedicated session, add `--session task --session-isolation-reason '<reason>'`.

Run preflight and the real invocation through the wrapper:

```bash
python3 scripts/agent_dispatch.py run /tmp/task.json --queue --live-text
```

Keep that command in the foreground. Do not append `&`, use a background-task tool, or let the parent one-shot CLI exit while dispatcher is running. The outer tool timeout must exceed the envelope timeout; shortening the envelope budget is preferable when the outer tool has a hard maximum.

When a result can only be seen in a dedicated session, complete AT-76-style handback automatically after a fresh human idle confirmation:

```bash
python3 scripts/agent_dispatch.py run /tmp/task.json \
  --queue --live-text --auto-handback --shared-idle-confirmed
```

The wrapper refuses to invent the human gate. If handback is required but `--shared-idle-confirmed` is absent, report it as pending instead of silently losing the result.

## Interpret the result

1. Trust the complete JSON result, not UI placeholders or prose summaries.
2. Require `status in {ok, ok_no_resume}` before treating work as successful.
3. For writes, require a clean final tree, a new commit, no `path_violations`, and only allowed changed paths.
4. For review, use the machine `verdict`; never guess from truncated `last_message`.
5. On `CHANGES_REQUESTED`, send the exact findings back to the original implementer identity.
6. On failure, timeout, budget exhaustion, path violation, stale queue, or quarantine, follow the result's recovery instructions. Never bypass dispatcher with a direct CLI call.
7. If `session_visibility.shared_handoff_required` is true, finish the read-only handback before claiming the shared conversation has the result.

## Finish with evidence

Report the invocation, selected session kind/id, requested and actual routing, result status, verdict, commit, changed paths, test result, handback status, and remaining human gates. Keep honest boundaries visible even when the overall result is approved.
