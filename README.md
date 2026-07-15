# Agent Dispatch Skill

Install one skill that lets **Codex and Claude coordinate through audited task envelopes** instead of asking you to copy prompts between them.

This is a minimal installation repository. It contains only the skill, its required dispatcher, and issue-reporting metadata—no development logs or project ledger.

## Requirements

- macOS or Linux
- Python 3.9+
- Git
- Installed and authenticated Codex CLI and Claude Code CLI

## Install for your user

From Codex, the standard GitHub skill installer can install the self-contained skill directly:

```text
$skill-installer install https://github.com/ChenLin-99/agent-dispatch-skill/tree/main/skill/agent-dispatch
```

To install the same source for both Codex and Claude Code, clone the repository and run its installer:

```bash
git clone https://github.com/ChenLin-99/agent-dispatch-skill.git
cd agent-dispatch-skill
python3 skill/agent-dispatch/scripts/install_skill.py --user
```

This installs the same source skill for both agents:

- `~/.agents/skills/agent-dispatch` for Codex
- `~/.claude/skills/agent-dispatch` for Claude Code

Restart an already-open agent if the skill does not appear.

## Install for one project

```bash
python3 skill/agent-dispatch/scripts/install_skill.py --project /absolute/path/to/project
```

The project receives links under `.agents/skills/` and `.claude/skills/`. The installer refuses to overwrite unrelated files or symlinks.

## Zero-cost selftest

From the installed skill directory, run:

```bash
python3 scripts/agent_dispatch.py selftest
```

The selftest uses a temporary Git repository and fixed local stub. It needs no network, authentication, model quota, or App-idle confirmation. Require exit code 0, top-level `status: ok`, and every reported check to be true.

Then inspect a real target repository without launching another agent:

```bash
python3 scripts/agent_dispatch.py doctor --worktree /absolute/path/to/project
```

Invoke the skill explicitly for the first real run:

- Codex: `$agent-dispatch coordinate this task with Claude`
- Claude Code: `/agent-dispatch ask Codex to review this change`

Foreground execution is the portable default. Do not assume plain `&` is durable. Use background execution only when the exact launcher documents durable jobs or passes the harmless survival probe in [`install-and-share.md`](skill/agent-dispatch/references/install-and-share.md), and monitor it through a terminal result.

The skill prefers compatible registered shared sessions, requires explicit confirmation that the target App is idle, preserves the one-hop guard, and records Git/session/result evidence. It does not silently bypass dispatcher after a failure.

## Important boundary

This is a trusted-agent coordination tool, not an operating-system sandbox for hostile code. Do not weaken a sandbox or copy credentials merely to make a nested call work. Read [`skill/agent-dispatch/SKILL.md`](skill/agent-dispatch/SKILL.md) for the complete workflow and safety rules.

## Report a problem

Open an issue: <https://github.com/ChenLin-99/agent-dispatch-skill/issues/new/choose>

Please remove tokens, credentials, private prompts, and sensitive paths before attaching envelopes or logs.

## License

No open-source license has been selected yet. Public availability does not by itself grant reuse or redistribution rights.

## 中文

这是一个只用于安装的最小分发仓库，只包含 `agent-dispatch` skill、必需的 dispatcher 和 issue 模板，不包含开发日志与项目台账。安装后，Codex 与 Claude 可以通过受审计信封互相委派实现、复审和修订任务，不需要用户手工复制提示词。
