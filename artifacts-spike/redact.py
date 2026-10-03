#!/usr/bin/env python3
"""Redact secrets from stdin before it touches RESULTS.md or any log.

Reads the account id and API token from the environment (never from argv).
Repo tokens are matched by family, not by a single prefix: the docs' art_v1_<40 hex>
and the real service's art_v2_x_<40 hex> are both covered by the generic art_*_
pattern below (optionally followed by ?expires=<unix>). Never prints secrets.

Gate mode (--gate): for pipelines that persist evidence (RESULTS.md, logs,
appendices). Fails closed — exits non-zero when CLOUDFLARE_API_TOKEN is unset —
because the API-token substitution cannot be derived from a pattern; running the
gate without it would silently emit unredacted evidence.
"""
import os
import re
import sys


def main() -> int:
    gate = "--gate" in sys.argv[1:]

    data = sys.stdin.buffer.read().decode("utf-8", "replace")

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")

    if gate and not token:
        print(
            "redact.py: FAIL CLOSED - CLOUDFLARE_API_TOKEN is unset in --gate mode; "
            "refusing to emit possibly-unredacted evidence",
            file=sys.stderr,
        )
        return 2

    if account:
        data = data.replace(account, "<account_id>")
    if token:
        data = data.replace(token, "<redacted-api-token>")

    # Repo tokens: docs say art_v1_<40 hex>, the real service issues art_v2_x_<40 hex>;
    # match the whole family generically, optionally followed by ?expires=<unix>
    data = re.sub(r"art_[A-Za-z0-9_]*[0-9][A-Za-z0-9_]*_[0-9a-fA-F]{8,}(?:\?expires=\d+)?",
                  "<redacted-repo-token>", data)

    # Basic-auth URL form: https://x:<secret>@host — the password slot
    data = re.sub(r"(https://x:)[^@]+(@)", r"\1<redacted>\2", data)

    sys.stdout.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
