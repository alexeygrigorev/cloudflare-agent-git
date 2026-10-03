/**
 * PLAN-L1-REAL §5.1 — webhook authenticity for /events/*. An unauthenticated
 * event ingest forges arbitrary push state, so webhook auth is MANDATORY
 * whenever a webhook receiver is enabled; the §4 deferral is valid only while
 * no webhook route exists (there is no silent deferral).
 *
 * Wire: headers `x-webhook-timestamp` (unix seconds) and `x-webhook-signature`
 * = hex HMAC-SHA256(`${timestamp}.${rawBody}`, EVENTS_WEBHOOK_SECRET). The
 * timestamp bounds replay to ±WEBHOOK_REPLAY_WINDOW_SECONDS; the signature
 * covers the exact raw bytes so the body cannot be re-serialized past it.
 *
 * When EVENTS_WEBHOOK_SECRET is unset the routes fall back to bearer-only
 * auth (CONTRACT 0.1.1 shared-secret posture). Setting the secret is a
 * REQUIRED deploy-gate step (DEPLOY.md), not an optional extra.
 */

import { timingSafeEqual } from "./coordinator.js";

export const WEBHOOK_REPLAY_WINDOW_SECONDS = 300;

export const WEBHOOK_TIMESTAMP_HEADER = "x-webhook-timestamp";
export const WEBHOOK_SIGNATURE_HEADER = "x-webhook-signature";

async function hmacSha256Hex(secret: string, payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** The exact string a webhook sender must put in x-webhook-signature. */
export async function signWebhookPayload(secret: string, timestamp: string, rawBody: string): Promise<string> {
  return hmacSha256Hex(secret, `${timestamp}.${rawBody}`);
}

export interface WebhookVerification {
  rawBody: string;
  timestamp: string | null;
  signature: string | null;
  secret: string;
  /** Injectable for tests; defaults to Date.now(). */
  nowMs?: number;
}

/**
 * Constant-time digest compare + freshness window. Never throws on malformed
 * input — every failure mode is just `false` (the route answers 401 without
 * echoing any presented material).
 */
export async function verifyWebhookSignature(input: WebhookVerification): Promise<boolean> {
  if (!input.timestamp || !input.signature) {
    return false;
  }
  const ts = Number(input.timestamp);
  const nowSec = Math.floor((input.nowMs ?? Date.now()) / 1000);
  if (!Number.isFinite(ts) || Math.abs(nowSec - ts) > WEBHOOK_REPLAY_WINDOW_SECONDS) {
    return false;
  }
  const expected = await signWebhookPayload(input.secret, input.timestamp, input.rawBody);
  return timingSafeEqual(expected, input.signature.trim().toLowerCase());
}
