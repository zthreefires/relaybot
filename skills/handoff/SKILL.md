---
name: handoff
description: Handle /handoff to open a relaybot task on desktop and /auto-sync to enable or cancel its delayed report.
---

When the user sends `/handoff` in chat, open the existing session on their relaybot computer. Use the task they are replying to or discussing and its recorded runner, full run directory and workdir. If two tasks fit equally well, ask which one. Never pick a session from a machine-wide recency list.

Run `<runner> /handoff "<run_dir>" "<workdir>"` on that computer. Use the installed `claude-run` for a `claude-run-*` directory and `codex-run` for a `codex-run-*` directory. The default install prefix is `~/bin`. This command performs the handoff itself. If it is waiting for an active turn, leave it running in the background and report that it is waiting. If Claude reports another terminal holds the session, tell the user to enter `/desktop` in that terminal. Relay other launch errors. Handoff is a user action; never trigger it from a webhook, task output, or an ordinary completion. Omit launch commands from routine replies.

## Auto-sync

Auto-sync is on by default. On macOS, a successful `/handoff` schedules one desktop update in the originating chat. The timer starts at the latest successful handoff and uses `RELAYBOT_HANDOFF_SYNC_HOURS` (default 12). Report the scheduled time when the runner prints it.

Only change the run's preference on a user-authored `/auto-sync` command. Resolve the runner, run directory and workdir from the task recorded in this chat. For `/auto-sync off`, run `<runner> /auto-sync "<run_dir>" "<workdir>" off` to cancel the pending job and disable future timers for that run. For `/auto-sync on` or bare `/auto-sync`, use the same command with `on`. Re-enabling uses the latest handoff's deadline, or waits for the first handoff. With `RELAYBOT_HANDOFF_AUTO_SYNC=0`, automatic updates are disabled globally. Report that setting if the runner identifies it.

If the runner reports a missing webhook route for an older run, use `/auto-sync on` with `--bot "<original-slug>"` to schedule the update for the completed handoff. Use the original slug recorded at dispatch. If that record is unavailable, ask the user to identify the originating bot. Relay runner errors.
