"""Lock a private state directory, atomically publish run files, and bind a run to its route.

  relaybot_files.py <run> <bot>                                save the originating webhook route
  relaybot_files.py --bind <run> <turn> <bot> <workdir> [resume]
      check (resume) or record the run's bot, workdir and session. A mismatch records
      resume_mismatch for the turn, prints the reason and exits 3.
  relaybot_files.py --bind-session <run>                       record the session after a turn
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile


@contextmanager
def locked(home):
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(home, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def replace_file(path, data, first=False):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        try:
            temp.write(data)
            temp.flush()
            os.fsync(temp.fileno())
            if first:
                try:
                    os.link(temp.name, path)
                except FileExistsError:
                    pass
            else:
                os.replace(temp.name, path)
        finally:
            Path(temp.name).unlink(missing_ok=True)


def save_origin(run, bot):
    if not bot or Path(bot).name != bot or bot in (".", ".."):
        raise ValueError("Invalid originating webhook slug.")
    route = dict(bot=bot, home=os.path.realpath(os.environ["RELAYBOT_HOME"]))
    replace_file(run / "origin.json", json.dumps(route).encode(), first=True)


def read_file(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return b""


def config_value(config, name):
    for line in config.splitlines():
        key, _, value = line.partition(b"=")
        if key.strip() == name.encode() and value.strip().strip(b'"'):
            return value.strip().strip(b'"').decode()
    return ""


def read_json(path):
    try:
        return json.loads(path.read_bytes() or b"{}")
    except FileNotFoundError:
        return {}


def note_turn(turn, outcome, failure_kind=None, detail=""):
    """Record why a turn stopped. The first backend note wins (a timeout stays a timeout)."""
    data = dict(outcome=outcome, failure_kind=failure_kind, detail=str(detail)[:500])
    replace_file(Path(turn) / "backend.json", json.dumps(data, ensure_ascii=False).encode(), first=True)


def bind(run, turn, bot, workdir, resume):
    """A resume must keep the original bot, workdir and session. Legacy runs are bound on first use."""
    binding = read_json(run / "binding.json")
    wd = os.path.realpath(workdir)
    if resume:
        problems = []
        owner = read_json(run / "origin.json").get("bot")
        if owner and owner != bot:
            problems.append(f"this run belongs to bot {owner!r}, not {bot!r}")
        allowed = {binding.get("workdir")}
        checkout = read_file(run / "worktree").decode().strip()
        if checkout:
            allowed.add(os.path.realpath(checkout))
        if binding.get("workdir") and wd not in allowed:
            problems.append(f"this run uses workdir {binding['workdir']}, not {wd}")
        session = read_file(run / "session").decode().strip()
        if binding.get("session") and session != binding["session"]:
            problems.append(f"the saved session changed from {binding['session']} to {session or 'nothing'}")
        if problems:
            reason = "Resume refused: " + "; ".join(problems) + ". Start a new task instead."
            note_turn(turn, "failed", "resume_mismatch", reason)
            print(reason)
            return 3
    if not binding.get("workdir"):
        binding = dict(binding, workdir=wd)
        replace_file(run / "binding.json", json.dumps(binding).encode())
    return 0


def bind_session(run):
    binding = read_json(run / "binding.json")
    session = read_file(run / "session").decode().strip()
    if binding.get("workdir") and session and not binding.get("session"):
        replace_file(run / "binding.json", json.dumps(dict(binding, session=session)).encode())


if __name__ == "__main__":
    if sys.argv[1:2] == ["--bind"] and len(sys.argv) in (6, 7):
        run, turn = Path(sys.argv[2]), Path(sys.argv[3])
        sys.exit(bind(run, turn, sys.argv[4], sys.argv[5], sys.argv[6:] == ["resume"]))
    if sys.argv[1:2] == ["--bind-session"] and len(sys.argv) == 3:
        sys.exit(bind_session(Path(sys.argv[2])))
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    save_origin(Path(sys.argv[1]), sys.argv[2])
