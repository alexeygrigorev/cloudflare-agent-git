"""Shared validation and atomic state helpers. No second runtime or server."""
import hashlib
import json
import os
import pathlib

def pin(path, expected):
    file = pathlib.Path(path)
    if not file.is_absolute() or not file.is_file() or file.is_symlink():
        raise ValueError("invalid pinned path")
    if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
        raise ValueError("pinned source changed")
    return str(file)

def save(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)
def callback_request(profile, body, operation):
    owner = body["owner"]
    if body["v"] != 1 or owner["project"] != profile["project"] or owner["role"] != "root":
        raise ValueError("wrong role/project")
    if owner["actor"] != profile["actor"] or owner["generation"] != profile["generation"]:
        raise ValueError("wrong native owner")
    epoch = owner["epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch <= 0:
        raise ValueError("invalid epoch")
    if not isinstance(body["key"], str) or not 0 < len(body["key"]) <= 256:
        raise ValueError("invalid durable key")
    if operation not in ("root-native-successor", "root-admission", "root-fence-activate", "root-model-evidence", "root-standup-ping", "root-status", "root-start", "root-stop", "root-recover", "root-check", "root-writeup-ping", "root-test-kill"):
        raise ValueError("unapproved operation")
    payload = body.get("payload", {})
    allowed = set()  # Every operation selects its fixed owned target locally.
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("caller override or unapproved payload")
    return dict(owner, v=1, key=body["key"], operation=operation, payload=body.get("payload", {}))
