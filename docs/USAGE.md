# Usage

## /relaybot-setup (once per bot)

Send `/relaybot-setup` in the dispatching bot's chat. In one run it checks whether Codex and Claude Code are installed and signed in, then sends a test through their shared webhook. Once the test arrives, the bot tells you which CLI or CLIs on this computer will send results back to this chat.

If one CLI is missing, install it or set its binary path in relaybot's config. If signed out, run `codex login` or `claude auth login` yourself. The other CLI can be used as soon as its checks and the webhook test pass.

Setup looks for both `relaybot-events` and the legacy `codex-events`. It reuses the existing routine and its `~/.config/relaybot/webhooks/<slug>.json` (mode 600). Legacy routines keep their name and prompt. Only a bot with neither routine gets a new `relaybot-events`. When credentials are needed, setup asks for the URL and collects the key through a secret request. Rerun the same command after fixing a CLI. Both routes keep the existing slug and key.

## /codex (each task)

```
/codex add a --dry-run flag to the export command in example-repo, with a test
```

The bot:

1. picks the working dir: the folder you named, else the existing clone under `RELAYBOT_REPOS_ROOT`,
   else asks; tasks tied to no project go to the default workdir;
2. writes the full prompt from what it knows and starts `codex-run` in the background, passing `--worktree <branch>` when the task needs an isolated checkout;
3. tells you it started. The Codex desktop thread is titled `[<bot>] <first line>`.
   Wait for the run to finish before writing to it.

When the turn ends, one event comes back and the bot reads Codex's final reply: it reports what Codex
did, or relays the question Codex asked or what is blocking it. If the
app-server asked for an approval or your input during the turn (`needs_auth`), the bot tells you what
was needed. The bot records the full `run_dir` and session ID in chat after each launch. Answers, review
fixes, extra tests and later changes to the same task in the same workdir resume its session by default.
An independent read-only review can use its own session and resume it for later review rounds. relaybot adds
nothing to the prompt Codex sees, so the thread reads like a task you typed and you can continue it in
the desktop by hand.

## /claude (each task)

```text
/claude summarize the changes in example-repo and list the tests that cover them
```

Use the same bot, webhook and workdir selection as for `/codex`. The bot starts `claude-run`. Claude Code runs in CLI print mode with its local permission settings. When an ordinary tool approval blocks the task, the bot reports the operation and offers a choice for every Claude task using this relaybot installation. Choose **Yes, skip future prompts and continue** to save `RELAYBOT_CLAUDE_SKIP_PERMISSIONS=1` and resume this task once in the same session. Choose **No, keep local permissions** to save `0` and leave this task paused. Later approval requests still reach the bot. While the question is unanswered, new tasks continue with local permissions. You can change the key later in `config.env`. An approval or structured question produces `needs_auth` and the bot relays the request. After you respond, it passes your text to a new turn in that session. If the tool still needs interactive approval, open `claude --resume <id>` in the original directory. A question in ordinary reply text can arrive as `done`. The bot reads it and waits for your answer.

## Open the current task on desktop

Send `/handoff` in the bot chat. The bot opens the Codex thread or the Claude Desktop Code session for the task you are discussing. With multiple possible tasks, reply to the result you want. Regular results carry the session ID as metadata and open the desktop only on your request.

