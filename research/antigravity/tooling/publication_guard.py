#!/usr/bin/env python3
"""
Publication Credential Guard (C1601 / C1603 / C1612 / C1614)

Scans public research deliverables, code files, standard input, or git staged
files to prevent accidental leaks of credentials, minted bearer tokens,
credential-bearing URLs, and unredacted local secrets into public commits or reports.

Pure Python standard library only. Zero third-party dependencies.

Reporting Contract:
  <file>:<line>: [RULE_ID] <violation_description>
  NEVER PRINTS THE MATCHED SECRET VALUE! The secret value is omitted or replaced with '***'.

Exit codes:
  0: All scanned targets are clean (zero violations).
  1: Refuse publication (one or more credential violations detected).
  2: Operational error (missing file, unreadable file, binary public target, invalid CLI arguments, git failure).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import List, NamedTuple, Optional, Sequence


class Violation(NamedTuple):
    filepath: str
    lineno: int
    rule_id: str
    description: str

    def format(self) -> str:
        return f"{self.filepath}:{self.lineno}: [{self.rule_id}] {self.description}"


# -----------------------------------------------------------------------------
# Regexes and Pattern Matchers
# -----------------------------------------------------------------------------

# Rule a1: art_v1_ minted task bearer tokens.
ART_V1_RE = re.compile(
    r'\bart_v1_([a-zA-Z0-9_-]{20,}(?:(?:\?|%3[Ff]|&)[^\s"\'`<>]+)?)'
)

# Rule a2: High-entropy bearer tokens (tok_ prefix).
TOK_RE = re.compile(r'\btok_([a-zA-Z0-9_-]{16,})\b')

# Rule a3: Authorization Bearer headers (Defect D2 fix: catches quotes, single quotes, JSON headers).
AUTH_BEARER_RE = re.compile(
    r'(?i:\b"?Authorization"?:\s*"?Bearer"?)\s+["\'`]?([^\s"\'`]+)["\'`]?'
)
AUTH_HEADER_ONLY_RE = re.compile(
    r'^\s*"?Authorization"?:\s*$', re.IGNORECASE
)
AUTH_BEARER_TRAIL_RE = re.compile(
    r'^\s*"?Authorization"?:\s*"?Bearer"?\s*$', re.IGNORECASE
)
BEARER_SOLO_RE = re.compile(
    r'^\s*"?Bearer"?\s+["\'`]?([^\s"\'`]+)["\'`]?', re.IGNORECASE
)

# Rule b: Credential-bearing URLs.
URL_CREDENTIAL_RE = re.compile(
    r'https?://([^/\s:@]+):([^/\s:@]+)@([^\s"\'`<>]+)'
)
URL_USER_ONLY_RE = re.compile(
    r'https?://([^/\s:@]+)@([^\s"\'`<>]+)'
)
URL_QUERY_TOKEN_RE = re.compile(
    r'(?:[?&]|%3[Ff]|%26)(?:token|access_token|key|secret)=([^\s"\'`&<>]+)'
)

# Rule c: Local secret literals.
LOCAL_SECRET_RE = re.compile(
    r'\b((?:admin|runner|sidecar|webhook)[-_](?:shared[-_])?(?:secret|token)[-_])([a-zA-Z0-9_-]+|\[REDACTED[^\]]*\])',
    re.IGNORECASE
)


# -----------------------------------------------------------------------------
# Path and Secret Sanitization
# -----------------------------------------------------------------------------

def sanitize_path_for_display(path_str: str) -> str:
    """Sanitize secrets that might appear in filenames/paths when reporting errors."""
    s = re.sub(r'art_v1_[a-zA-Z0-9_-]{20,}', 'art_v1_***', path_str)
    s = re.sub(r'tok_[a-zA-Z0-9_-]{16,}', 'tok_***', s)
    s = re.sub(
        r'((?:admin|runner|sidecar|webhook)[-_](?:shared[-_])?(?:secret|token)[-_])[a-zA-Z0-9_-]{8,}',
        r'\g<1>***',
        s,
        flags=re.IGNORECASE
    )
    return s


def is_private_path(path_str: str) -> bool:
    """Check if path is a private scratch or unredacted path that must be skipped in directory walking."""
    norm = os.path.normpath(path_str)
    parts = norm.split(os.sep)
    if any(p in ('.git', '__pycache__', 'node_modules') for p in parts):
        return True
    if 'scratch' in parts:
        return True
    if any(p == '.local' for p in parts) and any('scratch' in p for p in parts):
        return True
    if norm.endswith('.unredacted.md'):
        return True
    return False


def is_safe_redacted_token(token: str) -> bool:
    """Check if token is an explicit redaction placeholder or short fixture."""
    t = token.strip().strip('"\'`')
    if (t.startswith('[') and t.endswith(']')) or \
       (t.startswith('<') and t.endswith('>')) or \
       t in ('...', '***'):
        return True
    if len(t) < 20:
        return True
    return False


def is_safe_redacted_url_password(pw: str) -> bool:
    """
    Check if URL password component is safely redacted.
    Allows: <token>, [REDACTED], [REDACTED_TOKEN], art_v1_[REDACTED_HASH]%3Fexpires%3D[REDACTED_EXPIRY],
            ***, ...
    Detects any raw strings like 'dummysecret', 'abc123xyz', 'some_password', raw tokens.
    """
    p = pw.strip().strip('"\'`')
    if (p.startswith('[') and p.endswith(']')) or \
       (p.startswith('<') and p.endswith('>')) or \
       p in ('***', '...'):
        return True

    # Strip all bracketed placeholders [REDACTED...] and <...>
    cleaned = re.sub(r'\[[A-Za-z0-9_-]+\]', '', p)
    cleaned = re.sub(r'<[A-Za-z0-9_-]+>', '', cleaned)
    # Strip known non-secret literal keywords and URL-encoded query structure
    cleaned = re.sub(r'(?i:art_v1_)', '', cleaned)
    cleaned = re.sub(r'(?i:(?:%3f|\?)expires(?:%3d|=)?)', '', cleaned)
    cleaned = re.sub(r'(?i:%3d)', '', cleaned)
    cleaned = re.sub(r'[?&=_.~-]', '', cleaned)

    return len(cleaned) == 0


def is_safe_tok(tok_val: str) -> bool:
    """
    Check if tok_ payload is an allowed documented synthetic fixture or redaction.
    Per C1603, generated dummy values in private fixtures must be detected;
    only documented examples like 'tok_alpha_12345' or explicit public redactions allowed.
    """
    t = tok_val.strip().strip('"\'`')
    if t.startswith('alpha_12345'):
        return True
    if re.search(r'\[REDACTED[^\]]*\]', t, re.IGNORECASE):
        return True
    if t.startswith('<') and t.endswith('>'):
        return True
    return False


def is_safe_local_secret(suffix: str, filepath: str) -> bool:
    """
    Check if local secret suffix is safely redacted or standard documented fixture.
    Allows: [REDACTED...], ***, ..., pinned runbook fixtures (token_12345, secret_12345, dummy_12345),
            or test dummies in test files.
    """
    s = suffix.strip().strip('"\'`')
    if re.search(r'\[REDACTED[^\]]*\]', s, re.IGNORECASE):
        return True
    if s in ('***', '...'):
        return True
    # Pinned standard documented non-sensitive identifiers in runbooks per C1612
    if s in ('token_12345', 'secret_12345', 'dummy_12345') or \
       s.startswith(('token_12345', 'secret_12345', 'dummy_12345')):
        return True
    # In explicit test files, allow standard dummy names
    is_test_file = 'test_' in filepath or '/tests/' in filepath or filepath.startswith('tests/')
    if is_test_file and s.lower() in ('dummy', 'test', 'sample', 'example', 'mock'):
        return True
    return False


# -----------------------------------------------------------------------------
# Content Scanner
# -----------------------------------------------------------------------------

def scan_lines(lines: Sequence[str], filepath: str) -> List[Violation]:
    """Scan lines of text and collect all credential violations."""
    violations: List[Violation] = []

    for idx, line in enumerate(lines):
        lineno = idx + 1

        # 1. Full Minted art_v1_ Bearer Tokens
        for m in ART_V1_RE.finditer(line):
            violations.append(
                Violation(
                    filepath=filepath,
                    lineno=lineno,
                    rule_id="MINTED_TOKEN_ART_V1",
                    description="Unredacted art_v1_ bearer token detected (pattern: art_v1_***)"
                )
            )

        # 2. High-Entropy Bearer Tokens (tok_...)
        for m in TOK_RE.finditer(line):
            tok_payload = m.group(1)
            if not is_safe_tok(tok_payload):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="HIGH_ENTROPY_BEARER_TOKEN",
                        description="High-entropy bearer token detected (pattern: tok_***)"
                    )
                )

        # 3. Authorization Bearer Headers
        # Inline Authorization: Bearer <token>
        for m in AUTH_BEARER_RE.finditer(line):
            token_val = m.group(1)
            if not is_safe_redacted_token(token_val):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="AUTHORIZATION_BEARER_HEADER",
                        description="Unredacted Authorization Bearer header detected (token: ***)"
                    )
                )

        # Multi-line continuation: Authorization: Bearer on previous line, token on current line
        if idx > 0 and AUTH_BEARER_TRAIL_RE.match(lines[idx - 1]):
            stripped = line.strip().strip('"\'`')
            first_word = stripped.split()[0] if stripped else ""
            if first_word and not is_safe_redacted_token(first_word):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="AUTHORIZATION_BEARER_HEADER",
                        description="Unredacted Authorization Bearer header detected across line fold (token: ***)"
                    )
                )

        # Standalone Bearer <token> line (e.g. config or multiline header)
        m_solo = BEARER_SOLO_RE.match(line)
        if m_solo:
            token_val = m_solo.group(1)
            if not is_safe_redacted_token(token_val):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="AUTHORIZATION_BEARER_HEADER",
                        description="Unredacted standalone Bearer token detected (token: ***)"
                    )
                )

        # 4. Credential-Bearing URLs
        for m in URL_CREDENTIAL_RE.finditer(line):
            password_part = m.group(2)
            if not is_safe_redacted_url_password(password_part):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="CREDENTIAL_BEARING_URL",
                        description="Credential-bearing URL detected with unredacted credentials (URL: ***)"
                    )
                )

        # URL user-only check where username contains credentials
        for m in URL_USER_ONLY_RE.finditer(line):
            user_part = m.group(1)
            if user_part not in ('git', 'user', 'username', 'token', 'admin', 'runner', 'sidecar', 'nobody', 'root', 'agent'):
                if (not user_part.startswith(('[', '<')) and not user_part.endswith((']', '>')) and user_part not in ('***', '...')):
                    if ART_V1_RE.search(user_part) or (TOK_RE.search(user_part) and not is_safe_tok(user_part)) or len(user_part) >= 20:
                        violations.append(
                            Violation(
                                filepath=filepath,
                                lineno=lineno,
                                rule_id="CREDENTIAL_BEARING_URL",
                                description="Credential-bearing URL detected with unredacted user identity (URL: ***)"
                            )
                        )

        # URL Query parameter containing unredacted tokens
        for m in URL_QUERY_TOKEN_RE.finditer(line):
            query_token = m.group(1)
            if not is_safe_redacted_token(query_token) and len(query_token) >= 16:
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="CREDENTIAL_BEARING_URL",
                        description="Credential query parameter detected in URL (token: ***)"
                    )
                )

        # 5. Local Secret Literals
        for m in LOCAL_SECRET_RE.finditer(line):
            suffix = m.group(2)
            if len(suffix) >= 8 and not is_safe_local_secret(suffix, filepath):
                violations.append(
                    Violation(
                        filepath=filepath,
                        lineno=lineno,
                        rule_id="LOCAL_SECRET_LITERAL",
                        description="Unredacted local secret literal detected (key: ***)"
                    )
                )

    return violations


def scan_content(content: str, filepath: str) -> List[Violation]:
    """Scan full text content (splitting lines cleanly across CRLF/LF)."""
    lines = content.splitlines()
    return scan_lines(lines, filepath)


def is_binary_content(raw_bytes: bytes) -> bool:
    """Detect binary files to skip scanning raw compiled or image assets."""
    return b'\x00' in raw_bytes[:8192]


def scan_file(filepath: str) -> List[Violation]:
    """Read and scan a single file from disk. Fails closed (exit 2) on binary in explicit targets."""
    try:
        with open(filepath, "rb") as f:
            raw_bytes = f.read()
    except (OSError, IOError) as e:
        sys.stderr.write(f"publication_guard: error: file unreadable: {sanitize_path_for_display(filepath)} ({e})\n")
        sys.exit(2)

    if is_binary_content(raw_bytes):
        sys.stderr.write(
            f"publication_guard: error: binary content or NUL byte detected in file: {sanitize_path_for_display(filepath)}\n"
        )
        sys.exit(2)

    content = raw_bytes.decode("utf-8", errors="replace")
    return scan_content(content, filepath)


# -----------------------------------------------------------------------------
# Git Staged Inspection
# -----------------------------------------------------------------------------

def get_staged_files(explicit_paths: Optional[Sequence[str]] = None) -> List[str]:
    """
    Get list of added, copied, modified, or renamed files in git index.
    Per C1612: Does not skip scratch files; anything staged in git index must be inspected.
    Per C1614: If explicit paths are provided with --staged, filters only to those targets.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        sys.stderr.write(f"publication_guard: error: git diff --cached failed: {e}\n")
        sys.exit(2)

    files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]

    if explicit_paths:
        normalized_targets = set()
        for p in explicit_paths:
            normalized_targets.add(os.path.normpath(p))
            try:
                rel = os.path.relpath(p, start=os.getcwd())
                normalized_targets.add(os.path.normpath(rel))
            except ValueError:
                pass

        filtered = []
        for f in files:
            norm_f = os.path.normpath(f)
            if norm_f in normalized_targets or any(norm_f.startswith(t + os.sep) for t in normalized_targets):
                filtered.append(f)
        return filtered

    return files


