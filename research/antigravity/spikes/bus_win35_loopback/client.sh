#!/usr/bin/env bash
# Win35 Outbound-only GitBash curl client for Agent Bus Loopback Adapter
# Directive C3087 / bus-win35-nonssh-loopback-spike-01
# Demonstrates full 5-stage lifecycle (register, send, inbox poll, read-ack, accept, complete, reply)
# using strictly outbound curl calls without local listening ports.

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8788}"
DEVICE_ID="${2:-win35-device-01}"
AGENT_NAME="${3:-worker-win35-executor}"
PROJECT_ID="${4:-agent-bus}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

CRED_FILE="$TMP_DIR/credentials.json"
umask 077

echo "[1/7] Enrolling device and agent: $AGENT_NAME ($DEVICE_ID)..."
REG_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/register" \
  -H "Content-Type: application/json" \
  -d "{\"agent_name\": \"$AGENT_NAME\", \"device_id\": \"$DEVICE_ID\", \"project_id\": \"$PROJECT_ID\"}")

echo "$REG_RESP" > "$CRED_FILE"
chmod 600 "$CRED_FILE"

IDENTITY_ID=$(python3 -c "import json; print(json.load(open('$CRED_FILE'))['identity']['id'])")
TOKEN=$(python3 -c "import json; print(json.load(open('$CRED_FILE'))['token'])")

echo "  Enrolled identity: $IDENTITY_ID"

echo "[2/7] Checking status endpoint..."
STATUS_RESP=$(curl -sS -f "$BASE_URL/v1/status")
echo "  Adapter Status: $STATUS_RESP"

echo "[3/7] Polling inbox (initial unread)..."
INBOX_RESP=$(curl -sS -f "$BASE_URL/v1/inbox?identity_id=$IDENTITY_ID&token=$TOKEN&unread_only=true")
COUNT=$(python3 -c "import json; print(json.loads('''$INBOX_RESP''')['count'])")
echo "  Inbox message count: $COUNT"

# Send self a message to test complete lifecycle
echo "[4/7] Sending test task message..."
SEND_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/send" \
  -H "Content-Type: application/json" \
  -d "{\"sender_id\": \"$IDENTITY_ID\", \"token\": \"$TOKEN\", \"recipient_id\": \"$IDENTITY_ID\", \"body\": \"Run win35 loopback verification task\", \"kind\": \"task\", \"idempotency_key\": \"win35-spike-key-$RANDOM\"}")

MSG_ID=$(python3 -c "import json; print(json.loads('''$SEND_RESP''')['message']['id'])")
echo "  Sent message ID: $MSG_ID"

echo "[5/7] Polling inbox for delivered task..."
DELIV_RESP=$(curl -sS -f "$BASE_URL/v1/inbox?identity_id=$IDENTITY_ID&token=$TOKEN&unread_only=true")
echo "  Retrieved delivered message."

echo "[6/7] Advancing transport states: ack -> accept -> complete..."
ACK_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/ack" \
  -H "Content-Type: application/json" \
  -d "{\"identity_id\": \"$IDENTITY_ID\", \"token\": \"$TOKEN\", \"message_id\": \"$MSG_ID\"}")

ACCEPT_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/accept" \
  -H "Content-Type: application/json" \
  -d "{\"identity_id\": \"$IDENTITY_ID\", \"token\": \"$TOKEN\", \"message_id\": \"$MSG_ID\"}")

# Fake artifact digest
DIGEST="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
COMPLETE_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/complete" \
  -H "Content-Type: application/json" \
  -d "{\"identity_id\": \"$IDENTITY_ID\", \"token\": \"$TOKEN\", \"message_id\": \"$MSG_ID\", \"status\": \"success\", \"digest\": \"$DIGEST\"}")

echo "[7/7] Sending reply..."
REPLY_RESP=$(curl -sS -f -X POST "$BASE_URL/v1/reply" \
  -H "Content-Type: application/json" \
  -d "{\"sender_id\": \"$IDENTITY_ID\", \"token\": \"$TOKEN\", \"message_id\": \"$MSG_ID\", \"body\": \"Win35 task completed with verified digest $DIGEST\"}")

REPLY_ID=$(python3 -c "import json; print(json.loads('''$REPLY_RESP''')['message']['id'])")
echo "  Reply message ID: $REPLY_ID"

echo "WIN35_CLIENT_EXECUTION_SUCCESS"
