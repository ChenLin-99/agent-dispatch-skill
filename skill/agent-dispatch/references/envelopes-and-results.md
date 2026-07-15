# Envelopes and results

## Contents

- Envelope minimums
- Roles and modes
- Session policy
- Result decisions
- Failure recovery

## Envelope minimums

Every invocation needs:

```json
{
  "task_id": "bounded-slug",
  "caller": "codex",
  "target": "claude",
  "role": "implementer",
  "mode": "write",
  "worktree": "/absolute/repo",
  "base_commit": "full-or-short-sha",
  "allowed_paths": ["src/", "tests/"],
  "session": "auto",
  "workflow": {
    "id": "bounded-workflow",
    "phase": "implement",
    "iteration": 1
  },
  "routing": {"profile": "standard"},
  "queue": {"on_conflict": "wait", "timeout_s": 900, "poll_ms": 250},
  "budget": {"timeout_s": 2400, "max_turns": 100},
  "prompt": "Concrete task and acceptance criteria"
}
```

Use absolute worktrees and the current `HEAD`. Preflight is only a snapshot; the real run repeats every closing gate.

The caller's own launcher is outside the envelope contract. It must grant the dispatcher write access to the repository Git common directory used for `agent-runtime`, and it must leave the nested target CLI's ordinary authentication available. `doctor` can show the relevant paths and requirements but cannot prove OS sandbox or keychain access without causing side effects. A failed prerequisite must stop the workflow; never fall back to a direct business call.

## Roles and modes

| Phase | Role | Mode | Required evidence |
| --- | --- | --- | --- |
| implement | implementer | write | commit, clean tree, allowed paths, tests |
| review | reviewer | read_only or verify | zero repo changes, explicit verdict |
| revise | implementer | write | same implementation identity, review findings addressed |
| analyze | analyst | read_only or verify | facts separated from inference |
| record | recorder | write | only configured document paths, faithful verdict |

Use `verify` when the reviewer must run commands. It still forbids repository changes.

## Session policy

- `auto`: shared-first. If a compatible registered shared exists, a human idle confirmation is mandatory.
- `shared`: explicitly require registered shared; never fall back to fresh.
- `task` or `fresh`: exceptional dedicated identity. Supply `session_isolation_reason` when shared exists.
- `recorder`: always dedicated by policy, then hand the result back to shared.

Dispatcher locks coordinate dispatcher calls, not the open App. Never claim that a lock proves App idleness.

## Result decisions

Treat these fields as the contract:

- `status`: dispatcher outcome.
- `session_decision`: why shared or dedicated was selected.
- `session_visibility`: whether the registered App shared can see the result.
- `verdict`: only valid for successful review and only from the final non-empty line.
- `changed_paths` and `path_violations`: post-run Git audit.
- `target_errors`, `target_errors_observation`, and `attempt_paths`: target warnings with attempt provenance.
- `queue_audit`: waiting history and final state.
- `actual_model`, `actual_effort`, and observation fields: measured routing when available; explicit unavailable otherwise.

Decision order:

1. Reject non-success status.
2. Enforce path and commit contracts.
3. Parse review verdict.
4. Continue revise or record.
5. Perform shared handback when required.
6. Report remaining human gates.

## Failure recovery

- `rejected_worktree`: clean or commit only the owner's known changes, then rebuild the envelope with current `HEAD`.
- `rejected_stale_queue`: rebuild with the new base after inspecting the preceding writer.
- `budget_exhausted` in write/verify: inspect artifacts, then use audited human force-release before resuming.
- `timeout`, `interrupted`, `paths_violation`, or quarantine: inspect `--status` and the result directory. Do not auto-release.
- failed shared resume: stop. Do not create a fresh session that hides context loss.
- dispatcher failure: never fall back to a direct Claude or Codex CLI business call.
- parent one-shot CLI exits: never background dispatcher. Run it in the foreground with an outer tool timeout longer than the envelope budget; otherwise the parent can SIGTERM the whole process group and correctly leave quarantine.
