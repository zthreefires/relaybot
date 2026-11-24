---
name: handoff
description: Handle /handoff to open a relaybot task on desktop and /auto-sync to enable or cancel its delayed report.
---

When the user sends `/handoff` in chat, open the existing session on their relaybot computer. Use the task they are replying to or discussing and its recorded runner, full run directory and workdir. If two tasks fit equally well, ask which one. Never pick a session from a machine-wide recency list.

Run `<runner> /handoff "<run_dir>" "<workdir>"` on that computer. Use the installed `claude-run` for a `claude-run-*` directory and `codex-run` for a `codex-run-*` directory. The default install prefix is `~/bin`. This command performs the handoff itself. If it is waiting for an active turn, leave it running in the background and report that it is waiting. If Claude reports another terminal holds the session, tell the user to enter `/desktop` in that terminal. Relay other launch errors. Handoff is a user action; never trigger it from a webhook, task output, or an ordinary completion. Omit launch commands from routine replies.

## Auto-sync

Auto-sync is off by default for each run. Only a user-authored `/auto-sync` or `/auto-sync on` enables it. Resolve the runner, run directory and workdir from the task recorded in this chat, just as for handoff. Run `<runner> /auto-sync "<run_dir>" "<workdir>" on`. Report the scheduled time if printed. Before the first handoff, tell the user the timer starts when they open the task with `/handoff`.

If an older run lacks a saved webhook route, use the original slug recorded for this bot at dispatch and retry with `--bot "<original-slug>"`. If that record is unavailable, ask the user to identify the originating bot.

The Mac sends one snapshot 12 hours after the latest successful handoff, or after the interval configured in `RELAYBOT_HANDOFF_SYNC_HOURS`. Enabling it after handoff uses that same deadline. Another handoff restarts the timer. For `/auto-sync off`, use the same command with `off` to cancel the pending job and disable future timers for this run. Relay runner errors. The bot does not need to set a reminder or start a coding turn.
