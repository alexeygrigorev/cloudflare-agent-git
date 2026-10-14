#!/usr/bin/env python3
"""Fresh quse gate for real OpenAI Codex launches, never reset redemption.

Implements owner-contract.json and Root 07:38 amendment:
- Authenticated Hub /api/quota GET with Bearer token & host_id match.
- Schema 1.0, captured_at aware UTC, status ok, error null, routes map codex.
- Provider observed_at & details.stale held; serverreceived_at cannot launder old data.
- Dynamic safe windows (max 32 windows, name <= 48 chars, alphanumeric-hyphen-underscore).
- Optional absent window N/A rules; mandatory weekly window > 15% reserve.
- Hard snapshot age < 1200s on every fetch AND every cache hit; future invalid; cap cannot be extended.
- Short local cache (default <= 30s) with optional safe private cache file (mode 600, no tokens, config-bound).
- Hub unreachable triggers fallback to direct quse codex --json (timeout 45) exactly ONCE.
- Auth 401/403/malformed/schema/error bodies MUST NOT fallback.
- Config unset executes fresh local quse route; configured missing auth/host/invalid fails closed.
- No raw token / URL userinfo / query / error / reset value leaks.
"""
import datetime
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

DEFAULT_CACHE_TTL_SEC = 30.0
MAX_SNAPSHOT_STALENESS_SEC = 1200.0  # Hard 20-minute cap
DEFAULT_CONFIG_PATH = Path(".local/quota-hub.json")
DEFAULT_CACHE_FILE = Path(".local/cache/quota-gate-cache.json")
MAX_CACHE_FILE_SIZE = 65536  # 64 KB
MAX_WINDOWS_COUNT = 32
MAX_WINDOW_NAME_LEN = 48
WINDOW_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
FALLBACK_TIMEOUT_SEC = 45

STRICT_HUB_WEEKLY_WINDOWS = frozenset({"7d", "weekly"})
CANONICAL_WEEKLY_WINDOWS = frozenset({
    "7d", "weekly", "week", "7_day", "7-day", "codex_7d", "codex_weekly"
})
FORBIDDEN_HUB_WEEKLY_ALIASES = frozenset({
    "week", "7_day", "7-day", "codex_7d", "codex_weekly", "weekend"
})

CANONICAL_CONFIG_KEYS = frozenset({
    "hub_url",
    "token",
    "host_id",
    "cache_ttl_sec",
    "max_staleness_sec",
    "cache_file",
    "timeout_sec",
})

HUB_ENV_KEYS = (
    "QUOTA_HUB_CONFIG",
    "QUOTA_HUB_URL",
    "QUOTA_HUB_HOST",
    "QUOTA_HUB_TOKEN",
    "QUOTA_HUB_HOST_ID",
    "QUOTA_CACHE_TTL",
    "QUOTA_CACHE_MAX_STALENESS",
    "QUOTA_CACHE_FILE",
    "QUOTA_HUB_TIMEOUT",
)

FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "account",
    "accounts",
    "credits",
    "credit",
    "balance",
    "balances",
    "subscription",
    "subscriptions",
    "tokens",
    "token",
    "api_key",
    "apikey",
    "secret",
    "secrets",
    "password",
    "credentials",
    "credential",
    "model_usage",
    "modelusage",
    "authority",
    "root_authority",
    "task_authority",
    "edit_authorized",
    "review_authorized",
})

ALLOWED_CACHE_ENTRY_KEYS = frozenset({
    "config_key",
    "host_id",
    "cached_at",
    "captured_at",
    "serverreceived_at",
    "codex_record",
})
REQUIRED_CACHE_ENTRY_KEYS = frozenset({
    "config_key",
    "host_id",
    "cached_at",
    "captured_at",
    "codex_record",
})

SAFE_ERROR_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "auth", "authentication", "available",
    "bad", "boolean", "by", "cache", "cache_file", "cache_ttl_sec", "cached_at",
    "cannot", "captured_at", "clock", "codex", "codex_record", "config",
    "config_key", "configuration", "connection", "contradictory", "corrupt",
    "cutoff", "data", "datetime", "degraded", "detected", "details", "dictionary",
    "empty", "entry", "error", "exceeds", "expected", "expired", "failed",
    "failure", "fallback", "field", "file", "finite", "flag", "floor", "for",
    "forbidden", "found", "from", "future", "gate", "gateway", "got",
    "has_grok_code_access", "header", "host", "host_id", "http", "hub", "hub_url",
    "in", "internal", "invalid", "is", "json", "key", "keys", "launch", "limit",
    "limit_reached", "limited", "local", "malformed", "many", "marked", "match",
    "max", "max_staleness_sec", "minimum", "mismatch", "missing", "mode", "must",
    "na", "naive", "name", "negative", "network", "no", "non", "none", "not",
    "null", "number", "numeric", "object", "observed_at", "of", "offset", "ok",
    "on", "only", "or", "out", "parse", "past", "path", "percent",
    "percent_remaining", "permissions", "port", "positive", "present", "provider",
    "query", "quota", "range", "rate", "reached", "read", "reading", "record",
    "refused", "regular", "remaining", "reported", "request", "required",
    "reserve", "reset", "reset_at", "response", "rolling", "route", "routes",
    "schema", "schema_version", "sec", "seconds", "server", "serverreceived_at",
    "service", "size", "snapshot", "stale", "staleness", "stat", "status",
    "string", "strings", "symlink", "tamper", "tampered", "the", "time",
    "timeout", "timeout_sec", "timestamp", "timestamps", "timezone", "to",
    "token", "too", "top", "ttl", "type", "unauthorized", "unavailable",
    "unexpected", "unknown", "unreachable", "unsupported", "upstream", "url",
    "use", "userinfo", "utc", "valid", "value", "values", "version", "via",
    "weekly", "whitespace", "window", "windows", "with", "without", "zero",
    "0o600", "401", "403", "404", "500", "502", "503", "504", "1.0",
    "5h", "7d", "monthly", "daily", "grok", "jsondecodeerror", "typeerror",
    "valueerror", "oserror", "timeouterror", "urlerror", "httperror",
    "calledprocesserror", "timeoutexpired", "filenotfounderror",
    "account", "accounts", "credits", "credit", "balance", "balances",
    "subscription", "subscriptions", "tokens", "api_key", "apikey",
    "secret", "secrets", "password", "credentials", "credential",
    "model_usage", "modelusage", "authority", "root_authority",
    "task_authority", "edit_authorized", "review_authorized",
})


class QuotaGateError(Exception):
    """Base exception for quota gate errors."""
    pass


class HubAuthError(QuotaGateError):
    """HTTP 401 / 403 authentication error; MUST NOT fallback."""
    pass


class HubSchemaError(QuotaGateError):
    """Schema, validation, or response error; MUST NOT fallback."""
    pass


class HubConfigError(QuotaGateError):
    """Configuration error for Hub; MUST NOT fallback."""
    pass


class CacheTamperError(QuotaGateError):
    """Insecure, tampered, corrupt, or invalid persistent cache file; MUST NOT fallback."""
    pass


# Alias for compatibility with spec
TamperError = CacheTamperError


class HubUnreachableError(QuotaGateError):
    """Network, connection, or 502/503/504 error; triggers fallback."""
    pass


def _is_weekly_window(name: str, strict_hub: bool = False) -> bool:
    if not isinstance(name, str):
        return False
    if strict_hub:
        return name in STRICT_HUB_WEEKLY_WINDOWS
    return name.lower() in CANONICAL_WEEKLY_WINDOWS


