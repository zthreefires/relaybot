---
name: self
description: Use when the user sends /self to have the bot handle this chat directly, or sends a follow-up while that choice is active.
---

When the first word of the user's message is the command `/self`, remember in this chat that the bot is now handling the work directly. For a bare command, confirm the switch in the user's language and wait. If the command includes a task, do it now with the bot's own tools.

Keep handling later requests yourself, including “continue” and replies to earlier Codex or Claude results. Leave existing runs to finish and report their events as usual. Only switch back to dispatch when the user sends `/codex` or `/claude`, or explicitly asks that agent to take the work. Then follow the `codex` skill for the selected agent.
