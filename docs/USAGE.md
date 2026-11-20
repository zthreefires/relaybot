# Usage

## /relaybot-setup (once per bot)

Send `/relaybot-setup` in the dispatching bot's chat. In one run it checks whether Codex and Claude Code are installed and signed in, then sends a test through their shared webhook. Once the test arrives, the bot tells you which CLI or CLIs on this computer will send results back to this chat.

If one CLI is missing, install it or set its binary path in relaybot's config. If signed out, run `codex login` or `claude auth login` yourself. The other CLI can be used as soon as its checks and the webhook test pass.

Setup looks for both `relaybot-events` and the legacy `codex-events`. It reuses the existing routine and its `~/.config/relaybot/webhooks/<slug>.json` (mode 600). Legacy routines keep their name and prompt. Only a bot with neither routine gets a new `relaybot-events`. When credentials are needed, setup asks for the URL and collects the key through a secret request. Rerun the same command after fixing a CLI. Both routes keep the existing slug and key. Bots with the compatibility skill installed also accept `/codex-setup`.

## /codex (each task)

```
/codex add a --dry-run flag to the export command in example-repo, with a test
```

The bot:

1. picks the working dir: the folder you named, else the existing clone under `RELAYBOT_REPOS_ROOT`,
   else asks; tasks tied to no project go to the default workdir;
2. writes the full prompt from what it knows and starts `codex-run` in the background;
3. tells you it started. The thread is visible in the Codex desktop sidebar, under the matching project,
   titled `[<bot>] <first line>`. Don't type into it while it runs.

When the turn ends, one event comes back and the bot reads Codex's final reply: it reports what Codex
did, or relays the question Codex asked or what is blocking it, and includes `codex resume <id>`. If the
app-server asked for an approval or your input during the turn (`needs_auth`), the bot tells you what
was needed. After you answer or agree, the bot resumes the same session with your reply. relaybot adds
nothing to the prompt Codex sees, so the thread reads like a task you typed and you can continue it in
the desktop by hand.

## /claude (each task)

```text
/claude summarize the changes in example-repo and list the tests that cover them
```

Use the same bot, webhook and workdir selection as for `/codex`. The bot starts `claude-run`. Claude Code runs in CLI print mode. An approval or structured question produces `needs_auth` and the bot relays the request. After you respond, it passes your text to a new turn in that session. If the tool still needs interactive approval, open `claude --resume <id>` in the original directory. A question in ordinary reply text can arrive as `done`. The bot reads it and waits for your answer.

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

At a Git worktree root the app-server reuses a matching project or creates one with the folder name. A linked worktree (`git worktree add`, or Codex's `~/.codex/worktrees/*/<repo>`) with no exact-root project uses the main repository's project, creating it for the main root (named after the main folder) if none exists; the thread's cwd stays the worktree. A worktree subdirectory or a non-Git folder uses the fallback project. Configure its root with `RELAYBOT_PROJECT_FALLBACK_ROOT`. A project creation error is logged in `log.txt` and the task continues.

Keep the full `run_dir` from the summary. Resume snapshots `followup.md` and requires the original ID in `session`. If the ID is missing, recover it from the original log before retrying. An unreadable input or busy run leaves the prior turn usable. During a valid resume, `last.md` can be absent until a fresh reply is published.

The last output line is `run_dir=... exit=... session=... status=...`, with status `done`, `needs_auth` or `failed`. `done` and `needs_auth` return 0. A runner failure keeps its nonzero exit code; a clean exit with no final reply is `failed` with exit 1. The webhook event carries the same status plus the reply; see [the event contract](ARCHITECTURE.md#webhook-events).

Configure the final webhook URL directly. The receiver must return 2xx. A redirect or delivery error queues the event in `outbox.jsonl`. Check the queue for delivery issues before considering another task launch.