def _parse_iso_datetime(val: Any, allow_datetime: bool = True) -> Optional[datetime.datetime]:
    if isinstance(val, datetime.datetime):
        return val if allow_datetime else None
    if not isinstance(val, str) or not val:
        return None
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in val):
        return None
    try:
        clean = val.replace("UTC", "+00:00").replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _parse_aware_not_future(
    ts_val: Any,
    now_dt: datetime.datetime,
    field_name: str,
    allow_datetime: bool = False,
) -> Tuple[Optional[datetime.datetime], Optional[str]]:
    """Validate that ts_val is a timezone-aware ISO timestamp (or datetime if allowed) and not in the future."""
    if ts_val is None:
        return None, f"missing {field_name} timestamp"
    if not allow_datetime and not isinstance(ts_val, str):
        return None, f"invalid or timezone-naive {field_name} timestamp"
    dt = _parse_iso_datetime(ts_val, allow_datetime=allow_datetime)
    if dt is None or dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return None, f"invalid or timezone-naive {field_name} timestamp"
    age_sec = (now_dt - dt).total_seconds()
    if age_sec < 0.0:
        return None, f"{field_name} is in the future"
    return dt, None


def _validate_timestamp_freshness(
    ts_val: Any,
    now_dt: datetime.datetime,
    max_staleness_sec: float,
    field_name: str,
    allow_datetime: bool = False,
    cap_at_max_staleness: bool = True,
) -> Tuple[Optional[datetime.datetime], Optional[str]]:
    """Strictly validate that a timestamp is timezone-aware, not in the future, and not stale.

    Future tolerance: 0.0s (no grace period, dt > now_dt is rejected).
    Staleness cutoff: age_sec >= min(max_staleness_sec, MAX_SNAPSHOT_STALENESS_SEC).
    """
    dt, err = _parse_aware_not_future(ts_val, now_dt, field_name, allow_datetime=allow_datetime)
    if err is not None or dt is None:
        return None, err
    cutoff = min(float(max_staleness_sec), MAX_SNAPSHOT_STALENESS_SEC) if cap_at_max_staleness else float(max_staleness_sec)
    age_sec = (now_dt - dt).total_seconds()
    if age_sec >= cutoff:
        return None, f"{field_name} is stale"
    return dt, None


def _sanitize_error(val: Any) -> str:
    if val is None or isinstance(val, (bool, int, float, dict, list)):
        return "unavailable"
    if not isinstance(val, str) or not val.strip():
        return "unavailable"
    # Redact URL userinfo
    val = re.sub(r"://[^/@\s]+@", "://[REDACTED]@", val)
    # Redact URL query strings (e.g., ?code=123)
    val = re.sub(r"\?[^\s]*", "?[REDACTED]", val)
    # Redact Bearer tokens specifically (handles "Bearer secret", "Bearer: secret", "auth: Bearer secret")
    val = re.sub(r"(?i)\bbearer[\s:=]+[^\s,;]+", "Bearer [REDACTED]", val)
    # Redact common credentials/token patterns
    val = re.sub(
        r"(?i)\b(bearer|token|key|secret|password|auth|credential|code)[\s:=]+[^\s,;]+",
        r"\1=[REDACTED]",
        val,
    )
    # Redact long token-like hex/alphanumeric strings (16+ chars)
    val = re.sub(r"\b[a-zA-Z0-9_\-]{16,}\b", "[REDACTED]", val)
    # Redact filesystem paths
    val = re.sub(r"(/[\w.\-]+)+", "[PATH]", val)

    # Whitelist-based token filter so arbitrary short secrets (e.g. db_pass_9999, err_my_sec_99) never leak
    out_tokens: List[str] = []
    for raw_tok in val.split():
        if "[REDACTED]" in raw_tok or "[PATH]" in raw_tok:
            tok_out = "[REDACTED]" if "[REDACTED]" in raw_tok else "[PATH]"
        else:
            clean_word = raw_tok.strip("(),;:.!?'\"")
            if clean_word and clean_word.lower() in SAFE_ERROR_WORDS:
                tok_out = raw_tok
            else:
                tok_out = "[REDACTED]"
        if tok_out == "[REDACTED]" and out_tokens and out_tokens[-1] == "[REDACTED]":
            continue
        out_tokens.append(tok_out)

    res = " ".join(out_tokens) if out_tokens else "unavailable"
    if len(res) > 80:
        res = res[:77] + "..."
    return res


def _validate_clock(now: Any) -> Tuple[Optional[datetime.datetime], Optional[str]]:
    """Validate reference clock input, returning (now_dt, error_reason)."""
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc), None
    if isinstance(now, bool):
        return None, "invalid reference clock: boolean not allowed"
    if isinstance(now, (int, float)):
        if not math.isfinite(now):
            return None, "invalid reference clock: non-finite timestamp"
        try:
            return datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc), None
        except (OverflowError, OSError, ValueError):
            return None, "invalid reference clock: timestamp out of range"
    if isinstance(now, str):
        dt = _parse_iso_datetime(now, allow_datetime=False)
        if dt is None:
            return None, "invalid reference clock: malformed timestamp string"
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return None, "invalid reference clock: naive timestamp missing timezone"
        return dt, None
    if isinstance(now, datetime.datetime):
        if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            return None, "invalid reference clock: naive datetime missing timezone"
        return now, None
    return None, "invalid reference clock: unexpected type"


def _validate_non_empty_no_ws(val: Any, field_label: str) -> str:
    if not isinstance(val, str) or not val:
        raise HubConfigError(f"Configured Hub missing {field_label}")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in val):
        raise HubConfigError(f"Invalid {field_label}: whitespace or control characters not allowed")
    return val


def _validate_hub_url(url: Any) -> str:
    if not isinstance(url, str) or not url:
        raise HubConfigError("Hub URL must be a non-empty string")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        raise HubConfigError("Hub URL must not contain whitespace or control characters")
    if not url.startswith(("http://", "https://")):
        raise HubConfigError("Hub URL must use http:// or https://")
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        raise HubConfigError("Invalid Hub URL") from None

    if parsed.scheme not in ("http", "https"):
        raise HubConfigError("Hub URL must use http:// or https://")
    if not parsed.netloc or not parsed.hostname:
        raise HubConfigError("Hub URL missing valid host")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise HubConfigError("Hub URL must not contain userinfo")
    if parsed.query or "?" in url:
        raise HubConfigError("Hub URL must not contain query parameters")
    if parsed.fragment or "#" in url or ";" in url:
        raise HubConfigError("Hub URL must not contain fragments")

    # Strictly validate port (1..65535) and reject trailing empty colon, leading zero, or non-numeric port
    try:
        port = parsed.port
    except ValueError:
        raise HubConfigError("Invalid Hub URL port") from None

    if parsed.netloc.startswith("["):
        if "]" not in parsed.netloc:
            raise HubConfigError("Invalid Hub URL host")
        after_bracket = parsed.netloc.split("]", 1)[1]
        if after_bracket:
            if not after_bracket.startswith(":"):
                raise HubConfigError("Invalid Hub URL port")
            port_str = after_bracket[1:]
            if (
                not port_str
                or not port_str.isascii()
                or not port_str.isdigit()
                or port_str.startswith("0")
                or port is None
                or not (1 <= port <= 65535)
            ):
                raise HubConfigError("Invalid Hub URL port")
    else:
        if ":" in parsed.netloc:
            host_only, port_str = parsed.netloc.split(":", 1)
            if (
                not host_only
                or not port_str
                or ":" in port_str
                or not port_str.isascii()
                or not port_str.isdigit()
                or port_str.startswith("0")
            ):
                raise HubConfigError("Invalid Hub URL port")
            if port is None or not (1 <= port <= 65535):
                raise HubConfigError("Invalid Hub URL port")
        hostname = parsed.hostname
        if (
            hostname.startswith((".", "-"))
            or hostname.endswith((".", "-"))
            or ".." in hostname
            or not re.match(r"^[a-zA-Z0-9.\-]+$", hostname)
        ):
            raise HubConfigError("Invalid Hub URL host")

    if "//" in parsed.path:
        raise HubConfigError("Unsupported Hub URL path")
    clean_path = parsed.path.rstrip("/")
    if clean_path not in ("", "/api/quota"):
        raise HubConfigError("Unsupported Hub URL path")

    return f"{parsed.scheme}://{parsed.netloc}"


def _get_api_quota_endpoint(base_url: str) -> str:
    cleaned = _validate_hub_url(base_url)
    return f"{cleaned}/api/quota"


