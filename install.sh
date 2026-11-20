#!/usr/bin/env bash
# install.sh [--prefix DIR]   (default DIR: ~/bin, or $PREFIX)
# Copies the relaybot scripts into DIR, creates ~/.config/relaybot (or $RELAYBOT_HOME) with a
# config.env from config.example.env if missing.
# Idempotent: re-running updates the scripts and never overwrites config.env or webhook files.
set -eu
src=$(cd "$(dirname "$0")" && pwd)
prefix=${PREFIX:-$HOME/bin}
[ "${1:-}" = --prefix ] && [ -n "${2:-}" ] && prefix=$2
home=${RELAYBOT_HOME:-$HOME/.config/relaybot}

mkdir -p "$prefix"
for s in claude-run claude-stream-run codex-run codex-app-run codex-notify codex-relay-hook relaybot-doctor; do
  install -m 755 "$src/bin/$s" "$prefix/$s"
done
mkdir -p "$home/webhooks"; chmod 700 "$home" "$home/webhooks"
if [ ! -f "$home/config.env" ]; then
  install -m 600 "$src/config.example.env" "$home/config.env"
  echo "created $home/config.env (edit it to set model, effort, folders)"
fi
case ":$PATH:" in *":$prefix:"*) ;; *) echo "note: $prefix is not on PATH. Fine for runs (codex-run puts its own dir on PATH), but add it to call relaybot-doctor by name.";; esac

echo "installed to $prefix"
echo
echo "Next:"
echo "  1. Run: $prefix/relaybot-doctor"
echo "  2. Install skills/codex and skills/codex-setup into your agent, then run /codex-setup in each bot."
