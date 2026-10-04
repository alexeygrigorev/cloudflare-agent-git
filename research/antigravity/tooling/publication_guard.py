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


KNOWN_REDACTION_MARKERS = {
    "[REDACTED]",
    "[REDACTED_TOKEN]",
    "[REDACTED_SECRET]",
    "[REDACTED_PASSWORD]",
    "[REDACTED_HASH]",
    "[REDACTED_EXPIRY]",
    "<token>",
    "<admin_token>",
    "<runner_token>",
    "<sidecar_token>",
    "<alpha_token>",
    "<beta_token>",
    "<encoded_token>",
    "<secret>",
    "***",
    "...",
}

EXACT_SAFE_LOCAL_SECRET_FIXTURES = {
    "token_12345",
    "secret_12345",
    "dummy_12345",
}

EXACT_SAFE_LOCAL_SECRET_REDACTIONS = {
    "[REDACTED]",
    "[REDACTED_SECRET]",
    "[REDACTED_TOKEN]",
    "<secret>",
    "<token>",
    "***",
    "...",
}

KNOWN_BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.svg',
    '.pdf', '.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz',
    '.bin', '.dat', '.exe', '.so', '.dylib', '.a', '.o',
    '.pyc', '.pyo', '.pyd', '.woff', '.woff2', '.ttf', '.eot',
    '.lock'
}


def is_safe_redacted_token(token: str) -> bool:
    """
    Check if token is an explicit known redaction placeholder or recognized variable expression.
    Per C1621 / C1622: Strict known marker allowlist ONLY.
    No generic bracket/angle acceptance.
    """
    t = token.strip().strip('"\'`')
    t_lower = t.lower()
    if t_lower in KNOWN_REDACTION_MARKERS or t in KNOWN_REDACTION_MARKERS:
        return True
    # Standard template / environment variable syntax allowed in code & docs
    if re.match(r'^\$\{[A-Za-z0-9_]+\}$', t) or re.match(r'^\$[A-Za-z0-9_]+$', t):
        return True
    # Recognized angle placeholder pattern: must be explicitly a token or secret placeholder
    if re.match(r'^<[a-z0-9_]*token[a-z0-9_]*>$', t_lower):
        return True
    # Recognized bracketed redactions: must start with [redacted
    if re.match(r'^\[redacted(_[a-z0-9_]+)?\]$', t_lower):
        return True
    # URL query parameter redaction composite format
    if t_lower in ('art_v1_[redacted]', 'art_v1_...'):
        return True
    if t_lower.startswith('art_v1_[redacted_hash]') and (
        t_lower.endswith('?expires=[redacted_expiry]') or t_lower.endswith('%3fexpires%3d[redacted_expiry]')
    ):
        return True
    return False


def is_safe_redacted_url_password(pw: str) -> bool:
    """
    Check if URL password component is safely redacted.
    Per C1621 / C1622: Strict known marker allowlist ONLY.
    Arbitrary bracketed strings like [raw_secret] or <raw_secret> without known marker are REJECTED.
    """
    p = pw.strip().strip('"\'`')
    p_lower = p.lower()
    if p_lower in KNOWN_REDACTION_MARKERS or p in KNOWN_REDACTION_MARKERS:
        return True
    if re.match(r'^<[a-z0-9_]*token[a-z0-9_]*>$', p_lower):
        return True
    if re.match(r'^\[redacted(_[a-z0-9_]+)?\]$', p_lower):
        return True
    # Allow composite URL query redactions:
    # e.g. art_v1_[REDACTED_HASH]%3Fexpires%3D[REDACTED_EXPIRY]
    if p_lower.startswith('art_v1_[redacted_hash]') and (
        p_lower.endswith('%3fexpires%3d[redacted_expiry]') or p_lower.endswith('?expires=[redacted_expiry]')
    ):
        return True
    if p_lower in ('art_v1_[redacted]', 'art_v1_...'):
        return True
    return False


def is_safe_tok(tok_val: str) -> bool:
    """
    Check if tok_ payload is strictly an allowed documented synthetic fixture or known marker.
    Per C1621 / C1622: Strict equality ONLY. No startswith or prefix matching.
    """
    t = tok_val.strip().strip('"\'`')
    if t == "alpha_12345":
        return True
    if t in KNOWN_REDACTION_MARKERS:
        return True
    return False


def is_safe_local_secret(suffix: str, filepath: str) -> bool:
    """
    Check if local secret suffix is safely redacted or standard documented fixture.
    Per C1621 / C1622: Strict equality ONLY. No startswith or prefix matching.
    """
    s = suffix.strip().strip('"\'`')
    if s in EXACT_SAFE_LOCAL_SECRET_REDACTIONS:
        return True
    if s in EXACT_SAFE_LOCAL_SECRET_FIXTURES:
        return True
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

        # Multi-line continuation: auth header on previous line, token on current line
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
                if user_part not in KNOWN_REDACTION_MARKERS:
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
    Per C1614 / C1621 / C1622: If explicit paths are provided with --staged, filters only to those targets.
    Every explicit target MUST match at least one staged file in the index; missing/unmatched fails closed (exit 2).
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
        normalized_targets = {}
        for p in explicit_paths:
            norm_p = os.path.normpath(p)
            normalized_targets[norm_p] = False
            try:
                rel = os.path.normpath(os.path.relpath(p, start=os.getcwd()))
                normalized_targets[rel] = False
            except ValueError:
                pass

        filtered = []
        for f in files:
            norm_f = os.path.normpath(f)
            matched = False
            for t in normalized_targets:
                if norm_f == t or norm_f.startswith(t + os.sep):
                    matched = True
                    normalized_targets[t] = True
            if matched:
                filtered.append(f)

        # Check if any explicit path was unmatched
        unmatched = [p for p in explicit_paths if not normalized_targets.get(os.path.normpath(p), False)]
        if unmatched:
            for up in unmatched:
                sys.stderr.write(
                    f"publication_guard: error: explicit target not staged in git index: {sanitize_path_for_display(up)}\n"
                )
            sys.exit(2)

        return filtered

    return files


def read_staged_content(filepath: str) -> str:
    """
    Read staged blob directly from git index as raw bytes.
    Per C1621 / C1622: Staged text deliverables containing NUL bytes fail closed with exit 2.
    Only recognized binary file extensions (.png, .jpg, .tar, .bin, etc.) can skip without error.
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
        ext = os.path.splitext(filepath)[1].lower()
        if ext in KNOWN_BINARY_EXTENSIONS:
            return ""
        # Staged text file containing NUL bytes -> fail closed!
        sys.stderr.write(
            f"publication_guard: error: binary content or NUL byte detected in staged text file: {sanitize_path_for_display(filepath)}\n"
        )
        sys.exit(2)

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
