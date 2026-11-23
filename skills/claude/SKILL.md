---
name: claude
description: Use for /claude or when the user explicitly chooses local Claude Code for a task.
---

Load the `codex` skill and follow its Dispatch and Resume instructions, using `claude-run` for every turn.
Do not invoke the `claude` CLI directly because it bypasses the webhook callback.

`claude-run` adds `--dangerously-skip-permissions` by default for both new tasks and resumes. The operator can opt out with `RELAYBOT_CLAUDE_SKIP_PERMISSIONS=0`. If asked which mode a turn used, check Claude's `permissionMode` entry for that turn in the run's `log.txt`. Report a permission stop when the runner returns `needs_auth` with that reason.
