---
name: claude
description: Use for /claude, for /handoff on a Claude task, when the user explicitly chooses local Claude Code, or for follow-ups while Claude is selected in this chat.
---

Follow the `codex` skill's chat selection rules. Use its Dispatch and Resume instructions with `claude-run` while Claude is selected.
For a user message of `/handoff` or `/auto-sync [on|off]`, load the `handoff` skill. A successful Claude handoff schedules a desktop update by default. The `/auto-sync` command changes the preference for this run only.
Do not invoke the `claude` CLI directly because it bypasses the webhook callback.
A request for Claude to review another task, or to run alongside Codex, follows the codex skill's **Review and dual runs** section and does not select Claude.

New and resumed tasks inherit local Claude permissions. The runner adds `--dangerously-skip-permissions` only with an explicit `RELAYBOT_CLAUDE_SKIP_PERMISSIONS=1`. For a permission question, use the codex skill’s **Claude permission choice** instructions. If asked which mode a turn used, check Claude's `permissionMode` entry for that turn in the run's `log.txt`. Report a permission stop when the runner returns `needs_auth` with that reason.
