# Install

Requirements: macOS or Linux, `bash`, `python3` (3.8+), a signed-in CLI for each target you use (Claude Code, Codex CLI or the Codex/ChatGPT desktop app), and a personal agent that can run shell commands on that computer and has webhook routines
(built for Grok Bot).

1. Clone and install the scripts (default prefix `~/bin`; re-running updates them):

   ```bash
   git clone https://github.com/zthreefires/relaybot.git
   cd relaybot
   ./install.sh                 # or ./install.sh --prefix ~/.local/bin
   ```

   This copies `claude-run`, `claude-stream-run`, `codex-run`, `codex-app-run`, `codex-notify`, `codex-relay-hook`, `relaybot-doctor`,
   creates `~/.config/relaybot/` (mode 700) with `webhooks/`, and creates `config.env` from
   `config.example.env` if it does not exist.

2. Edit `~/.config/relaybot/config.env` (all optional): model, effort, default workdir, repos root,
   binary paths. See [Configuration](#configuration).

3. For Codex desktop runs, in the Codex desktop app, create a project whose root is your default workdir
   (`RELAYBOT_DEFAULT_WORKDIR`, default `~/Documents/relaybot`). Unmatched non-repository workdirs can use this fallback. Git repository roots get their own project; a linked worktree without its own project goes under the main repository's project. A preexisting `~/Documents/codex-for-grok` project is preferred as fallback when both root settings are unset.

4. Check: `relaybot-doctor` (read-only). From a clone, `tests/selftest.sh` runs an offline end-to-end
   test with stub Codex exec/app-server, Claude CLI and a local webhook. Pass an installed prefix to test that copy, e.g. `tests/selftest.sh ~/bin`.

5. Install the skills into your agent: `skills/codex/SKILL.md` and `skills/relaybot-setup/SKILL.md`. Then,
   in each bot that should dispatch to either target, send `/relaybot-setup` once. It checks installation and sign-in for both CLIs and tests their shared webhook. New bots get one `relaybot-events` routine. Setup reuses an existing `codex-events` routine as is. A missing or signed-out CLI can be added later by rerunning setup.

## Configuration

Environment variables win over `config.env`. All keys are optional.

| key | default | meaning |
|---|---|---|
| `RELAYBOT_HOME` | `~/.config/relaybot` | config dir: `config.env`, `webhooks/`, `outbox.jsonl` (env only) |
| `RELAYBOT_CODEX_BIN` | desktop-bundled codex, else `codex` on PATH | Codex binary |
| `RELAYBOT_CLAUDE_BIN` | `claude` on PATH, then `~/.local/bin/claude` | Claude Code binary with print mode, stream-json and stdio permission requests |
| `RELAYBOT_MODEL` | Codex default | model |
| `RELAYBOT_EFFORT` | Codex default | reasoning effort |
| `RELAYBOT_SANDBOX` | `danger-full-access` | app-server sandbox mode |
| `RELAYBOT_DEFAULT_WORKDIR` | `~/Documents/relaybot` | workdir for tasks tied to no project (`codex-run <bot> - ...`) |
| `RELAYBOT_PROJECT_FALLBACK_ROOT` | configured default workdir, else existing codex-for-grok or default project | desktop project root used when no project matches |
| `RELAYBOT_REPOS_ROOT` | `~/Developer` | where existing clones live (`<root>/<repo>`); read by the `codex` skill |
| `RELAYBOT_RUN_ROOT` | `/tmp` | parent of run dirs |
| `RELAYBOT_EXTRA_PATH` | empty | prepended to PATH for the runners |
| `RELAYBOT_PYTHON` | `python3` on PATH | interpreter for the helper scripts |
| `RELAYBOT_CLIENT_NAME` | `relaybot` | client name reported to Codex |
| `RELAYBOT_MAX_SECONDS` | none | optional cap per turn |
| `RELAYBOT_FORCE_EXEC` | empty | set to skip the app-server path (env only) |

Webhook files: `~/.config/relaybot/webhooks/<slug>.json`, mode 600, shaped like
[`examples/webhook.example.json`](../examples/webhook.example.json). `/relaybot-setup` writes them for you.
Never commit them.

## Uninstall

Remove the installed scripts from the prefix and `~/.config/relaybot/`. Nothing else is changed. relaybot
passes no Codex hooks; installs from before this change may have left a relaybot hook trust entry under
`[hooks.state]` in `~/.codex/config.toml`, which is now unused and can be deleted.
