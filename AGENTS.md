# AGENTS.md

## What this repo is

relaybot lets a personal agent (built for Grok Bot) dispatch coding tasks to Codex running on the user's
own computer and get the result back over a webhook: run in the right repo clone, show the session in the
Codex desktop app, report `done` / `failed` / `needs_auth` with Codex's final reply, and resume the same session after
the user approves. Claude Code support is planned, not implemented.

## Layout

- `bin/codex-run`: entry point (bash). `codex-run <bot> <workdir|-> <task_file> [resume]`.
- `bin/codex-app-run`: Codex app-server client (python3); desktop-visible threads, project pick, IPC refresh.
- `bin/codex-notify`: webhook poster with per-pause dedupe (python3).
- `bin/codex-relay-hook`: codex-run's turn-status resolver and pause recorder (not a Codex hook; relaybot passes no hooks).
- `bin/relaybot-doctor`: read-only self-check.
- `skills/codex`, `skills/codex-setup`: agent skills (SKILL.md with YAML frontmatter).
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

In `~/.config/relaybot/config.env` or the environment: `RELAYBOT_CODEX_BIN`, `RELAYBOT_MODEL`,
`RELAYBOT_EFFORT`, `RELAYBOT_SANDBOX`, `RELAYBOT_DEFAULT_WORKDIR`, `RELAYBOT_PROJECT_FALLBACK_ROOT`,
`RELAYBOT_REPOS_ROOT`, `RELAYBOT_RUN_ROOT`, `RELAYBOT_EXTRA_PATH`, `RELAYBOT_PYTHON`,
`RELAYBOT_CLIENT_NAME`, `RELAYBOT_MAX_SECONDS`; env only: `RELAYBOT_HOME`, `RELAYBOT_FORCE_EXEC`.
Webhooks: `~/.config/relaybot/webhooks/<slug>.json` = `{url, key, bot}` (mode 600, never commit).

## Self-check

```bash
relaybot-doctor                    # install check
relaybot-doctor --webhook-test <slug>
tests/selftest.sh                  # offline e2e
bash -n bin/codex-run && for f in bin/codex-app-run bin/codex-notify bin/codex-relay-hook; do python3 -m py_compile "$f"; done
```

## Rules for agents changing this repo

- Never commit webhook files, keys, tokens, personal paths, or machine names. Use `examples/` placeholders.
- Keep scripts dependency-free (bash + python3 stdlib) and bash 3.2 compatible (macOS).
- Codex must see the task verbatim: do not append rules or markers to `prompt.md` or pass Codex hooks; derive status from system signals (exit, app-server requests) only.
- The desktop IPC refresh is undocumented and best-effort: never make a run fail because of it.
- Run `tests/selftest.sh` and shellcheck before committing.
