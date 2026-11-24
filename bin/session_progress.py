"""Read the visible assistant messages and turn lifecycle from one desktop transcript."""
from datetime import datetime
import json
from pathlib import Path


class Unavailable(ValueError):
    pass


def transcript(agent, root, session):
    pattern = f"**/rollout-*-{session}.jsonl" if agent == "codex" else f"*/{session}.jsonl"
    paths = [p for p in root.glob(pattern) if p.is_file() and not p.is_symlink() and root in p.resolve().parents]
    if len(paths) != 1:
        raise Unavailable("Could not identify a unique local transcript for the handed-off session.")
    return paths[0]


def visible_text(content, kind):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(b["text"] for b in content if isinstance(b, dict)
                     and b.get("type") == kind and isinstance(b.get("text"), str))


def codex_event(row, session):
    p = row.get("payload")
    if row.get("type") == "session_meta" and (not isinstance(p, dict) or p.get("id") != session):
        raise Unavailable("The rollout belongs to a different Codex thread.")
    if not isinstance(p, dict) or p.get("thread_id", session) != session:
        return
    kind = p.get("type")
    if row.get("type") == "event_msg":
        if kind in ("task_started", "turn_started"):
            return "turn_started", ""
        if kind == "user_message":
            return "start", ""
        if kind in ("task_complete", "turn_complete"):
            return "done", p.get("last_agent_message")
        if kind == "turn_aborted":
            return "interrupted", ""
        if kind == "agent_message":
            return ("running" if p.get("phase") == "commentary" else "reply"), p.get("message")
        item = p.get("item")
        if kind == "item_completed" and isinstance(item, dict) and item.get("type") == "AgentMessage":
            return ("running" if item.get("phase") == "commentary" else "reply"), visible_text(item.get("content"), "Text")
    if row.get("type") == "response_item":
        if kind == "message" and p.get("role") == "assistant" and p.get("recipient") in (None, "all"):
            return ("running" if p.get("phase") == "commentary" else "reply"), visible_text(p.get("content"), "output_text")
        if kind in ("function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"):
            return "running", ""
        if kind == "message" and p.get("role") == "user":
            return "start", ""


def claude_event(row, session):
    if row.get("sessionId", session) != session or row.get("isSidechain") or row.get("isMeta"):
        return
    kind = row.get("type")
    if kind == "user":
        message = row.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        tool_result = isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result"
                                                      for b in content)
        return ("running" if tool_result else "start"), ""
    if kind == "system" and row.get("subtype") == "turn_duration":
        return "done", ""
    if kind == "assistant":
        message = row.get("message")
        if isinstance(message, dict):
            stop = message.get("stop_reason")
            if row.get("isApiErrorMessage") or stop in ("max_tokens", "model_context_window_exceeded"):
                return "interrupted", visible_text(message.get("content"), "text")
            active = stop in (None, "tool_use", "pause_turn")
            return ("running" if active else "done"), visible_text(message.get("content"), "text")


def events(path, parse, session):
    with path.open("rb") as stream:
        # Bound the snapshot even if the desktop keeps appending while we read.
        remaining = stream.seek(0, 2)
        stream.seek(0)
        while remaining:
            line = stream.readline(remaining)
            if not line:
                break
            remaining -= len(line)
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                if not remaining and not line.endswith(b"\n"):
                    break  # A writer has not finished this JSON record yet.
                raise Unavailable("The local session transcript contains an unreadable record.")
            if not isinstance(row, dict):
                continue
            event = parse(row, session)
            if event is None:
                continue
            try:
                ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).timestamp()
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            yield ts, *event


def progress(agent, handoff):
    session = handoff["session_id"]
    path = transcript(agent, Path(handoff["transcripts"]), session)
    parse = codex_event if agent == "codex" else claude_event
    status = None
    open_turn = False
    new_activity = False
    replies = []
    current_reply = ""
    previous_text = None
    for ts, kind, text in events(path, parse, session):
        if kind == "turn_started":
            open_turn = True
            kind = "start"
        elif kind == "reply":
            kind = "running" if open_turn else "done"
        elif kind in ("done", "interrupted"):
            open_turn = False
        # Retain the final visible reply per turn and the latest progress of an open turn.
        # Codex may serialize the same final message again in task_complete.
        if kind == "start" or (status in ("done", "interrupted") and kind == "running"):
            if current_reply:
                replies.append(current_reply)
            current_reply = ""
            previous_text = None
        status = "running" if kind == "start" else kind
        if ts > handoff["at"]:
            new_activity = True
            if isinstance(text, str) and text.strip() and text != previous_text:
                current_reply = text
        if isinstance(text, str) and text.strip():
            previous_text = text
    if not new_activity:
        if status == "running":
            return status, "No new progress since handoff. The last recorded turn is still running.", ""
        return "no_progress", "No new progress since handoff.", ""
    messages = {"running": "The last recorded turn is still running.",
                "done": "The desktop turn finished.", "interrupted": "The desktop turn was interrupted."}
    if current_reply:
        replies.append(current_reply)
    return status, messages[status], "\n\n".join(replies)
