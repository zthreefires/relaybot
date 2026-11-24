---
name: claude
description: Use for /claude, for /handoff on a Claude task, when the user explicitly chooses local Claude Code, or for any follow-up on a task already running in Claude Code.
---

Load the `codex` skill and follow its Dispatch and Resume instructions, using `claude-run` for every turn.
For a user message of `/handoff`, load the `handoff` skill.
Do not invoke the `claude` CLI directly because it bypasses the webhook callback.

New and resumed tasks inherit local Claude permissions. The runner adds `--dangerously-skip-permissions` only with an explicit `RELAYBOT_CLAUDE_SKIP_PERMISSIONS=1`. For a permission question, use the codex skill’s **Claude permission choice** instructions. If asked which mode a turn used, check Claude's `permissionMode` entry for that turn in the run's `log.txt`. Report a permission stop when the runner returns `needs_auth` with that reason.
