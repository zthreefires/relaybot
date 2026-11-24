"""Per-run handoff snapshots and one-shot macOS LaunchAgents."""
from contextlib import contextmanager
from datetime import datetime
import json
import math
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import time
import uuid

from relaybot_files import locked, replace_file, save_origin
from session_progress import Unavailable, progress


def owned_run(agent, root, directory):
    path = Path(directory)
    run = path.resolve()
    if (path.is_symlink() or run.parent != Path(root).resolve() or not run.name.startswith(agent + "-run-")
            or run.stat().st_uid != os.getuid() or not run.is_dir()
            or not all((run / f).is_file() for f in ("pause", "task.md", "prompt.md"))):
        raise ValueError("Expected the original owned run directory for this task.")
    return run


@contextmanager
def handoff_state(run):
    # Distinct from the runner lock: Codex can hand off an active relaybot turn.
    folder = run / "handoff"
    with locked(folder):
        try:
            state = json.loads((folder / "state.json").read_bytes())
        except FileNotFoundError:
            state = {"enabled": False}
        yield state


def save(run, state):
    replace_file(run / "handoff/state.json", json.dumps(state).encode())


def origin(run, bot=None):
    if bot is not None and not (run / "origin.json").exists():
        save_origin(run, bot)  # First writer wins, including a concurrent legacy resume.
    try:
        data = json.loads((run / "origin.json").read_bytes())
    except FileNotFoundError:
        raise ValueError("No saved webhook route. Supply --bot <original-slug> from the original bot chat.")
    slug = data["bot"]
    if not slug or Path(slug).name != slug or slug in (".", ".."):
        raise ValueError("Invalid saved webhook slug.")
    if bot is not None and bot != slug:
        raise ValueError("This run already belongs to a different bot.")
    return data


def job_info(token):
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid handoff job ID.")
    label = "local.relaybot.handoff-sync." + token
    return label, Path.home() / "Library/LaunchAgents" / (label + ".plist")


def remove_job(token):
    label, path = job_info(token)
    path.unlink(missing_ok=True)
    result = subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
    if result.returncode not in (0, 3, 113):  # ESRCH / launchd service not found
        raise ValueError(f"Could not unload handoff job (launchctl exit {result.returncode}).")


def disarm(run, state):
    token = state.pop("job", None)
    save(run, state)  # A worker already waiting for this lock must see the invalidation.
    if token:
        remove_job(token)


def delay_seconds():
    try:
        hours = float(os.environ.get("RELAYBOT_HANDOFF_SYNC_HOURS") or 12)
        if math.isfinite(hours) and hours > 0:
            return hours * 3600
    except ValueError:
        pass
    raise ValueError("RELAYBOT_HANDOFF_SYNC_HOURS must be a positive number of hours.")


def arm(agent, run, state):
    if not state["enabled"] or "at" not in state or state.get("job") or state.get("fired"):
        return
    due = state["at"] + delay_seconds()
    when = datetime.fromtimestamp(math.ceil(due / 60) * 60)
    token = uuid.uuid4().hex
    label, path = job_info(token)
    spec = dict(Label=label, ProgramArguments=[sys.executable, str(Path(__file__).resolve()), agent,
                                               str(run.parent), str(run), "fire", token],
                EnvironmentVariables={"HOME": str(Path.home())},
                StartCalendarInterval=dict(Month=when.month, Day=when.day, Hour=when.hour, Minute=when.minute),
                RunAtLoad=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.update(job=token, due=due)
    save(run, state)
    try:
        replace_file(path, plistlib.dumps(spec))
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], check=True)
    except (OSError, subprocess.SubprocessError):
        path.unlink(missing_ok=True)
        state.pop("job")
        save(run, state)
        raise
    print("Desktop sync scheduled for", datetime.fromtimestamp(due).astimezone().isoformat(timespec="seconds"))


def record_handoff(agent, run, state, workdir, session, at):
    store = (Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions" if agent == "codex"
             else Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects")
    state.update(at=at, workdir=str(Path(workdir).resolve()), session_id=session, transcripts=str(store.resolve()),
                 fired=False)
    disarm(run, state)
    arm(agent, run, state)


def sync(agent, run, state, bot=None):
    if "at" not in state:
        raise ValueError("Open this run with /handoff before syncing it.")
    route = origin(run, bot)
    try:
        status, message, reply = progress(agent, state)
    except (Unavailable, OSError) as exc:
        status, reply = "unavailable", ""
        message = str(exc) if isinstance(exc, Unavailable) else "Could not read the local session transcript."
    replace_file(run / "sync.md", (reply or message).encode("utf-8", errors="replace"))
    report = dict(sync_status=status, message=message, session_id=state["session_id"],
                  handoff_at=state["at"], synced_at=time.time())
    replace_file(run / "sync-status.json", json.dumps(report).encode())
    subprocess.run([sys.executable, str(Path(__file__).with_name("codex-notify")), "--handoff-sync",
                    route["bot"], str(run), state["workdir"]],
                   env=dict(os.environ, RELAYBOT_HOME=route["home"]), check=True)
    print(message)


def fire(agent, root, directory, token):
    job_info(token)
    cleanup = True
    try:
        run = owned_run(agent, root, directory)
        with handoff_state(run) as state:
            if state.get("job") != token or not state["enabled"]:
                return
            if time.time() < state["due"]:
                cleanup = False  # RunAtLoad also checks for a missed deadline after login.
                return
            try:
                sync(agent, run, state)
            finally:
                state.pop("job")
                state["fired"] = True
                save(run, state)
    finally:
        if cleanup:
            # bootout may terminate this very process. All writes and delivery precede it.
            remove_job(token)


def main():
    agent, root, directory, command, *args = sys.argv[1:]
    if command == "fire":
        fire(agent, root, directory, *args)
        return
    bot = None
    if args[-2:-1] == ["--bot"]:
        bot = args[-1]
        args = args[:-2]
    run = owned_run(agent, root, directory)
    with handoff_state(run) as state:
        if command == "/sync" and not args:
            sync(agent, run, state, bot)
            return
        if command != "/auto-sync" or args not in ([], ["on"], ["off"]):
            raise ValueError("Expected /sync or /auto-sync [on|off], optionally followed by --bot <original-slug>.")
        state["enabled"] = args != ["off"]
        if not state["enabled"]:
            disarm(run, state)
            print("Auto-sync off for this run.")
            return
        origin(run, bot)
        delay_seconds()
        if not shutil.which("launchctl"):
            raise ValueError("Automatic sync requires macOS launchd. Manual /sync is available.")
        save(run, state)
        arm(agent, run, state)
        print("Auto-sync on for this run.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, OverflowError, subprocess.SubprocessError) as exc:
        sys.exit(f"Handoff sync failed: {exc}")
