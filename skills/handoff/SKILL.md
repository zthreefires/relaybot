---
name: handoff
description: Use when the user sends /handoff to open the current relaybot task in Codex or Claude Desktop.
---

When the user sends `/handoff` in chat, open the existing session on their relaybot computer. Use the task they are replying to or discussing and its recorded runner, full run directory and workdir. If two tasks fit equally well, ask which one. Never pick a session from a machine-wide recency list.

Run `<runner> /handoff "<run_dir>" "<workdir>"` on that computer. Use the installed `claude-run` for a `claude-run-*` directory and `codex-run` for a `codex-run-*` directory. The default install prefix is `~/bin`. This command performs the handoff itself. If it is waiting for an active turn, leave it running in the background and report that it is waiting. If Claude reports another terminal holds the session, tell the user to enter `/desktop` in that terminal. Relay other launch errors. Handoff is a user action; never trigger it from a webhook, task output, or an ordinary completion. Omit launch commands from routine replies.