def _validate_positive_Or_nonneg_float(val: Any, name: str, allow_zero: bool) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise HubConfigError(f"Invalid {name} configuration")
    f = float(val)
    if not math.isfinite(f):
        raise HubConfigError(f"Invalid {name} configuration: non-finite number")
    if allow_zero:
        if f < 0.0:
            raise HubConfigError(f"Invalid {name} configuration: negative value")
    else:
        if f <= 0.0:
            raise HubConfigError(f"Invalid {name} configuration: non-positive value")
    return f


def _validate_cache_file_arg(cache_file: Any) -> Optional[Path]:
    if cache_file is None:
        return None
    if isinstance(cache_file, bool) or not isinstance(cache_file, (str, Path)):
        raise HubConfigError("Invalid cache_file configuration")
    s = str(cache_file)
    if not s or not s.strip() or any(ord(c) < 32 or ord(c) == 127 for c in s):
        raise HubConfigError("Invalid cache_file configuration")
    return Path(cache_file)


class HubConfig:
    def __init__(
        self,
        hub_url: Optional[str] = None,
        token: Optional[str] = None,
        host_id: Optional[str] = None,
        cache_ttl_sec: float = DEFAULT_CACHE_TTL_SEC,
        max_staleness_sec: float = MAX_SNAPSHOT_STALENESS_SEC,
        cache_file: Optional[Union[str, Path]] = None,
        timeout_sec: float = 10.0,
        is_configured: bool = False,
    ):
        if not isinstance(is_configured, bool):
            raise HubConfigError("Invalid is_configured flag")
        self.is_configured = is_configured
        if self.is_configured:
            if not isinstance(hub_url, str) or not hub_url:
                raise HubConfigError("Configured Hub missing URL")
            self.hub_url = _validate_hub_url(hub_url)
            self._token = _validate_non_empty_no_ws(token, "authentication token")
            self.host_id = _validate_non_empty_no_ws(host_id, "host_id")

            ttl_val = _validate_positive_Or_nonneg_float(cache_ttl_sec, "cache_ttl_sec", allow_zero=True)
            self.cache_ttl_sec = min(ttl_val, 30.0)

            stale_val = _validate_positive_Or_nonneg_float(max_staleness_sec, "max_staleness_sec", allow_zero=False)
            self.max_staleness_sec = min(stale_val, MAX_SNAPSHOT_STALENESS_SEC)

            self.timeout_sec = _validate_positive_Or_nonneg_float(timeout_sec, "timeout_sec", allow_zero=False)
            self.cache_file = _validate_cache_file_arg(cache_file)
        else:
            self.hub_url = None
            self._token = None
            self.host_id = None
            self.cache_ttl_sec = DEFAULT_CACHE_TTL_SEC
            self.max_staleness_sec = MAX_SNAPSHOT_STALENESS_SEC
            self.cache_file = None
            self.timeout_sec = 10.0

    @property
    def token(self) -> Optional[str]:
        return self._token

    def __repr__(self) -> str:
        masked_url = "[REDACTED]" if self.hub_url else "None"
        masked_host = "[REDACTED]" if self.host_id else "None"
        masked_token = "[REDACTED]" if self._token else "None"
        return (
            f"HubConfig(is_configured={self.is_configured}, "
            f"hub_url={masked_url}, host_id={masked_host}, token={masked_token})"
        )


def _parse_env_float(raw: str, name: str, allow_zero: bool) -> float:
    if not isinstance(raw, str) or not raw.strip() or any(c.isspace() or ord(c) < 32 for c in raw):
        raise HubConfigError(f"Invalid {name} configuration")
    try:
        f = float(raw)
    except (ValueError, TypeError):
        raise HubConfigError(f"Invalid {name} configuration") from None
    return _validate_positive_Or_nonneg_float(f, name, allow_zero=allow_zero)


def load_config(config_path: Optional[Union[str, Path]] = None) -> HubConfig:
    """Load and validate Hub configuration using key presence and strict types.

    If Hub is unconfigured, returns HubConfig(is_configured=False).
    If Hub is configured (any Hub env key present, explicit config_path, or default config file exists)
    but missing auth/host or malformed, raises HubConfigError.
    """
    has_env_cfg_path = "QUOTA_HUB_CONFIG" in os.environ
    env_config_path = os.environ.get("QUOTA_HUB_CONFIG")

    if config_path is not None:
        if isinstance(config_path, bool) or not isinstance(config_path, (str, Path)):
            raise HubConfigError("Invalid config file path")
        if isinstance(config_path, str) and (not config_path.strip() or any(ord(c) < 32 for c in config_path)):
            raise HubConfigError("Invalid config file path")
        explicit_path: Optional[Union[str, Path]] = config_path
    elif has_env_cfg_path:
        if not env_config_path or not env_config_path.strip() or any(ord(c) < 32 for c in env_config_path):
            raise HubConfigError("Invalid config file path")
        explicit_path = env_config_path
    else:
        explicit_path = None

    cfg_file = Path(explicit_path) if explicit_path is not None else DEFAULT_CONFIG_PATH

    file_dict: Dict[str, Any] = {}
    file_found = False

    if explicit_path is not None:
        if os.path.islink(cfg_file) or not cfg_file.is_file():
            raise HubConfigError("Configured quota hub file not found")
        try:
            content = cfg_file.read_text(encoding="utf-8")
            loaded = json.loads(content)
        except json.JSONDecodeError:
            raise HubConfigError("Malformed config file JSON") from None
        except OSError:
            raise HubConfigError("Cannot read config file") from None
        if not isinstance(loaded, dict):
            raise HubConfigError("Config file must contain a JSON object")
        file_dict = loaded
        file_found = True
    elif os.path.lexists(cfg_file):
        if os.path.islink(cfg_file) or not cfg_file.is_file():
            raise HubConfigError("Invalid default config file")
        try:
            content = cfg_file.read_text(encoding="utf-8")
            loaded = json.loads(content)
        except json.JSONDecodeError:
            raise HubConfigError("Malformed default config file JSON") from None
        except OSError:
            raise HubConfigError("Cannot read default config file") from None
        if not isinstance(loaded, dict):
            raise HubConfigError("Default config file must contain a JSON object")
        file_dict = loaded
        file_found = True

    any_env_present = any(k in os.environ for k in HUB_ENV_KEYS)
    is_configured = bool(file_found or any_env_present or config_path is not None)
    if not is_configured:
        return HubConfig(is_configured=False)

    # Reject non-canonical environment alias QUOTA_HUB_HOST
    if "QUOTA_HUB_HOST" in os.environ:
        raise HubConfigError("Unsupported non-canonical configuration key")

    # Reject unknown or non-canonical keys and explicit null values in file_dict
    for k, v in file_dict.items():
        if k not in CANONICAL_CONFIG_KEYS:
            raise HubConfigError("Unsupported or unknown configuration key")
        if v is None:
            raise HubConfigError(f"Invalid {k} configuration: null not allowed")

    raw_url = os.environ["QUOTA_HUB_URL"] if "QUOTA_HUB_URL" in os.environ else file_dict.get("hub_url")
    raw_token = os.environ["QUOTA_HUB_TOKEN"] if "QUOTA_HUB_TOKEN" in os.environ else file_dict.get("token")
    raw_host_id = os.environ["QUOTA_HUB_HOST_ID"] if "QUOTA_HUB_HOST_ID" in os.environ else file_dict.get("host_id")

    if "QUOTA_CACHE_TTL" in os.environ:
        ttl = _parse_env_float(os.environ["QUOTA_CACHE_TTL"], "cache_ttl_sec", allow_zero=True)
    elif "cache_ttl_sec" in file_dict:
        ttl = _validate_positive_Or_nonneg_float(file_dict["cache_ttl_sec"], "cache_ttl_sec", allow_zero=True)
    else:
        ttl = DEFAULT_CACHE_TTL_SEC

    if "QUOTA_CACHE_MAX_STALENESS" in os.environ:
        max_staleness = _parse_env_float(os.environ["QUOTA_CACHE_MAX_STALENESS"], "max_staleness_sec", allow_zero=False)
    elif "max_staleness_sec" in file_dict:
        max_staleness = _validate_positive_Or_nonneg_float(file_dict["max_staleness_sec"], "max_staleness_sec", allow_zero=False)
    else:
        max_staleness = MAX_SNAPSHOT_STALENESS_SEC

    if "QUOTA_HUB_TIMEOUT" in os.environ:
        timeout = _parse_env_float(os.environ["QUOTA_HUB_TIMEOUT"], "timeout_sec", allow_zero=False)
    elif "timeout_sec" in file_dict:
        timeout = _validate_positive_Or_nonneg_float(file_dict["timeout_sec"], "timeout_sec", allow_zero=False)
    else:
        timeout = 10.0

    if "QUOTA_CACHE_FILE" in os.environ:
        raw_cache_file: Any = os.environ["QUOTA_CACHE_FILE"]
    elif "cache_file" in file_dict:
        raw_cache_file = file_dict["cache_file"]
    else:
        raw_cache_file = None

    return HubConfig(
        hub_url=raw_url,
        token=raw_token,
        host_id=raw_host_id,
        cache_ttl_sec=ttl,
        max_staleness_sec=max_staleness,
        cache_file=raw_cache_file,
        timeout_sec=timeout,
        is_configured=True,
    )


