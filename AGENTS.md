# AGENTS.md

## What this repo is

relaybot lets a personal agent (built for Grok Bot) dispatch coding tasks to Codex or Claude Code running on the user's
own computer, report `done` / `failed` / `needs_auth` over a webhook and resume the same session.
Codex app-server threads are visible in the desktop. Claude uses the local CLI.

## Layout

- `bin/codex-run`, `bin/claude-run`: shared bash launcher, selected by executable name. Explicit `/handoff` requests use `bin/desktop_handoff.py` to open the saved session.
- `bin/handoff_sync.py` manages per-run desktop snapshot state and optional launchd jobs. `bin/session_progress.py` reads the local session transcript.
- `bin/claude-stream-run`: Claude Code stream-json client (python3), including permission stops. `bin/claude_preference.py` coordinates the installation-wide permission question.
- `bin/codex-app-run`: Codex app-server client (python3); desktop-visible threads, project pick, IPC refresh.
- `bin/codex-notify`: webhook poster with per-pause dedupe (python3).
- `bin/codex-relay-hook`: shared turn-status resolver and pause recorder (not a Codex hook; relaybot passes no hooks).
- `bin/relaybot-doctor`: checks the install and each CLI's sign-in status. An explicit `--webhook-test` sends a test event.
- `skills/codex` dispatches to either runner. `skills/claude` uses that workflow with `claude-run` for `/claude`. `skills/handoff` opens the current task on the desktop and schedules a report by default. `skills/auto-sync` toggles reports for one run. `skills/relaybot-setup` checks both and wires one webhook per bot.
- `docs/ARCHITECTURE.md`: flow, run dir, event contract. `docs/INSTALL.md`, `docs/USAGE.md`,
  `docs/INSTALL_FOR_AGENTS.md`.
- `config.example.env`, `examples/`: sample config, webhook file, event, task, routine prompt.
- `tests/selftest.sh`: offline end-to-end test.

## Install

```bash
./install.sh [--prefix DIR]     # default ~/bin; idempotent
```

Full agent walkthrough: [docs/INSTALL_FOR_AGENTS.md](docs/INSTALL_FOR_AGENTS.md).

## Config keys

In `~/.config/relaybot/config.env` or the environment: `RELAYBOT_CODEX_BIN`, `RELAYBOT_CLAUDE_BIN`, `RELAYBOT_CLAUDE_SKIP_PERMISSIONS`, `RELAYBOT_MODEL`,
`RELAYBOT_EFFORT`, `RELAYBOT_SANDBOX`, `RELAYBOT_DEFAULT_WORKDIR`, `RELAYBOT_PROJECT_FALLBACK_ROOT`,
`RELAYBOT_REPOS_ROOT`, `RELAYBOT_RUN_ROOT`, `RELAYBOT_EXTRA_PATH`, `RELAYBOT_PYTHON`,
`RELAYBOT_CLIENT_NAME`, `RELAYBOT_MAX_SECONDS`, `RELAYBOT_HANDOFF_AUTO_SYNC`, `RELAYBOT_HANDOFF_SYNC_HOURS`; env only: `RELAYBOT_HOME`, `RELAYBOT_FORCE_EXEC`.
Webhooks: `~/.config/relaybot/webhooks/<slug>.json` = `{url, key, bot}` (mode 600, never commit).

## Self-check

```bash
relaybot-doctor                    # install check
relaybot-doctor --webhook-test <slug>
tests/selftest.sh                  # offline e2e
bash -n bin/codex-run && for f in bin/claude-stream-run bin/codex-app-run bin/codex-notify bin/codex-relay-hook; do python3 -m py_compile "$f"; done
```

## Rules for agents changing this repo

- Never commit webhook files, keys, tokens, personal paths, or machine names. Use `examples/` placeholders.
- Keep scripts dependency-free (bash + python3 stdlib) and bash 3.2 compatible (macOS).
- Both coding agents must see the task verbatim: do not append rules or markers to `prompt.md` or pass hooks; derive status from system signals (exit, Codex app-server requests, Claude stream frames) only.
- The desktop IPC refresh is undocumented and best-effort: never make a run fail because of it.
- Run `tests/selftest.sh` and shellcheck before committing.
