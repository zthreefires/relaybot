# Architecture

Grok Bot holds the context and dispatches a task to the selected local runner. Both runners share the run-directory lifecycle and post one event through `codex-notify`. The diagram details the Codex path.

```
chat ──> bot (skill: codex) ──Shell──> codex-run ──> codex-app-run ──stdio JSON-RPC──> codex app-server
                ^                          │                │                              │
                │                          │                └─IPC "thread-unarchived"──> Codex desktop (sidebar refresh)
                │                          │
                │                          ├─(exit 97)──> codex exec   (fallback, not visible in desktop)
                │                          │
                │                          └─ approval / user-input requests ──> turn pause record
                │
                └──── webhook routine `codex-events` <── codex-notify (one event per launch)
```

## Run directory

A new task creates a private directory with `mktemp -d` under `RELAYBOT_RUN_ROOT` (default `/tmp`). Its name starts with `codex-run-` or `claude-run-` and its mode is `0700`. Resume reuses an owned run directory and takes an exclusive lock. Each launch snapshots its task before rotating results. A valid historical run is tightened to `0700` on resume. The worktree keeps the caller's umask.

| file | written by | meaning |
|---|---|---|
| `task.md` | shared launcher | the task as dispatched (first line names the Codex desktop thread) |
| `prompt.md` | shared launcher | the task text sent to the selected agent, verbatim |
| `log.txt` | selected backend | readable log; contains `session id: <thread id>` |
| `session` | selected backend | Codex thread id or Claude session UUID, used for `resume` |
| `turn-*/input.md` | shared launcher | input snapshot for this launch |
| `turn-*/previous-last.md` | shared launcher | previous published reply, moved aside on resume |
| `last.md` | shared launcher | current reply, published by atomic rename from the turn directory |
| `status.json` | shared status resolver | `{status, reason, pause, turn_id, session_id, source, ts}`; `status` is `done`, `needs_auth` or `failed` |
| `turn-*/pending.json` | shared pause recorder | first approval/user-input request of this launch |
| `pause` | shared launcher | id of this launch; notifications and status are scoped to it |
| `notified.jsonl` | codex-notify | dedupe ledger |
| `exit`, `pid` | shared launcher | exit code and pid |
| `followup.md` | the agent | text for a `resume` turn |

## app-server flow (preferred path)

`codex exec` threads are recorded with source `exec`, and the Codex desktop's thread list shows
interactive threads only, so exec runs never appear there. codex-app-run talks to
`codex app-server` over stdio instead, which produces normal interactive threads:

1. `initialize` with `clientInfo` (`RELAYBOT_CLIENT_NAME`) and `capabilities.experimentalApi`, then `initialized`.
2. Page through `project/list` to find a matching real root, preferring a single-root project. If the workdir is the root of a linked Git worktree (`--git-dir` differs from `--git-common-dir`) and no project has that exact root, resolve the main worktree root (the parent of the common `.git`) and match on it with the same ranking, using the main folder name. At an unmatched Git worktree root, call `project/create` with the folder name, its canonical root and the stable idempotency key `relaybot:<real path>`; for a linked worktree these are the main root's name and path, never the worktree's. The thread cwd stays the workdir. Skip creation for default and fallback directories. On creation failure, log the error and look up the fallback project. With no project match, omit `projectId`.
3. `thread/start` with `{cwd, approvalPolicy: "never", sandbox, threadSource: "user", projectId?, model?, config.model_reasoning_effort?}`.
   Passing `projectId` is what files the thread under the right desktop project.
   For a continuation: `thread/resume` with the stored thread id.
4. `thread/name/set` to `[<bot>] <first line of task>`.
5. `turn/start` with the prompt (and `effort` if configured).
6. Stream notifications: `item/completed` (an `agentMessage` item gives the latest reply),
   `turn/completed`, and `hook/completed` for the user's own hooks (logged only). Approval and user-input
   requests from the server are declined (runs are unattended) and recorded for the final `needs_auth` decision.

Exit codes: `0` turn completed, `1` failed after the server was up, `2` usage, `97` the app-server
could not be spawned or initialized, `130/143` killed. Only `97` makes codex-run fall back to `codex exec`:
once a thread exists, retrying under exec would fail the same way or run the task twice.

Concurrency: while a run is writing a thread, the desktop cannot write to it ("active writer").
If the user continues the thread in the desktop, a later `resume` may fail until they close it there.

## Claude Code CLI

`claude-run` selects the Claude backend by its executable name. It runs `claude -p` in the requested workdir with stream-json input/output and `--permission-prompt-tool stdio`. One user frame carries the UTF-8 task, preserving whitespace and line endings. The runner reads the session UUID from the CLI, saves it in `session`, and checks the UUID again on `--resume <uuid>`. The full reply comes from the terminal `result` frame. Codex model, effort, sandbox and desktop settings apply only to Codex.