def _check_no_forbidden_keys(mapping: Dict[str, Any]) -> Optional[str]:
    for k in mapping.keys():
        if isinstance(k, str) and k.lower() in FORBIDDEN_PAYLOAD_KEYS:
            return f"forbidden field {k}"
    return None


def _validate_window_entry(
    name: Any,
    win: Any,
    now_dt: datetime.datetime,
    is_hub_record: bool,
) -> Tuple[Optional[float], Optional[str]]:
    """Centralized canonical validation for a single quota window entry.

    Returns (evaluated_percent_or_None_if_NA, error_reason_or_None).
    """
    if not isinstance(name, str) or len(name) > MAX_WINDOW_NAME_LEN or not WINDOW_NAME_REGEX.match(name):
        return None, "invalid window name"

    if is_hub_record and name.lower() in FORBIDDEN_HUB_WEEKLY_ALIASES:
        return None, "non-canonical weekly window alias not permitted"

    is_weekly = _is_weekly_window(name, strict_hub=is_hub_record)

    if not isinstance(win, dict):
        return None, f"window '{name}' malformed: expected dictionary"

    forb_win = _check_no_forbidden_keys(win)
    if forb_win:
        return None, f"window '{name}' {forb_win}"

    if "has_grok_code_access" in win:
        return None, f"window '{name}' forbidden has_grok_code_access field"

    if is_hub_record and "reset" in win:
        return None, f"window '{name}' non-canonical reset alias not permitted"

    # Window-level error flag, status, and boolean flags checked BEFORE N/A skip
    if "error" in win and win["error"] is not None:
        return None, f"window '{name}' reported error: {_sanitize_error(win['error'])}"

    if "status" in win and win.get("status") != "ok":
        return None, f"window '{name}' status not ok"

    if "stale" in win and win["stale"] is not None:
        if not isinstance(win["stale"], bool):
            return None, f"window '{name}' invalid stale flag"
        if win["stale"] is True:
            return None, f"window '{name}' marked stale"

    if "limit_reached" in win and win["limit_reached"] is not None:
        if not isinstance(win["limit_reached"], bool):
            return None, f"window '{name}' invalid limit_reached flag"
        if win["limit_reached"] is True:
            return None, f"window '{name}' limit reached"

    if "rolling" in win and win["rolling"] is not None:
        if not isinstance(win["rolling"], bool):
            return None, f"window '{name}' invalid rolling flag"

    if "present" in win and win["present"] is not None:
        if not isinstance(win["present"], bool):
            return None, f"window '{name}' invalid present flag"

    win_details = win.get("details")
    if isinstance(win_details, dict):
        forb_wdet = _check_no_forbidden_keys(win_details)
        if forb_wdet:
            return None, f"window '{name}' {forb_wdet}"
        if "has_grok_code_access" in win_details:
            return None, f"window '{name}' forbidden has_grok_code_access field"
        if win_details.get("limit_reached") is True:
            return None, f"window '{name}' limit reached"
        if "limit_reached" in win_details and win_details["limit_reached"] is not None and not isinstance(win_details["limit_reached"], bool):
            return None, f"window '{name}' invalid limit_reached flag"
        if win_details.get("stale") is True:
            return None, f"window '{name}' marked stale"
        if "stale" in win_details and win_details["stale"] is not None and not isinstance(win_details["stale"], bool):
            return None, f"window '{name}' invalid stale flag"
    elif win_details is not None:
        return None, f"window '{name}' malformed details: expected dictionary"

    # Resolve reset fields strictly by `is not None` (never treat `""` as None!)
    raw_reset_at = win["reset_at"] if "reset_at" in win else None
    raw_reset_alias = win["reset"] if ("reset" in win and not is_hub_record) else None

    has_reset_at = raw_reset_at is not None
    has_reset_alias = raw_reset_alias is not None

    has_pct = "percent_remaining" in win and win["percent_remaining"] is not None
    has_reset = has_reset_at or has_reset_alias

    # Check present: False contradiction BEFORE empty-string reset check so optional present:False + non-None reset_at fails closed
    if win.get("present") is False:
        if is_weekly:
            return None, f"window '{name}' marked not present"
        if has_pct or has_reset:
            return None, f"window '{name}' marked not present but has non-null reading or reset_at"
        # Truthful ABSENT = N/A (both percent_remaining and reset_at are None)
        return None, None

    # Any non-None empty string reset_at or reset fails closed immediately
    if has_reset_at and raw_reset_at == "":
        return None, f"window '{name}' missing reset timestamp (malformed empty reset_at)"
    if has_reset_alias and raw_reset_alias == "":
        return None, f"window '{name}' missing reset timestamp (malformed empty reset_at)"

    if has_reset_at and has_reset_alias:
        if raw_reset_at != raw_reset_alias:
            dt1 = _parse_iso_datetime(raw_reset_at, allow_datetime=False)
            dt2 = _parse_iso_datetime(raw_reset_alias, allow_datetime=False)
            if dt1 is None or dt2 is None or dt1 != dt2:
                return None, f"window '{name}' contradictory reset timestamps"
        resolved_reset = raw_reset_at
    elif has_reset_at:
        resolved_reset = raw_reset_at
    elif has_reset_alias:
        resolved_reset = raw_reset_alias
    else:
        resolved_reset = None

    # Mandatory weekly window checks
    if is_weekly:
        if not has_pct:
            return None, f"window '{name}' missing required percent_remaining"
        if not has_reset:
            return None, f"window '{name}' missing reset timestamp"
    else:
        if win.get("present") is True:
            if not has_pct:
                return None, f"window '{name}' marked present: true but missing percent_remaining"
            if not has_reset:
                return None, f"window '{name}' marked present: true but missing reset timestamp"

        # Present omitted: empty reading & absent reset is N/A
        if not has_pct and not has_reset:
            return None, None

    # Evaluated window
    if not has_pct:
        return None, f"window '{name}' missing required percent_remaining"

    pct = win["percent_remaining"]
    if isinstance(pct, bool):
        return None, f"window '{name}' invalid percent_remaining: boolean not allowed"
    if not isinstance(pct, (int, float)):
        return None, f"window '{name}' invalid percent_remaining: expected numeric"
    if not math.isfinite(pct):
        return None, f"window '{name}' invalid percent_remaining: non-finite value"
    if pct < 0.0 or pct > 100.0:
        return None, f"window '{name}' percent_remaining {pct:g}% out of range [0, 100]"

    if not has_reset:
        return None, f"window '{name}' missing reset timestamp"

    dt = _parse_iso_datetime(resolved_reset, allow_datetime=False)
    if dt is None:
        return None, f"window '{name}' malformed reset timestamp"

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return None, f"window '{name}' naive reset timestamp: missing timezone"

    if dt <= now_dt:
        return None, f"window '{name}' stale reset timestamp"

    return float(pct), None