def read_staged_content(filepath: str) -> str:
    """
    Read staged blob directly from git index as raw bytes.
    Returns empty string for binary blobs without raising UnicodeDecodeError.
    """
    try:
        proc = subprocess.run(
            ["git", "show", f":{filepath}"],
            capture_output=True,
            check=True
        )
        raw_bytes = proc.stdout
    except subprocess.SubprocessError:
        # Fallback to file on disk if git show fails
        try:
            with open(filepath, "rb") as f:
                raw_bytes = f.read()
        except OSError as e:
            sys.stderr.write(
                f"publication_guard: error: failed to read staged file {sanitize_path_for_display(filepath)}: {e}\n"
            )
            sys.exit(2)

    if is_binary_content(raw_bytes):
        return ""

    return raw_bytes.decode("utf-8", errors="replace")


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publication Credential Guard: Prevent credential leaks into public deliverables."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Explicit file or directory paths to inspect."
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Inspect content read from standard input."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Inspect git staged files from index."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output."
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.paths and not args.stdin and not args.staged:
        sys.stderr.write(
            "publication_guard: error: No targets specified. Provide file/directory paths, --stdin, or --staged.\n"
        )
        return 2

    violations: List[Violation] = []

    # 1. Scan Stdin
    if args.stdin:
        try:
            stdin_content = sys.stdin.read()
            violations.extend(scan_content(stdin_content, filepath="<stdin>"))
        except (OSError, IOError) as e:
            sys.stderr.write(f"publication_guard: error: failed reading from stdin: {e}\n")
            return 2

    # 2. Scan Staged Files (C1614: filtered if explicit paths provided)
    if args.staged:
        staged_files = get_staged_files(explicit_paths=args.paths if args.paths else None)
        for staged_file in staged_files:
            content = read_staged_content(staged_file)
            if content:
                violations.extend(scan_content(content, filepath=staged_file))

    # 3. Scan Explicit Paths (when not in staged mode)
    if not args.staged and args.paths:
        for path_str in args.paths:
            path = Path(path_str)
            if not path.exists():
                sys.stderr.write(f"publication_guard: error: file not found: {sanitize_path_for_display(path_str)}\n")
                return 2

            if path.is_file():
                violations.extend(scan_file(str(path)))
            elif path.is_dir():
                for root, dirs, files in os.walk(str(path)):
                    # Prune private directories during traversal
                    dirs[:] = [
                        d for d in dirs
                        if not is_private_path(os.path.join(root, d))
                    ]
                    for file_name in files:
                        full_file_path = os.path.join(root, file_name)
                        if not is_private_path(full_file_path):
                            # Skip binary assets during directory traversal
                            try:
                                with open(full_file_path, "rb") as bf:
                                    header = bf.read(8192)
                                if is_binary_content(header):
                                    continue
                            except OSError:
                                pass
                            violations.extend(scan_file(full_file_path))

    # Output Violations
    if violations:
        for v in violations:
            sys.stdout.write(f"{v.format()}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
