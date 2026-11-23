"""One outstanding Claude permission question per relaybot installation."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile


KEY = "RELAYBOT_CLAUDE_SKIP_PERMISSIONS"
OFFER = "claude-permission-offer.json"


@contextmanager
def locked(home):
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(home, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def read_file(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return b""


def replace_file(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        try:
            temp.write(data)
            temp.flush()
            os.fsync(temp.fileno())
            os.replace(temp.name, path)
        finally:
            Path(temp.name).unlink(missing_ok=True)


def configured(config):
    for line in config.splitlines():
        key, _, value = line.partition(b"=")
        if key.strip() == KEY.encode() and value.strip().strip(b'"'):
            return value.strip().strip(b'"').decode()
    return ""


def save_preference(path, config, value):
    line = f"{KEY}={value}".encode()
    updated, count = re.subn(rb"(?m)^[ \t]*" + KEY.encode() + rb"[ \t]*=[^\r\n]*", line, config, count=1)
    if not count:
        newline = b"\r\n" if b"\r\n" in config else b"\n"
        separator = newline if config and not config.endswith(b"\n") else b""
        updated = config + separator + line + newline
    replace_file(path, updated)


def binding(bot, run, turn, workdir, sid):
    return dict(bot=bot, run_dir=str(run.resolve()), turn=turn, workdir=os.path.realpath(workdir), session_id=sid)


def outstanding(home):
    data = read_file(home / OFFER)
    return json.loads(data) if data else {}


def current_question(target):
    run = Path(target["run_dir"])
    status = json.loads(read_file(run / "status.json") or b"{}")
    return (read_file(run / "pause").decode().strip() == target["turn"]
            and status.get("status") == "needs_auth" and status.get("permission_question") == target)


def reserve_offer(home, target):
    with locked(home):
        if not current_question(target) or os.environ.get(KEY) or configured(read_file(home / "config.env")):
            return False
        old = outstanding(home)
        if old and current_question(old):
            return False
        replace_file(home / OFFER, json.dumps(target).encode())
        return True


def answer(home, target, choice):
    # The launcher holds the run lock through this check, turn rotation and execution.
    with locked(home):
        offer = outstanding(home)
        if offer != target or not current_question(target):
            sys.exit("This permission question is stale or belongs to another task.")
        path = home / "config.env"
        config = read_file(path)
        value = "1" if choice == "yes" else "0"
        stored = configured(config)
        if any(v and v != value for v in (stored, os.environ.get(KEY))):
            sys.exit("A different Claude permission preference is already configured.")
        if not stored:
            save_preference(path, config, value)
        if choice == "no":
            (home / OFFER).unlink()
        # For yes, a retry can finish preparing the resume up to the pause rotation.


if __name__ == "__main__":
    if len(sys.argv) != 7 or sys.argv[6] not in ("ask", "yes", "no"):
        sys.exit("Expected bot, run directory, turn, workdir, session id and ask/yes/no.")
    bot, run_dir, turn, cwd, sid, choice = sys.argv[1:]
    run = Path(run_dir).resolve()
    if run.parent != Path(os.environ.get("RELAYBOT_RUN_ROOT") or "/tmp").resolve():
        sys.exit("Permission choices require a run in the configured run root.")
    target = binding(bot, run, turn, cwd, sid)
    home = Path(os.environ["RELAYBOT_HOME"])
    if choice == "ask":
        print("ask" if reserve_offer(home, target) else "skip")
    else:
        answer(home, target, choice)