def _validate_sibling_hub_route(
    provider_name: Any,
    route_obj: Any,
    now_dt: datetime.datetime,
) -> Optional[str]:
    """Validate sibling provider routes in Hub snapshot against the Hub96 route contract."""
    if not isinstance(provider_name, str) or not provider_name or not WINDOW_NAME_REGEX.match(provider_name):
        return "invalid provider route key"
    if not isinstance(route_obj, dict):
        return "provider route is not a dictionary"
    forb = _check_no_forbidden_keys(route_obj)
    if forb:
        return forb
    if provider_name != "grok" and "has_grok_code_access" in route_obj:
        return "forbidden has_grok_code_access on non-grok route"
    if "status" not in route_obj or route_obj["status"] not in ("ok", "error", "unknown"):
        return "invalid sibling route status"
    if "error" not in route_obj or route_obj["error"] not in (None, "unavailable"):
        return "invalid sibling route error field"
    if "observed_at" in route_obj and route_obj["observed_at"] is not None:
        _, obs_err = _parse_aware_not_future(route_obj["observed_at"], now_dt, "sibling observed_at")
        if obs_err:
            return obs_err
    details = route_obj.get("details")
    if details is not None:
        if not isinstance(details, dict):
            return "invalid sibling route details"
        forb_det = _check_no_forbidden_keys(details)
        if forb_det:
            return forb_det
        if provider_name != "grok" and "has_grok_code_access" in details:
            return "forbidden has_grok_code_access on non-grok route"
        if "has_grok_code_access" in details and details["has_grok_code_access"] is not None:
            if not isinstance(details["has_grok_code_access"], bool):
                return "invalid has_grok_code_access flag"
        if "limit_reached" in details and details["limit_reached"] is not None:
            if not isinstance(details["limit_reached"], bool):
                return "invalid sibling route limit_reached flag"
        if "stale" in details and details["stale"] is not None:
            if not isinstance(details["stale"], bool):
                return "invalid sibling route stale flag"
    windows = route_obj.get("windows")
    if windows is not None:
        if not isinstance(windows, dict) or len(windows) > MAX_WINDOWS_COUNT:
            return "invalid sibling route windows"
        for wname, win in windows.items():
            if not isinstance(wname, str) or len(wname) > MAX_WINDOW_NAME_LEN or not WINDOW_NAME_REGEX.match(wname):
                return "invalid sibling window name"
            if not isinstance(win, dict):
                return "invalid sibling window object"
            forb_win = _check_no_forbidden_keys(win)
            if forb_win:
                return forb_win
            if "reset" in win or "has_grok_code_access" in win:
                return "invalid sibling window field"
            if "error" in win and win["error"] not in (None, "unavailable"):
                return "invalid sibling window error"
            if "present" in win and win["present"] is not None and not isinstance(win["present"], bool):
                return "invalid sibling window present flag"
            if "rolling" in win and win["rolling"] is not None and not isinstance(win["rolling"], bool):
                return "invalid sibling window rolling flag"
            if "percent_remaining" in win and win["percent_remaining"] is not None:
                wpct = win["percent_remaining"]
                if isinstance(wpct, bool) or not isinstance(wpct, (int, float)) or not math.isfinite(wpct) or wpct < 0.0 or wpct > 100.0:
                    return "invalid sibling window percent_remaining"
            if "reset_at" in win and win["reset_at"] is not None:
                wdt = _parse_iso_datetime(win["reset_at"], allow_datetime=False)
                if wdt is None or wdt.tzinfo is None or wdt.tzinfo.utcoffset(wdt) is None:
                    return "invalid sibling window reset_at"
    return None


def _validate_strict_hub_codex_route(
    codex_record: Dict[str, Any],
    now_dt: datetime.datetime,
    max_staleness_sec: float,
) -> None:
    """Strictly validate routes['codex'] against the canonical Hub96 schema."""
    forb = _check_no_forbidden_keys(codex_record)
    if forb:
        raise HubSchemaError(forb)

    if "status" not in codex_record or codex_record["status"] != "ok":
        raise HubSchemaError("Hub codex route status not ok")

    if "error" not in codex_record:
        raise HubSchemaError("Hub codex route missing required error key")
    if codex_record["error"] is not None:
        raise HubSchemaError(f"Hub codex route reported error: {_sanitize_error(codex_record['error'])}")

    if "has_grok_code_access" in codex_record:
        raise HubSchemaError("Forbidden has_grok_code_access on codex route")

    if "present" in codex_record and codex_record["present"] is not None:
        if not isinstance(codex_record["present"], bool) or codex_record["present"] is False:
            raise HubSchemaError("Hub codex route invalid or false present flag")

    if "limit_reached" in codex_record and codex_record["limit_reached"] is not None:
        if not isinstance(codex_record["limit_reached"], bool) or codex_record["limit_reached"] is True:
            raise HubSchemaError("Hub codex route limit reached or invalid flag")

    if "stale" in codex_record and codex_record["stale"] is not None:
        if not isinstance(codex_record["stale"], bool) or codex_record["stale"] is True:
            raise HubSchemaError("Hub codex route marked stale or invalid flag")

    if "observed_at" in codex_record:
        obs_ts = codex_record["observed_at"]
        if obs_ts is None or not isinstance(obs_ts, str):
            raise HubSchemaError("Provider observed_at must be a non-null ISO string")
        _, obs_err = _validate_timestamp_freshness(
            obs_ts, now_dt, max_staleness_sec, "Provider observed_at"
        )
        if obs_err:
            raise HubSchemaError(obs_err)

    if "details" in codex_record and codex_record["details"] is not None:
        details = codex_record["details"]
        if not isinstance(details, dict):
            raise HubSchemaError("Hub codex route details must be a dictionary")
        forb_det = _check_no_forbidden_keys(details)
        if forb_det:
            raise HubSchemaError(forb_det)
        if "has_grok_code_access" in details:
            raise HubSchemaError("Forbidden has_grok_code_access on codex route details")
        if "limit_reached" in details and details["limit_reached"] is not None:
            if not isinstance(details["limit_reached"], bool):
                raise HubSchemaError("Invalid codex details limit_reached flag")
            if details["limit_reached"] is True:
                raise HubSchemaError("Provider details limit reached")
        if "stale" in details and details["stale"] is not None:
            if not isinstance(details["stale"], bool):
                raise HubSchemaError("Invalid codex details stale flag")
            if details["stale"] is True:
                raise HubSchemaError("Provider details marked stale")

    windows = codex_record.get("windows")
    if not isinstance(windows, dict) or not windows:
        raise HubSchemaError("Hub codex route missing windows dictionary")
    if len(windows) > MAX_WINDOWS_COUNT:
        raise HubSchemaError("Hub codex route exceeds maximum windows count")

    has_canonical_weekly = False
    for wname, win in windows.items():
        if isinstance(wname, str) and wname in STRICT_HUB_WEEKLY_WINDOWS:
            has_canonical_weekly = True
        _, win_err = _validate_window_entry(wname, win, now_dt, is_hub_record=True)
        if win_err is not None:
            raise HubSchemaError(win_err)

    if not has_canonical_weekly:
        raise HubSchemaError("Hub codex route missing mandatory canonical 7d/weekly window")


