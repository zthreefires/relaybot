"""Lock a private state directory and atomically publish a file inside a run."""
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


if __name__ == "__main__":
    save_origin(Path(sys.argv[1]), sys.argv[2])
