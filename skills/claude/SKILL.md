---
name: claude
description: Use for /claude or when the user explicitly chooses local Claude Code for a task.
---

Load the `codex` skill and follow its Dispatch and Resume instructions, using `claude-run` for every turn.
Do not invoke the `claude` CLI directly because it bypasses the webhook callback.