def fetch_hub_snapshot(
    config: HubConfig,
    now: Optional[datetime.datetime] = None,
) -> Tuple[Dict[str, Any], datetime.datetime]:
    """Fetch and validate authenticated Hub /api/quota snapshot."""
    if not isinstance(config, HubConfig) or not config.is_configured:
        raise HubConfigError("Hub is not configured")

    now_dt, clock_err = _validate_clock(now)
    if clock_err or now_dt is None:
        raise HubSchemaError(clock_err or "invalid reference clock")

    endpoint = _get_api_quota_endpoint(config.hub_url)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {config.token}",
        "User-Agent": "quota-gate/1.0",
    }
    req = urllib.request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise HubAuthError(f"Hub authentication failed (HTTP {exc.code})") from None
        if exc.code in (502, 503, 504):
            raise HubUnreachableError(f"Hub service unavailable (HTTP {exc.code})") from None
        raise HubSchemaError(f"Hub request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise HubUnreachableError(f"Hub unreachable: {type(exc).__name__}") from None
    except Exception:
        raise HubConfigError("Invalid Hub request configuration") from None

    try:
        data = json.loads(body)
    except Exception as exc:
        raise HubSchemaError(f"Malformed Hub JSON response: {type(exc).__name__}") from None

    if not isinstance(data, dict):
        raise HubSchemaError("Malformed Hub response: top-level JSON must be an object")

    forb_top = _check_no_forbidden_keys(data)
    if forb_top:
        raise HubSchemaError(forb_top)

    if "schema_version" not in data or data["schema_version"] != "1.0":
        raise HubSchemaError("Unsupported schema_version")

    if "status" not in data or data["status"] != "ok":
        raise HubSchemaError("Hub status not ok")

    if "error" not in data:
        raise HubSchemaError("Hub response missing required error key")
    if data["error"] is not None:
        raise HubSchemaError(f"Hub reported error: {_sanitize_error(data['error'])}")

    if "host_id" not in data or not isinstance(data["host_id"], str) or data["host_id"] != config.host_id:
        raise HubSchemaError("Hub host_id mismatch")

    if "captured_at" not in data or not isinstance(data["captured_at"], str) or not data["captured_at"]:
        raise HubSchemaError("Hub snapshot missing required captured_at timestamp")
    ts_str = data["captured_at"]

    captured_at_dt, cap_err = _validate_timestamp_freshness(
        ts_str, now_dt, config.max_staleness_sec, "Hub captured_at"
    )
    if cap_err or captured_at_dt is None:
        raise HubSchemaError(cap_err or "invalid Hub captured_at")

    srv_ts: Optional[str] = None
    if "serverreceived_at" in data:
        raw_srv = data["serverreceived_at"]
        if raw_srv is None or not isinstance(raw_srv, str):
            raise HubSchemaError("Hub serverreceived_at must be a non-null ISO string")
        _, srv_err = _validate_timestamp_freshness(
            raw_srv, now_dt, config.max_staleness_sec, "Hub serverreceived_at"
        )
        if srv_err:
            raise HubSchemaError(srv_err)
        srv_ts = raw_srv

    routes = data.get("routes")
    if not isinstance(routes, dict) or not routes:
        raise HubSchemaError("Hub response missing routes dictionary")

    if "codex" not in routes:
        raise HubSchemaError("Hub routes missing codex provider")

    for prov_name, route_val in routes.items():
        if prov_name == "codex":
            continue
        sib_err = _validate_sibling_hub_route(prov_name, route_val, now_dt)
        if sib_err:
            raise HubSchemaError(sib_err)

    codex_raw = routes["codex"]
    if not isinstance(codex_raw, dict):
        raise HubSchemaError("Hub codex route is not a dictionary")

    _validate_strict_hub_codex_route(codex_raw, now_dt, config.max_staleness_sec)

    # Return a shallow copy with verified snapshot timestamps attached
    codex_record = dict(codex_raw)
    codex_record["captured_at"] = ts_str
    if srv_ts is not None:
        codex_record["serverreceived_at"] = srv_ts

    return codex_record, captured_at_dt


_IN_PROCESS_CACHE: Dict[str, Any] = {}


def clear_cache() -> None:
    global _IN_PROCESS_CACHE
    _IN_PROCESS_CACHE.clear()


def _get_cache_key(config: HubConfig) -> str:
    raw = f"{config.hub_url}:{config.host_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_persistent_cache(
    config: HubConfig,
    now_dt: datetime.datetime,
) -> Optional[Tuple[Dict[str, Any], datetime.datetime, Optional[datetime.datetime], datetime.datetime]]:
    """Read persistent cache file using centralized timestamp validation.

    If file does not exist, returns None.
    If file exists but has invalid mode, symlink, non-regular, oversize, corrupt JSON,
    mismatched config/host, or invalid/naive/future timestamps, raises CacheTamperError.
    If valid but expired/stale, returns None.
    If valid and fresh, returns (record, captured_at_dt, srv_dt, cached_at_dt).
    """
    if not config.cache_file:
        return None
    cache_path = Path(config.cache_file)
    if not os.path.lexists(cache_path):
        return None

    if os.path.islink(cache_path):
        raise CacheTamperError("Persistent cache is a symlink")

    try:
        st = os.lstat(cache_path)
    except OSError:
        raise CacheTamperError("Cannot stat persistent cache") from None

    if not stat.S_ISREG(st.st_mode):
        raise CacheTamperError("Persistent cache is not a regular file")

    if (st.st_mode & 0o777) != 0o600:
        raise CacheTamperError("Persistent cache invalid permissions")

    if st.st_size > MAX_CACHE_FILE_SIZE:
        raise CacheTamperError("Persistent cache file size exceeds maximum")

    if st.st_size == 0:
        raise CacheTamperError("Persistent cache file is empty")

    try:
        content = cache_path.read_text(encoding="utf-8")
        entry = json.loads(content)
    except Exception:
        raise CacheTamperError("Persistent cache corrupt JSON") from None

    if not isinstance(entry, dict):
        raise CacheTamperError("Persistent cache entry is not a JSON object")

    if not REQUIRED_CACHE_ENTRY_KEYS.issubset(entry.keys()) or not set(entry.keys()).issubset(ALLOWED_CACHE_ENTRY_KEYS):
        raise CacheTamperError("Persistent cache invalid schema keys")

    expected_key = _get_cache_key(config)
    if (
        not isinstance(entry["config_key"], str)
        or entry["config_key"] != expected_key
        or not isinstance(entry["host_id"], str)
        or entry["host_id"] != config.host_id
    ):
        raise CacheTamperError("Persistent cache config_key or host_id mismatch")

    codex_record = entry["codex_record"]
    if not isinstance(codex_record, dict):
        raise CacheTamperError("Persistent cache invalid codex_record")

    forb = _check_no_forbidden_keys(codex_record)
    if forb:
        raise CacheTamperError("Persistent cache contains forbidden fields")

    # 1. Validate format, timezone-awareness, and non-future on all timestamps (tamper check)
    cached_at_dt, cache_ts_err = _parse_aware_not_future(entry["cached_at"], now_dt, "cached_at")
    if cache_ts_err or cached_at_dt is None:
        raise CacheTamperError(cache_ts_err or "invalid cached_at")

    captured_at_dt, cap_ts_err = _parse_aware_not_future(entry["captured_at"], now_dt, "captured_at")
    if cap_ts_err or captured_at_dt is None:
        raise CacheTamperError(cap_ts_err or "invalid captured_at")

    if "captured_at" in codex_record:
        rec_cap_dt, rec_cap_err = _parse_aware_not_future(codex_record["captured_at"], now_dt, "captured_at")
        if rec_cap_err or rec_cap_dt is None or rec_cap_dt != captured_at_dt:
            raise CacheTamperError("Persistent cache captured_at mismatch")

    srv_dt: Optional[datetime.datetime] = None
    if "serverreceived_at" in entry and entry["serverreceived_at"] is not None:
        srv_dt, srv_err = _parse_aware_not_future(entry["serverreceived_at"], now_dt, "serverreceived_at")
        if srv_err or srv_dt is None:
            raise CacheTamperError(srv_err or "invalid serverreceived_at")

    if "serverreceived_at" in codex_record:
        rec_srv_dt, rec_srv_err = _parse_aware_not_future(codex_record["serverreceived_at"], now_dt, "serverreceived_at")
        if rec_srv_err or rec_srv_dt is None:
            raise CacheTamperError(rec_srv_err or "invalid serverreceived_at")
        if srv_dt is not None and rec_srv_dt != srv_dt:
            raise CacheTamperError("Persistent cache serverreceived_at mismatch")
        srv_dt = rec_srv_dt

    obs_dt: Optional[datetime.datetime] = None
    if "observed_at" in codex_record:
        obs_dt, obs_err = _parse_aware_not_future(codex_record["observed_at"], now_dt, "observed_at")
        if obs_err or obs_dt is None:
            raise CacheTamperError(obs_err or "invalid observed_at")

    # 2. Validate freshness/TTL using centralized _validate_timestamp_freshness
    _, ttl_err = _validate_timestamp_freshness(
        cached_at_dt,
        now_dt,
        config.cache_ttl_sec,
        "cached_at",
        allow_datetime=True,
        cap_at_max_staleness=False,
    )
    if ttl_err:
        return None

    _, cap_stale_err = _validate_timestamp_freshness(
        captured_at_dt,
        now_dt,
        config.max_staleness_sec,
        "captured_at",
        allow_datetime=True,
    )
    if cap_stale_err:
        return None

    if srv_dt is not None:
        _, srv_stale_err = _validate_timestamp_freshness(
            srv_dt,
            now_dt,
            config.max_staleness_sec,
            "serverreceived_at",
            allow_datetime=True,
        )
        if srv_stale_err:
            return None

    if obs_dt is not None:
        _, obs_stale_err = _validate_timestamp_freshness(
            obs_dt,
            now_dt,
            config.max_staleness_sec,
            "observed_at",
            allow_datetime=True,
        )
        if obs_stale_err:
            return None

    return codex_record, captured_at_dt, srv_dt, cached_at_dt


