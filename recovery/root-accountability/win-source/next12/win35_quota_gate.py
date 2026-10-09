"""Fresh local ChatGPT quota admission for an independently pinned Codex binary.

Read-only: never logs auth/credits, starts a model turn, refreshes credentials,
consumes resets, or changes account settings. Exit 75 denies admission.
"""
import argparse
import base64
import hashlib
import json
import math
import pathlib
import platform
import os
import queue
import subprocess
import threading
import time


def decision(result, account_type):
    if account_type != "chatgpt":
        return False, "unsupported authentication route"
    if not isinstance(result, dict):
        return False, "missing limits"
    buckets = result.get("rateLimitsByLimitId")
    if buckets is None:
        bucket = result.get("rateLimits")
        buckets = {"legacy": bucket} if bucket else {}
    if not isinstance(buckets, dict) or not buckets:
        return False, "missing quota buckets"
    known = []
    for bucket in buckets.values():
        if not isinstance(bucket, dict):
            return False, "invalid quota bucket"
        if bucket.get("rateLimitReachedType") or bucket.get("spendControlReached"):
            return False, "account limit reached"
        windows = []
        for name in ("primary", "secondary"):
            window = bucket.get(name)
            if window is None:
                continue
            if not isinstance(window, dict):
                return False, "invalid quota window"
            value = window.get("usedPercent")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False, "unknown quota window"
            if not math.isfinite(value) or not 0 <= value <= 100:
                return False, "invalid quota usage"
            windows.append(100 - value)
        if not windows:
            return False, "unknown quota bucket"
        known.extend(windows)
    if min(known) <= 15:
        return False, "reserve gate"
    return True, "fresh known windows above reserve"


def account_fingerprint(account):
    if not isinstance(account, dict) or account.get("type") != "chatgpt":
        raise ValueError("unsupported authentication route")
    email = account.get("email")
    if not isinstance(email, str) or not email.strip():
        raise ValueError("account identity unavailable")
    identity = json.dumps({"type": "chatgpt", "email": email.strip().casefold()},
                          sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(identity.encode()).hexdigest()


def read_limits(executable, timeout=45):
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(
        [str(executable), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    )
    messages = queue.Queue(maxsize=256)

    def reader():
        try:
            for line in process.stdout:
                messages.put(line, timeout=1)
        except Exception:
            pass

    threading.Thread(target=reader, daemon=True).start()

    def request(ident, method, params=None):
        body = {"id": ident, "method": method}
        if params is not None:
            body["params"] = params
        process.stdin.write(json.dumps(body) + "\n")
        process.stdin.flush()
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            try:
                raw = messages.get(timeout=min(1, remaining))
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("app-server exited")
                continue
            if len(raw) > 1024 * 1024:
                raise RuntimeError("oversized response")
            message = json.loads(raw)
            if message.get("id") == ident:
                if "error" in message or "result" not in message:
                    raise RuntimeError("RPC denied")
                return message["result"]
        raise TimeoutError("quota request deadline")

    try:
        request(0, "initialize", {"clientInfo": {
            "name": "win35_root_admission", "title": "Root admission", "version": "1",
        }})
        process.stdin.write('{"method":"initialized","params":{}}\n')
        process.stdin.flush()
        account = request(1, "account/read", {"refreshToken": False})
        if account.get("requiresOpenaiAuth") is not True:
            raise ValueError("active provider is not OpenAI authenticated")
        limits = request(2, "account/rateLimits/read")
        return limits, account.get("account")
    finally:
        # Exact child handle only: existing desktop/server/model processes are untouched.
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            stream.close()


def load_private_profile(path):
    # PowerShell's native security descriptor handling avoids approximating NTFS
    # ownership with POSIX modes. The path travels as data in the environment.
    script = r'''
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$f=Get-Item -LiteralPath $env:WIN35_ROOT_ADMISSION_PROFILE
if($f.PSIsContainer -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'invalid profile'}
$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$acl=Get-Acl -LiteralPath $f.FullName
$owner=(New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
if($owner -ne $me){throw 'owner mismatch'}
foreach($rule in $acl.Access){
 if($rule.AccessControlType -eq 'Allow'){
  $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
  if($sid -notin @($me,'S-1-5-18','S-1-5-32-544')){throw 'broad ACL'}
 }
}
Get-Content -LiteralPath $f.FullName -Raw
'''
    environment = dict(os.environ, WIN35_ROOT_ADMISSION_PROFILE=str(path))
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
                            capture_output=True, text=True, env=environment,
                            timeout=10, check=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True,
                        help="Fixed provisioner-owned private profile; no identity overrides")
    args = parser.parse_args()
    allowed = False
    reason = "preflight denied"
    try:
        if platform.system() != "Windows":
            raise ValueError("wrong platform")
        profile = load_private_profile(pathlib.Path(args.profile))
        executable = pathlib.Path(profile["codex_exe"])
        if platform.node() != profile["expected_host"]:
            raise ValueError("wrong host")
        if not executable.is_absolute() or not executable.is_file() or executable.is_symlink():
            raise ValueError("invalid executable")
        def digest():
            with executable.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        pin = profile["sha256"].lower()
        expected_account = profile["expected_account_fingerprint"]
        if len(pin) != 64 or digest() != pin:
            raise ValueError("pin mismatch")
        limits, account = read_limits(executable)
        if len(expected_account) != 64 or account_fingerprint(account) != expected_account:
            raise ValueError("account binding mismatch")
        allowed, reason = decision(limits, account.get("type"))
        if digest() != pin:
            allowed, reason = False, "pin changed during preflight"
    except Exception as exc:
        reason = "quota unavailable (" + type(exc).__name__ + ")"
    print(json.dumps({"provider": "codex", "launch_allowed": allowed,
                      "reason": reason, "observed_at": int(time.time()),
                      "source": "local-app-server/account-rateLimits-read"}))
    return 0 if allowed else 75


if __name__ == "__main__":
    raise SystemExit(main())