A tool approval, `AskUserQuestion`, or MCP elicitation delivered as a control request stops the CLI while the request is outstanding. Relaybot records the reason as `needs_auth`, grants no permission, and lets Claude flush its transcript on termination. Structured permission denials, deferred tool calls and explicit account/authentication errors can also produce `needs_auth`. If a stop precedes the final result, `reply` is empty and `reply_file` is null. An unsuccessful or missing result, unexpected session ID, timeout or unexpected exit produces `failed`. A question expressed only in the final text is delivered as a normal reply. See the [Claude Code approvals interface](https://code.claude.com/docs/en/agent-sdk/user-input) and [print-mode lifecycle](https://code.claude.com/docs/en/headless).

A follow-up uses the same workdir and `claude --resume <uuid>`. The user's existing Claude permissions still apply. If an interactive approval is required again, the user can open that session locally to handle it. Relaybot supplies no hooks or permission overrides.

## Desktop live refresh (undocumented, best-effort)

Without a nudge, the desktop only shows the new thread after a restart. codex-app-run connects to the
desktop's IPC socket `~/.codex/ipc/ipc.sock`. Frames are a 4-byte little-endian length followed by JSON.
It sends `initialize` (`clientType`), then a `broadcast` with method `thread-unarchived`, version `1`,
params `{hostId: "local", conversationId: <thread id>}`, and the desktop re-reads the thread. It does
this after `turn/start`, at most every 15 s on item completion, and at the end.

This is not a documented interface. It may change or stop working with any desktop update; failures are
ignored and only cost the live refresh.

## Codex turn status

`prompt.md` is the task file, byte for byte. relaybot appends no rules or markers and passes no
hooks, so the thread in the desktop reads exactly like a task the user typed, and continuing it by
hand there carries nothing from relaybot. Constraints (for example "don't push", "stop before a
login") belong in the task text, which the dispatching bot writes.

The turn's status comes only from system signals:

- the process exit: nonzero from codex-app-run or `codex exec` means `failed`;
- the app-server's requests: `item/commandExecution/requestApproval`, `item/fileChange/requestApproval`,
  `execCommandApproval`, `applyPatchApproval`, `item/permissions/requestApproval`,
  `item/tool/requestUserInput` and `mcpServer/elicitation/request`. Runs are unattended, so codex-app-run
  declines or refuses each one and records the first as the turn's pause (`turn-*/pending.json`,
  through `codex-notify <bot> needs_auth ...`). That makes the turn `needs_auth`;
- an empty final reply on a clean exit means `failed`.

Everything else is `done`: the turn finished. Whether Codex completed the task, asked a question or got
stuck is in the reply text; the receiving bot reads it. relaybot never parses the reply.

At finalization `codex-relay-hook --result` (a plain helper, not a Codex hook) writes `status.json`.
A nonzero exit wins and keeps its code; then a recorded pause; then a missing reply (exit 1); else
`done`. `done` and `needs_auth` return 0. The exit code, `exit` file, final output line and webhook all
agree.

The `codex exec` fallback has no app-server requests (`codex exec` never asks for approval), so it
yields `done` or `failed`.

Older sessions that were started with the previous dispatcher rules may still call
`codex-notify <bot> blocked ...`; that is recorded like a pause and sent as `blocked`.

## Webhook events

Each runner posts exactly one event per launch (a new task or a resume), after the turn ends or the
runner exits. Pauses recorded during the turn are held until then. `codex-notify` POSTs JSON to the URL
in `$RELAYBOT_HOME/webhooks/<bot>.json`:

```json
{"event": "done", "run_id": "codex-run-AbC123xy", "run_dir": "/tmp/codex-run-AbC123xy",
 "workdir": "/path/to/repo", "ts": 1767240000,
 "message": "View session: codex resume <id>\n<first 1500 chars of the reply>",
 "session_id": "<thread id>", "exit_code": 0,
 "reply": "<final reply, up to 8000 chars>", "reply_truncated": false,
 "reply_file": "/tmp/codex-run-AbC123xy/last.md"}
```

Headers: `Content-Type: application/json`, `Authorization: Bearer <key>`, `X-Automation-Key: <key>`.

| field | meaning |
|---|---|
| `event` | `done`, `needs_auth`, `failed`, `test` (`blocked` only from older sessions, see above) |
| `run_id`, `run_dir`, `workdir`, `ts` | the run directory's name and path, the agent's cwd, send time (unix seconds) |
| `message` | short human text, at most 2000 chars: session command (`codex resume <id>` or `claude --resume <id>`), then for `done` the reply start; for `needs_auth` the request and any reply start; for `failed` the reason and the current turn's log tail |
| `session_id` | Codex thread id or Claude session UUID, or `null` if none was created |
| `exit_code` | the runner's exit code for this launch (`0` for `done`/`needs_auth`) |
| `reply` | this turn's final agent message (`last.md`), first 8000 chars; `""` if there was none |
| `reply_truncated` | `true` when `reply` was cut; read `reply_file` for the rest |
| `reply_file` | path of `last.md` on the relaybot computer, or `null` when there is no reply |

`test` events carry only `event, run_id, run_dir, workdir, message, ts`.

| event | when it fires | what the receiver does |
|---|---|---|
| `done` | the turn completed with a final reply and no pause was recorded | read `reply`: report the result, relay the agent's question, or say what blocks it |
| `needs_auth` | Codex requested approval/input or Claude reported one of the pause signals above | tell the user what the agent requested (`message`, `status.json` `reason`) and any final reply (`reply`); continue only after they agree |
| `failed` | nonzero exit (app-server error, interrupted, killed, exec failure, resume mismatch), or no final reply | report the reason and log tail |
| `test` | `/relaybot-setup` or `relaybot-doctor --webhook-test` | confirm the webhook works |

Delivery: only a direct HTTP 2xx counts. Redirects (301, 302, 303, 307, 308) and other failures are
queued in `$RELAYBOT_HOME/outbox.jsonl` without credentials; there is no automatic retry, and queuing
does not change the task's exit code. Each launch has its own dedupe slot in `notified.jsonl`.

The receiving side is a webhook routine (`codex-events`) on the dispatching bot. Its prompt is one pointer
to the `codex` skill, so changing event handling only means editing the skill.
