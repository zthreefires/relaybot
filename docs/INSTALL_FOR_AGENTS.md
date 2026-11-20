# Install relaybot (for agents)

You are an agent asked to install relaybot for your user. Follow these steps in order and report the
result in the user's language. Run commands on the computer where Codex runs (for a personal agent with
remote machines, that is the user's computer, not your own sandbox). Do not print secrets at any step.

## 0. Preconditions (check, don't fix silently)

```bash
command -v python3 && python3 --version          # need 3.8+
command -v git
ls /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex 2>/dev/null || command -v codex
```

If no Codex binary is found, stop and tell the user to install the Codex desktop app or CLI and sign in.

## 1. Get the code and install

```bash
git clone https://github.com/zthreefires/relaybot.git ~/relaybot 2>/dev/null || git -C ~/relaybot pull --ff-only
~/relaybot/install.sh                       # prefix ~/bin; use --prefix DIR to change
```

`install.sh` is idempotent and never overwrites `~/.config/relaybot/config.env` or webhook files.

## 2. Configure (ask the user, then edit)

Ask the user for the values they care about and set them in `~/.config/relaybot/config.env`:

- `RELAYBOT_MODEL`, `RELAYBOT_EFFORT`: leave unset to use their Codex defaults.
- `RELAYBOT_REPOS_ROOT`: where their clones live (`<root>/<repo>`). Verify with `ls`.
- `RELAYBOT_DEFAULT_WORKDIR`: folder for tasks tied to no project; ask them to create a Codex desktop
  project with this root.

## 3. Verify

```bash
~/bin/relaybot-doctor            # expect "0 fail"
~/relaybot/tests/selftest.sh     # offline: stub Codex + local webhook; expect "selftest passed"
```

## 4. Install the skills and wire the bot

Install `skills/codex/SKILL.md` and `skills/codex-setup/SKILL.md` into the agent's skill store. Then run
`/codex-setup` in each bot that should dispatch (it creates the `codex-events` webhook routine, stores
`~/.config/relaybot/webhooks/<slug>.json`, and sends a `test` event). Verify with:

```bash
~/bin/relaybot-doctor --webhook-test <slug>    # expect "sent 200"
```

## 5. Report

Tell the user: install prefix, config values set, doctor/selftest results,
which bots are wired. List anything you could not do.
