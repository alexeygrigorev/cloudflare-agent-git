"""Private per-project settings and server-bound task credentials, outside Git."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def config_path():
    explicit = os.environ.get("AGENT_BRANCHES_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    project = str(Path.cwd().resolve())
    key = hashlib.sha256(project.encode()).hexdigest()[:20]
    return Path.home() / ".config" / "agent-branches" / (key + ".json")


def load_config():
    path = config_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Branches configuration must be a JSON object")
    return data


def settings_for(server=None):
    data = load_config()
    selected = (server or os.environ.get("AGENT_BRANCHES_SERVER") or os.environ.get("COORDINATOR_URL")
                or data.get("server") or "http://127.0.0.1:8787").rstrip("/")
    settings = dict(data.get("servers", {}).get(selected, {}))
    return selected, settings


def save_settings(server, changes=None, task=None):
    """Serialize concurrent CLI registrations; never put credentials in a repo."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError("Branches configuration is locked; retry after the other registration finishes")
            time.sleep(0.05)
    temporary = None
    try:
        os.close(descriptor)
        data = load_config()
        data["server"] = server
        settings = data.setdefault("servers", {}).setdefault(server, {})
        settings.update(changes or {})
        if task:
            settings.setdefault("tasks", {})[task["taskId"]] = task
        handle, temporary = tempfile.mkstemp(prefix=".branches-config-", dir=path.parent)
        os.chmod(temporary, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
        os.replace(temporary, path)
        temporary = None
        os.chmod(path, 0o600)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return settings
