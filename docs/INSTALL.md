# Install

Requirements: macOS or Linux, `bash`, `python3` (3.8+), Codex CLI or the Codex/ChatGPT desktop app
(signed in), and a personal agent that can run shell commands on that computer and has webhook routines
(built for Grok Bot).

1. Clone and install the scripts (default prefix `~/bin`; re-running updates them):

   ```bash
   git clone https://github.com/zthreefires/relaybot.git
   cd relaybot
   ./install.sh                 # or ./install.sh --prefix ~/.local/bin
   ```

   This copies `codex-run`, `codex-app-run`, `codex-notify`, `codex-relay-hook`, `relaybot-doctor`,
   creates `~/.config/relaybot/` (mode 700) with `webhooks/`, and creates `config.env` from
   `config.example.env` if it does not exist.

2. Edit `~/.config/relaybot/config.env` (all optional): model, effort, default workdir, repos root,
   Codex binary. See [Configuration](#configuration).

3. In the Codex desktop app, create a project whose root is your default workdir
   (`RELAYBOT_DEFAULT_WORKDIR`, default `~/Documents/relaybot`). Unmatched non-repository workdirs can use this fallback. Git repository roots get their own project; a linked worktree without its own project goes under the main repository's project. A preexisting `~/Documents/codex-for-grok` project is preferred as fallback when both root settings are unset.

4. Check: `relaybot-doctor` (read-only). From a clone, `tests/selftest.sh` runs an offline end-to-end
   test with stub exec, app-server and webhook endpoints. Pass an installed prefix to test that copy, e.g. `tests/selftest.sh ~/bin`.

5. Install the skills into your agent: `skills/codex/SKILL.md` and `skills/codex-setup/SKILL.md`. Then,
   in each bot that should dispatch to Codex, send `/codex-setup` once.

## Configuration

Environment variables win over `config.env`. All keys are optional.

| key | default | meaning |
|---|---|---|
| `RELAYBOT_HOME` | `~/.config/relaybot` | config dir: `config.env`, `webhooks/`, `outbox.jsonl` (env only) |
| `RELAYBOT_CODEX_BIN` | desktop-bundled codex, else `codex` on PATH | Codex binary |
| `RELAYBOT_MODEL` | Codex default | model |
| `RELAYBOT_EFFORT` | Codex default | reasoning effort |
| `RELAYBOT_SANDBOX` | `danger-full-access` | app-server sandbox mode |
| `RELAYBOT_DEFAULT_WORKDIR` | `~/Documents/relaybot` | workdir for tasks tied to no project (`codex-run <bot> - ...`) |
| `RELAYBOT_PROJECT_FALLBACK_ROOT` | configured default workdir, else existing codex-for-grok or default project | desktop project root used when no project matches |
| `RELAYBOT_REPOS_ROOT` | `~/Developer` | where existing clones live (`<root>/<repo>`); read by the `codex` skill |
| `RELAYBOT_RUN_ROOT` | `/tmp` | parent of run dirs |
| `RELAYBOT_EXTRA_PATH` | empty | prepended to PATH for Codex |
| `RELAYBOT_PYTHON` | `python3` on PATH | interpreter for the helper scripts |
| `RELAYBOT_CLIENT_NAME` | `relaybot` | client name reported to Codex |
| `RELAYBOT_MAX_SECONDS` | none | optional cap per turn |
| `RELAYBOT_FORCE_EXEC` | empty | set to skip the app-server path (env only) |

Webhook files: `~/.config/relaybot/webhooks/<slug>.json`, mode 600, shaped like
[`examples/webhook.example.json`](../examples/webhook.example.json). `/codex-setup` writes them for you.
Never commit them.

## Uninstall

Remove the five scripts from the prefix and `~/.config/relaybot/`. Nothing else is changed. relaybot
passes no Codex hooks; installs from before this change may have left a relaybot hook trust entry under
`[hooks.state]` in `~/.codex/config.toml`, which is now unused and can be deleted.