def _ensure_safe_target_for_write(cache_path: Path) -> None:
    if os.path.lexists(cache_path):
        if os.path.islink(cache_path):
            raise CacheTamperError("Refusing to write to symlink cache_file")
        try:
            st = os.lstat(cache_path)
        except OSError:
            raise CacheTamperError("Cannot stat cache_file") from None
        if not stat.S_ISREG(st.st_mode):
            raise CacheTamperError("Refusing to write to non-regular cache_file")


def _write_persistent_cache(
    config: HubConfig,
    record: Dict[str, Any],
    cached_at_dt: datetime.datetime,
    captured_at_dt: datetime.datetime,
    serverreceived_at_dt: Optional[datetime.datetime] = None,
) -> None:
    if not config.cache_file:
        return
    cache_path = Path(config.cache_file)
    _ensure_safe_target_for_write(cache_path)

    try:
        parent = cache_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        if os.path.islink(parent):
            raise CacheTamperError("Refusing to write cache_file in symlink directory")

        entry = {
            "config_key": _get_cache_key(config),
            "host_id": config.host_id,
            "cached_at": cached_at_dt.isoformat(),
            "captured_at": captured_at_dt.isoformat(),
            "serverreceived_at": serverreceived_at_dt.isoformat() if serverreceived_at_dt else None,
            "codex_record": record,
        }
        data = json.dumps(entry, indent=2)

        tmp_path = parent / f".tmp_cache_{os.getpid()}_{id(entry)}"
        if os.path.lexists(tmp_path):
            if os.path.islink(tmp_path):
                raise CacheTamperError("Temp cache path is a symlink")
            tmp_path.unlink()

        fd = os.open(
            str(tmp_path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            _ensure_safe_target_for_write(cache_path)
            os.replace(str(tmp_path), str(cache_path))
            os.chmod(str(cache_path), 0o600)
        except Exception:
            try:
                if os.path.lexists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except CacheTamperError:
        raise
    except Exception:
        # Non-tamper filesystem write errors do not crash execution
        pass


def get_cached_record(config: HubConfig, now_dt: datetime.datetime) -> Optional[Dict[str, Any]]:
    now_checked, clock_err = _validate_clock(now_dt)
    if clock_err or now_checked is None:
        return None
    now_dt = now_checked

    key = _get_cache_key(config)
    entry = _IN_PROCESS_CACHE.get(key)
    if entry:
        valid = True
        rec = entry.get("record")
        if not isinstance(rec, dict):
            valid = False

        if valid:
            _, ttl_err = _validate_timestamp_freshness(
                entry.get("cached_at"),
                now_dt,
                config.cache_ttl_sec,
                "cached_at",
                allow_datetime=True,
                cap_at_max_staleness=False,
            )
            if ttl_err:
                valid = False

        if valid:
            _, cap_err = _validate_timestamp_freshness(
                entry.get("captured_at"),
                now_dt,
                config.max_staleness_sec,
                "captured_at",
                allow_datetime=True,
            )
            if cap_err:
                valid = False

        if valid and "captured_at" in rec:
            _, rec_cap_err = _validate_timestamp_freshness(
                rec["captured_at"],
                now_dt,
                config.max_staleness_sec,
                "captured_at",
                allow_datetime=True,
            )
            if rec_cap_err:
                valid = False

        if valid and entry.get("serverreceived_at") is not None:
            _, srv_err = _validate_timestamp_freshness(
                entry.get("serverreceived_at"),
                now_dt,
                config.max_staleness_sec,
                "serverreceived_at",
                allow_datetime=True,
            )
            if srv_err:
                valid = False

        if valid and "serverreceived_at" in rec:
            _, rec_srv_err = _validate_timestamp_freshness(
                rec["serverreceived_at"],
                now_dt,
                config.max_staleness_sec,
                "serverreceived_at",
                allow_datetime=True,
            )
            if rec_srv_err:
                valid = False

        if valid and "observed_at" in rec:
            _, obs_err = _validate_timestamp_freshness(
                rec["observed_at"],
                now_dt,
                config.max_staleness_sec,
                "observed_at",
                allow_datetime=True,
            )
            if obs_err:
                valid = False

        if valid:
            return rec
        _IN_PROCESS_CACHE.pop(key, None)

    # Check persistent cache; CacheTamperError propagates
    res = _read_persistent_cache(config, now_dt)
    if res:
        record, captured_at_dt, srv_dt, cached_at_dt = res
        _IN_PROCESS_CACHE[key] = {
            "cached_at": cached_at_dt,  # Preserve original persistent cached_at; never renew TTL
            "captured_at": captured_at_dt,
            "serverreceived_at": srv_dt,
            "record": record,
        }
        return record

    return None


def store_cached_record(
    config: HubConfig,
    record: Dict[str, Any],
    captured_at_dt: datetime.datetime,
    now_dt: datetime.datetime,
) -> None:
    key = _get_cache_key(config)
    srv_dt: Optional[datetime.datetime] = None
    if "serverreceived_at" in record and record["serverreceived_at"] is not None:
        parsed_srv, srv_err = _parse_aware_not_future(
            record["serverreceived_at"], now_dt, "serverreceived_at", allow_datetime=True
        )
        if srv_err or parsed_srv is None:
            raise HubSchemaError(srv_err or "invalid serverreceived_at")
        srv_dt = parsed_srv

    _write_persistent_cache(config, record, now_dt, captured_at_dt, srv_dt)
    _IN_PROCESS_CACHE[key] = {
        "cached_at": now_dt,
        "captured_at": captured_at_dt,
        "serverreceived_at": srv_dt,
        "record": record,
    }


def _invoke_fallback_and_decide(
    fallback_fn: Optional[Callable[[], Tuple[Optional[Dict[str, Any]], Optional[str]]]] = None,
    now_dt: Optional[datetime.datetime] = None,
    max_staleness_sec: float = MAX_SNAPSHOT_STALENESS_SEC,
) -> Tuple[bool, str]:
    if fallback_fn is not None:
        rec, err = fallback_fn()
        if err is not None or rec is None:
            return False, _sanitize_error(err) if err else "quota fallback failed"
        return decision(rec, now=now_dt, max_staleness_sec=max_staleness_sec, strict_hub=False)

    # Direct quse execution
    result = subprocess.run(
        ["quse", "codex", "--json"],
        capture_output=True,
        text=True,
        timeout=FALLBACK_TIMEOUT_SEC,
        check=True,
    )
    data = json.loads(result.stdout)
    codex_record = data.get("codex") if isinstance(data, dict) else None
    if codex_record is None or not isinstance(codex_record, dict):
        return False, "quota fallback failed: missing codex record"
    return decision(codex_record, now=now_dt, max_staleness_sec=max_staleness_sec, strict_hub=False)


def decision(
    record: Any,
    now: Any = None,
    max_staleness_sec: float = MAX_SNAPSHOT_STALENESS_SEC,
    strict_hub: bool = False,
) -> Tuple[bool, str]:
    # Reference clock validation
    now_dt, clock_err = _validate_clock(now)
    if clock_err or now_dt is None:
        return False, clock_err or "invalid reference clock"

    if isinstance(max_staleness_sec, bool) or not isinstance(max_staleness_sec, (int, float)) or not math.isfinite(max_staleness_sec) or max_staleness_sec <= 0.0:
        return False, "invalid max_staleness_sec configuration"
    effective_max_staleness = min(float(max_staleness_sec), MAX_SNAPSHOT_STALENESS_SEC)

    # Provider-level validations
    if not isinstance(record, dict):
        return False, "malformed record: expected dictionary"

    forb_rec = _check_no_forbidden_keys(record)
    if forb_rec:
        return False, f"hub schema error: {forb_rec}"

    if "has_grok_code_access" in record:
        return False, "forbidden has_grok_code_access on codex record"

    # If record carries Hub envelope timestamps, enforce strict Hub mode
    is_hub_record = bool(strict_hub or "captured_at" in record or "serverreceived_at" in record)

    if "present" in record and record["present"] is not None:
        if not isinstance(record["present"], bool):
            return False, "invalid provider present flag"
        if record["present"] is False:
            return False, "provider marked not present"

    if record.get("status") != "ok":
        return False, "quota unavailable"

    # Falsy non-null errors ('' or 0 or False) must fail closed
    if "error" in record and record["error"] is not None:
        return False, f"provider error: {_sanitize_error(record['error'])}"

    if "limit_reached" in record and record["limit_reached"] is not None:
        if not isinstance(record["limit_reached"], bool):
            return False, "invalid provider limit_reached flag"
        if record["limit_reached"] is True:
            return False, "provider limit reached"

    if "stale" in record and record["stale"] is not None:
        if not isinstance(record["stale"], bool):
            return False, "invalid provider stale flag"
        if record["stale"] is True:
            return False, "provider marked stale"

    details = record.get("details")
    if isinstance(details, dict):
        forb_det = _check_no_forbidden_keys(details)
        if forb_det:
            return False, f"hub schema error: {forb_det}"
        if "has_grok_code_access" in details:
            return False, "forbidden has_grok_code_access in codex details"
        if details.get("limit_reached") is True:
            return False, "provider limit reached"
        if "limit_reached" in details and details["limit_reached"] is not None and not isinstance(details["limit_reached"], bool):
            return False, "invalid provider details limit_reached flag"
        if details.get("stale") is True:
            return False, "provider details marked stale"
        if "stale" in details and details["stale"] is not None and not isinstance(details["stale"], bool):
            return False, "invalid provider details stale flag"
    elif details is not None:
        return False, "malformed provider details"

    # Validate timestamps in record if key is present
    if "captured_at" in record:
        if record["captured_at"] is None:
            return False, "hub schema error: missing captured_at timestamp"
        _, cap_err = _validate_timestamp_freshness(
            record["captured_at"], now_dt, effective_max_staleness, "captured_at"
        )
        if cap_err:
            return False, f"hub schema error: {cap_err}"

    if "serverreceived_at" in record:
        if record["serverreceived_at"] is None:
            return False, "hub schema error: missing serverreceived_at timestamp"
        _, srv_err = _validate_timestamp_freshness(
            record["serverreceived_at"], now_dt, effective_max_staleness, "serverreceived_at"
        )
        if srv_err:
            return False, f"hub schema error: {srv_err}"

    if "observed_at" in record:
        obs_val = record["observed_at"]
        if obs_val is None or not isinstance(obs_val, str):
            return False, "invalid provider observed_at timestamp"
        _, obs_err = _validate_timestamp_freshness(
            obs_val, now_dt, effective_max_staleness, "provider observed_at"
        )
        if obs_err:
            return False, f"provider observed_at error: {obs_err}"

    windows_raw = record.get("windows")
    if windows_raw is None or not isinstance(windows_raw, dict) or not windows_raw:
        return False, "no available quota window"

    # Dynamic safe windows max 32
    if len(windows_raw) > MAX_WINDOWS_COUNT:
        return False, f"too many quota windows: {len(windows_raw)} > max {MAX_WINDOWS_COUNT}"

    # Weekly/7d window is mandatory
    weekly_keys = [k for k in windows_raw.keys() if _is_weekly_window(k, strict_hub=is_hub_record)]
    if not weekly_keys:
        return False, "mandatory 7d/weekly quota window missing"

    evaluated_values = []

    for name, win in windows_raw.items():
        pct_val, win_err = _validate_window_entry(name, win, now_dt, is_hub_record=is_hub_record)
        if win_err is not None:
            return False, win_err
        if pct_val is not None:
            evaluated_values.append((name, pct_val))

    if not evaluated_values:
        return False, "no available quota window"

    min_name, min_remaining = min(evaluated_values, key=lambda x: x[1])
    if min_remaining <= 15.0:
        return False, f"minimum available window {min_remaining:g}% remaining; reserve 15%"

    return True, f"minimum available window {min_remaining:g}% remaining; reserve 15%"


def evaluate_gate(
    argv: Optional[List[str]] = None,
    config: Optional[HubConfig] = None,
    now: Any = None,
    fallback_fn: Optional[Callable[[], Tuple[Optional[Dict[str, Any]], Optional[str]]]] = None,
) -> Tuple[bool, str]:
    now_dt, clock_err = _validate_clock(now)
    if clock_err or now_dt is None:
        return False, clock_err or "invalid reference clock"

    if config is None:
        try:
            config = load_config()
        except HubConfigError as exc:
            return False, f"configuration error: {_sanitize_error(str(exc))}"
    elif not isinstance(config, HubConfig):
        return False, "configuration error: invalid HubConfig instance"

    # 1. Unset config -> direct quse execution
    if not config.is_configured:
        return _invoke_fallback_and_decide(
            fallback_fn=fallback_fn,
            now_dt=now_dt,
            max_staleness_sec=MAX_SNAPSHOT_STALENESS_SEC,
        )

    # 2. Check local cache (persistent tamper errors MUST fail closed without fallback)
    try:
        cached_record = get_cached_record(config, now_dt)
    except CacheTamperError as exc:
        return False, f"cache error: tamper detected ({_sanitize_error(str(exc))})"
    except Exception:
        return False, "cache error"

    if cached_record is not None:
        return decision(
            cached_record,
            now=now_dt,
            max_staleness_sec=config.max_staleness_sec,
            strict_hub=True,
        )

    # 3. Cache miss: fetch from Hub, validate decision, and cache ONLY after validation succeeds
    try:
        codex_record, captured_at_dt = fetch_hub_snapshot(config, now=now_dt)
        allowed, reason = decision(
            codex_record,
            now=now_dt,
            max_staleness_sec=config.max_staleness_sec,
            strict_hub=True,
        )
        if allowed:
            store_cached_record(config, codex_record, captured_at_dt, now_dt)
        return allowed, reason
    except CacheTamperError as exc:
        return False, f"cache error: tamper detected ({_sanitize_error(str(exc))})"
    except HubAuthError as exc:
        return False, f"hub auth error: {_sanitize_error(str(exc))}"
    except HubSchemaError as exc:
        return False, f"hub schema error: {_sanitize_error(str(exc))}"
    except HubConfigError as exc:
        return False, f"configuration error: {_sanitize_error(str(exc))}"
    except HubUnreachableError:
        return _invoke_fallback_and_decide(
            fallback_fn=fallback_fn,
            now_dt=now_dt,
            max_staleness_sec=config.max_staleness_sec,
        )


def main(
    argv: Optional[List[str]] = None,
    config: Optional[HubConfig] = None,
    now: Any = None,
    fallback_fn: Optional[Callable[[], Tuple[Optional[Dict[str, Any]], Optional[str]]]] = None,
) -> int:
    try:
        allowed, reason = evaluate_gate(argv=argv, config=config, now=now, fallback_fn=fallback_fn)
    except Exception as exc:
        allowed, reason = False, f"quota read failed ({type(exc).__name__})"

    output = {"provider": "codex", "launch_allowed": allowed, "reason": reason}
    print(json.dumps(output))
    return 0 if allowed else 75


if __name__ == "__main__":
    sys.exit(main())