The local command is `<runner> /handoff "<run_dir>" "<workdir>"`, using the runner that created the task. Codex opens its thread link. Claude waits for the relaybot turn to exit, then runs `claude --desktop --resume <session_id>` in the original workdir. If an interactive Claude terminal still owns the session, use `/desktop` there. On macOS, Claude handoff requires Claude Desktop and Claude Code 2.1.285 or later signed in with a Claude subscription. [Claude Desktop session handoff](https://code.claude.com/docs/en/desktop#desktop-vs-cli)

## Sync desktop progress

Auto-sync is on by default. Each successful `/handoff` on the Mac schedules one update 12 hours later. Another handoff restarts the timer. Send `/auto-sync off` in the originating chat to cancel the pending job and disable future timers for that run. Send `/auto-sync on` (or just `/auto-sync`) to re-enable that run. Re-enabling uses the latest handoff's deadline. An overdue update runs immediately.

Set `RELAYBOT_HANDOFF_AUTO_SYNC=0` in `config.env` to disable automatic scheduling and delivery for all runs. Pending jobs recheck the setting before sending. After switching back to `1`, the next handoff schedules a timer for an enabled run. To schedule an existing handoff, send `/auto-sync on`. An explicit environment setting on the runner takes precedence over the file for that handoff and its job. Runs saved as off by earlier versions keep that preference until you send `/auto-sync on`.

```bash
codex-run /handoff "$run_dir" "$workdir"
codex-run /sync "$run_dir"                    # request a snapshot now
codex-run /auto-sync "$run_dir" "$workdir" off
codex-run /auto-sync "$run_dir" "$workdir" on
```

Use `claude-run` for a Claude task. Manual `/sync` works after handoff, including when auto-sync is off. Each manual request sends a fresh snapshot and keeps any automatic timer. The report contains the visible reply from each new turn, or the latest available progress if the last turn is still open. A quiet session sends a no-progress event. An inaccessible transcript produces a read-error report.

Set `RELAYBOT_HANDOFF_SYNC_HOURS` in `config.env` to a positive number of hours, including fractional hours. Automatic scheduling uses the logged-in user's macOS LaunchAgents and fires with minute precision. A missed deadline is checked on wake or login. Keep the run directory and local transcript until then. If your system clears `/tmp` on reboot, configure a persistent `RELAYBOT_RUN_ROOT` before dispatch. For a run created before this feature, append `--bot "<original-slug>"` to `/auto-sync on` or the manual `/sync` command if the route is missing. Use the bot recorded in the originating chat.

## Running the scripts by hand

```bash
echo "Summarize the README" > /tmp/task.md
codex-run my-bot ~/path/to/repo /tmp/task.md          # new run
codex-run my-bot - /tmp/task.md                         # default workdir
echo "Done, continue" > /tmp/codex-run-.../followup.md
codex-run my-bot ~/path/to/repo /tmp/codex-run-.../followup.md resume
claude-run my-bot ~/path/to/repo /tmp/task.md
echo "Use the first option" > /tmp/claude-run-.../followup.md
claude-run my-bot ~/path/to/repo /tmp/claude-run-.../followup.md resume
codex-notify my-bot test /tmp ~ "hello"                 # webhook test
```

At a Git worktree root the app-server reuses a matching project or creates one with the folder name. A linked worktree with no exact-root project uses the main repository's project ID. The thread's cwd stays the worktree. A worktree subdirectory or a non-Git folder uses the fallback project. Configure its root with `RELAYBOT_PROJECT_FALLBACK_ROOT`. A project creation error is logged in `log.txt` and the task continues.

If a sibling worktree's thread is missing from the desktop project, open `codex://threads/<session_id>` on the relaybot computer. To file that individual thread, use **Move to project** in the desktop and select the main repository. Check the proposed folders and the working directory before continuing there. The desktop can propose adding project folders or switching the thread to the main checkout.

Resume snapshots `followup.md` and requires the original ID in `session`. It must use the run's original bot slug and workdir (for a managed worktree, the main repo or the saved checkout), and the session recorded by the first turn. Otherwise the turn fails with `failure_kind: resume_mismatch` before the agent starts, and the run keeps its session. If the ID is missing, recover it from the original log before retrying. Report any failure. If the desktop holds the thread, ask the user to close it and retry the same ID. A replacement session requires the user's approval. An unreadable input or busy run leaves the prior turn usable. During a valid resume, `last.md` can be absent until a fresh reply is published.

The runner prints `started run_dir=...` before dispatch so the bot can identify an active task for handoff. The last output line is `run_dir=... exit=... session=... status=...`, with status `done`, `needs_auth` or `failed`. `done` and `needs_auth` return 0. A runner failure keeps its nonzero exit code; a clean exit with no final reply is `failed` with exit 1. `status.json` and the webhook also carry `outcome` (`done`, `needs_auth`, `interrupted` or `failed`), a `failure_kind` for failures (for example `cli_missing`, `auth`, `timeout`, `resume_mismatch`), and the turn's `turn_id` and `turn_seq`. Each turn's reply stays in `turn-*/last.md`; a stopped or failed turn keeps its partial text in `turn-*/partial.md`. Stopping the runner with TERM, INT or HUP ends the turn as `interrupted` and still sends its event. See [the event contract](ARCHITECTURE.md#webhook-events).

Configure the final webhook URL directly. The receiver must return 2xx. A redirect or delivery error queues the event in `outbox.jsonl`. Each turn records its delivery in `turn-*/delivery.json` (mirrored as `delivery` in `status.json`). To deliver it again without rerunning the task:

```bash
codex-run /resend /tmp/codex-run-...            # current turn; refuses if already delivered
claude-run /resend /tmp/claude-run-... turn-... --force   # a specific turn, even if delivered
```

## Isolated Codex tasks

Pass the main checkout root and a local branch name. Git checks out an existing branch at its tip, or creates a new branch at the main checkout's current `HEAD`. Uncommitted files in the main checkout stay there. A branch already in use in another checkout produces a failed run.

```bash
codex-run my-bot ~/path/to/repo /tmp/task.md --worktree feature/export
# Use run_dir from the launch summary or webhook.
cat "$run_dir/worktree"
echo "Add the regression test" > "$run_dir/followup.md"
codex-run my-bot ~/path/to/repo "$run_dir/followup.md" resume
```

The checkout lives under `$CODEX_HOME/worktrees` (normally `~/.codex/worktrees`). The event's `workdir` gives its absolute path. Resume accepts either the original main root or this checkout. Each launch starts a fresh app-server and checks the returned cwd before sending the prompt. If the saved checkout was removed or belongs to another thread, resume fails. Keep the worktree while follow-ups are pending.

Relaybot uses the default Codex directory layout. Desktop-specific setup scripts, copying ignored files through `.worktreeinclude`, and the desktop's custom worktree-root setting apply to desktop-created worktrees. [Implementation and verification](ARCHITECTURE.md#managed-worktree-creation)
