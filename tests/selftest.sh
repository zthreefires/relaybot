#!/usr/bin/env bash
# tests/selftest.sh: offline end-to-end check of both runners and their shared webhook.
# Usage: tests/selftest.sh [bin-directory]. Exercises Codex exec/app-server, Claude stream-json and loopback webhooks.
# All configuration, runs and tasks are temporary. No real coding CLI or external webhook is used.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
bin=${1:-$repo/bin}
bin=$(cd "$bin" && pwd)
t=$(mktemp -d)
cleanup() {
  if [ -n "${srv:-}" ]; then
    kill "$srv" 2>/dev/null || true
    wait "$srv" 2>/dev/null || true
  fi
  rm -rf "$t"
}
trap cleanup EXIT
export HOME=$t
export RELAYBOT_HOME=$t/home RELAYBOT_RUN_ROOT=$t/runs RELAYBOT_FORCE_EXEC=1
mkdir -p "$RELAYBOT_HOME/webhooks" "$RELAYBOT_RUN_ROOT"

# Stub codex: behaves like `codex exec ... -o <last> -`. The NEEDS_AUTH case records a pause the way
# codex-app-run does when the app-server asks for approval. The prompt must be the task verbatim.
cat > "$t/codex" <<'S'
#!/usr/bin/env bash
out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done
prompt=$(cat)
printf '%s\n' "$prompt" >> "$HOME/prompts.txt"
case $prompt in *NEEDS_AUTH_CASE*) last="Stopped before entering a 2FA code."
  codex-notify test-bot needs_auth "$RELAYBOT_RUN_DIR" . "Codex needs user input: please enter the 2FA code" ;;
  *) last="All good. Wrote hello.txt." ;; esac
echo "session id: 00000000-test-session"
printf '%s' "$last" > "$out"
S
chmod +x "$t/codex"
export RELAYBOT_CODEX_BIN=$t/codex

# Local receiver: records each POST body plus whether the auth headers matched.
python3 - "$t/port" "$t/received.jsonl" <<'P' &
import http.server, json, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body["_auth_ok"] = (self.headers.get("Authorization") == "Bearer test-key"
                            and self.headers.get("X-Automation-Key") == "test-key")
        open(sys.argv[2], "a").write(json.dumps(body) + "\n")
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass
server = http.server.HTTPServer(("127.0.0.1", 0), H)
with open(sys.argv[1], "w") as f:
    print(server.server_port, file=f)
server.serve_forever()
P
srv=$!
for ((i=0; i<100; i++)); do [ -s "$t/port" ] && break; sleep 0.05; done
port=$(cat "$t/port")
printf '{"url": "http://127.0.0.1:%s/hook", "key": "test-key", "bot": "Test Bot"}\n' "$port" > "$RELAYBOT_HOME/webhooks/test-bot.json"

fail() { echo "FAIL: $*"; exit 1; }
echo "write hello.txt" > "$t/task1.md"
"$bin/codex-run" test-bot "$t/work" "$t/task1.md" | tail -1
echo "NEEDS_AUTH_CASE" > "$t/task2.md"
r2=$("$bin/codex-run" test-bot "$t/work" "$t/task2.md" | tail -1); echo "$r2"
run2=${r2#run_dir=}; run2=${run2%% *}
echo "code entered, continue" > "$run2/followup.md"
"$bin/codex-run" test-bot "$t/work" "$run2/followup.md" resume | tail -1
"$bin/codex-notify" test-bot test /tmp "$t" "connectivity" >/dev/null

python3 - "$t/received.jsonl" <<'P' || fail "webhook payloads"
import json, sys
ev = [json.loads(l) for l in open(sys.argv[1])]
assert [e["event"] for e in ev] == ["done", "needs_auth", "done", "test"], [e["event"] for e in ev]
for e in ev:
    assert e["_auth_ok"], "auth headers"
    assert set(e) >= {"event", "run_id", "run_dir", "workdir", "message", "ts"}
assert ev[0]["message"] == ev[0]["reply"]
assert "2FA" in ev[1]["message"]
for e in ev[:3]:
    assert set(e) >= {"session_id", "exit_code", "reply", "reply_truncated", "reply_file"}, e
assert ev[0]["reply"] == "All good. Wrote hello.txt." and ev[0]["reply_file"].endswith("/last.md")
assert ev[0]["session_id"] == "00000000-test-session" and ev[0]["exit_code"] == 0
print("ok: events", [e["event"] for e in ev])
P
grep -q GROKBOT "$t/prompts.txt" && fail "prompt carries injected text"
[ "$(cat "$t/prompts.txt")" = "$(printf 'write hello.txt\nNEEDS_AUTH_CASE\ncode entered, continue')" ] || fail "prompt is not the task verbatim"
python3 "$repo/tests/regression.py" "$bin"
echo "selftest passed"
