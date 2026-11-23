# Install relaybot (for agents)

You are an agent asked to install relaybot for your user. Follow these steps in order and report the
result in the user's language. Run commands on the user's relaybot computer. Do not print secrets at any step.

## 0. Preconditions (check, don't fix silently)

```bash
command -v python3 && python3 --version          # need 3.8+
command -v git
```

The doctor checks both coding CLIs after installation, using the paths selected by their runners.

## 1. Get the code and install

```bash
git clone https://github.com/zthreefires/relaybot.git ~/relaybot 2>/dev/null || git -C ~/relaybot pull --ff-only
~/relaybot/install.sh                       # prefix ~/bin; use --prefix DIR to change
```

`install.sh` is idempotent and never overwrites `~/.config/relaybot/config.env` or webhook files.

## 2. Configure (ask the user, then edit)

Ask the user for the values they care about and set them in `~/.config/relaybot/config.env`:

- `RELAYBOT_CLAUDE_BIN`: optional explicit path to Claude Code.
- `RELAYBOT_MODEL`, `RELAYBOT_EFFORT`: leave unset to use their Codex defaults.
- `RELAYBOT_REPOS_ROOT`: where their clones live (`<root>/<repo>`). Verify with `ls`.
- `RELAYBOT_DEFAULT_WORKDIR`: folder for tasks tied to no project; for Codex desktop filing, ask them to create a project with this root.

## 3. Verify

```bash
~/bin/relaybot-doctor            # expect "0 fail"
~/relaybot/tests/selftest.sh     # offline: stub Codex and Claude + local webhook; expect "selftest passed"
```

## 4. Install the skills and wire the bot

Install `skills/codex/SKILL.md`, `skills/claude/SKILL.md`, and `skills/relaybot-setup/SKILL.md` into the agent's skill store.
On upgrade, refresh the codex and claude skills in each dispatching bot so it can handle permission choices and the `-handoff` chat command.

Run `/relaybot-setup` in the dispatching bot's chat. It checks both CLIs and their sign-in status and sends one shared test. Reuse the bot's existing event routine and slug. The legacy `codex-events` routine works as is. Create `relaybot-events` only when neither name exists. If a CLI is missing or signed out, finish the other route and webhook test. Give the user the missing CLI's install or sign-in instructions.

## 5. Report

Report the install prefix, config values set, doctor/selftest results, each CLI's status and the current bot's webhook result. Once the test arrives, tell the user which ready CLI or CLIs on this computer will send task results back to this chat.
