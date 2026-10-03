#!/usr/bin/env python3
"""Redact secrets from stdin before it touches RESULTS.md or any log.

Reads the account id and API token from the environment (never from argv),
plus any art_v1_* repo token anywhere in the stream. Never prints secrets.
"""
import os
import re
import sys

data = sys.stdin.buffer.read().decode("utf-8", "replace")

account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
token = os.environ.get("CLOUDFLARE_API_TOKEN", "")

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
