"""Open one previously dispatched session. Invoked only by a runner's /handoff command."""
import fcntl
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


def open_claude(binary, workdir, session):
    # Claude rejects redirected stdin or stdout for --desktop. Give only the
    # short-lived handoff command a terminal, also when the bot runs headless.
    master, slave = os.openpty()
    with os.fdopen(master, "rb", buffering=0) as output, os.fdopen(slave, "r+b", buffering=0) as tty:
        os.set_blocking(master, False)
        try:
            subprocess.run([binary, "--desktop", "--resume", str(uuid.UUID(session))],
                           cwd=workdir, stdin=tty, stdout=tty, timeout=15, check=True)
        finally:
            sys.stdout.buffer.write(output.read() or b"")


def main():
    agent, binary, root, directory, workdir = sys.argv[1:]
    path = Path(directory)
    run = path.resolve()
    if (path.is_symlink() or run.parent != Path(root).resolve() or not run.name.startswith(agent + "-run-")
            or run.stat().st_uid != os.getuid() or not all((run / f).is_file() for f in ("pause", "task.md", "prompt.md"))):
        sys.exit("Handoff requires the original owned run directory for this task.")
    fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        record = run / "session"
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            if agent == "claude":
                print("Waiting for the current relaybot turn to finish before opening Desktop.", flush=True)
                fcntl.flock(fd, fcntl.LOCK_SH)
            else:
                # Codex can display an active thread as soon as its ID is published.
                while not record.is_file() or not record.stat().st_size:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        break  # The runner exited, possibly without a session.
                    except BlockingIOError:
                        time.sleep(0.2)
        if record.is_symlink() or not record.is_file():
            sys.exit("No saved session ID for this task.")
        session = record.read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", session):
            sys.exit("Invalid saved session ID.")
        if agent == "claude":
            open_claude(binary, workdir, session)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, "codex://threads/" + session], check=True, timeout=15)
    finally:
        os.close(fd)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Desktop handoff failed: {exc}")
