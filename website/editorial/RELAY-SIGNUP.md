# Relay signup for Agent Git Lab

The user requested the same email-capture pattern as the PocketShell website. This integration reuses Relay's public double opt-in flow. It does not reuse the PocketShell audience, place an API key in the static site, add visitor analytics, or start a daily email campaign.

## Browser contract

- List URL: `https://relay.datatalks.club/api/public/lists/agent-git-lab`.
- Request confirmation: JSON `POST /subscribe` with `{email}` after a valid email and explicit experiment-update consent.
- Confirm: JSON `POST /confirm` with `{token}` from the dedicated website confirmation route.
- Confirmation landing: `https://alexeygrigorev.com/cloudflare-agent-git/subscribe/`.
- Website origin: `https://alexeygrigorev.com`.
- Only `200` with `verification_requested`, `already_subscribed`, or the appropriate confirmation `subscribed` response is success. An unrelated `200` does not prove a signup.
- Pending requests disable the controls and prevent duplicate submits. A 15-second abort restores controls. Validation, rate limits, unavailable service, invalid/expired token, and network failures have explicit messages.
- The token is removed from the URL before the first await. The page uses `no-referrer`; neither submitted addresses nor tokens are stored in browser storage or logged by the website script.

The JSON file `website/signup.json` is public configuration, not credentials. Enable it only after the separate Relay list and exact website origin are verified on the live service. While disabled, no subscribe or confirm request is sent and the page offers RSS instead. Do not claim this disabled state collects emails.

## Relay ownership and durable configuration

Relay's owner must configure a distinct client and audience for `agent-git-lab`, a supported existing sender, and the signup-confirmation template. Keep PocketShell's entries intact. `RELAY_PUBLIC_LISTS` names the fixed organization, client, audience, category, template, and confirmation URL; the browser cannot select a sender or arbitrary template.

The existing PocketShell deploy script writes its public-list and origin settings on deployment. A one-off runtime addition can therefore disappear at the next deploy. The owner must make the multi-list addition durable in the supported deployment configuration as well as provision its database objects. The existing `provision_public_signup` command has a sender/template mapping; that mapping must support the new list. Do not deploy a stale local checkout or overwrite unrelated dirty Relay work.

Use genuine aplexer communication with the Relay owner. Preserve the current deployment and its rollback path. No Terraform purchase, new email service, DNS change, broad credential, or campaign is required by this website task.

## Validation and its limits

The private Node suite exercises the actual browser script with a mocked DOM and fetch implementation. It covers consent, input validity, strict response types, pending duplicate protection, timeouts, network/service/rate-limit errors, and confirmation-token removal. These controlled tests do not send email or prove live mail delivery.

Live readiness checks use `OPTIONS`, invalid email input, and invalid confirmation tokens only. Check the exact origin response header and configured list response; preserve addresses, real tokens, keys, and subscriber records privately. Do not subscribe someone else's address to obtain a green result. The Relay owner can verify the named objects and template without printing subscriber data.

Publish the enabled form only after live configuration is ready. Rebuild the static site, run internal-link and privacy checks, commit explicit owned paths under the experiment Git lock, and verify the existing GitHub Pages deployment and public routes.

## Future sending

The user has authorized capturing consented addresses. This task does not launch a marketing blast or automate daily email delivery. Any future update email must identify this experiment, honor its opt-in, and provide Relay's unsubscribe path. Daily reader reports currently publish to the website.

## Reviewed provider source

[Relay PR 40](https://github.com/DataTalksClub/relay/pull/40), merged as `7dbd9ad8bbf2bfbd7850be7e814c6a00e5f5ce2f`, adds the separate Agent Git Lab list, sender, template, durable settings, and provisioning invocation. Its sender is `Agent Git Lab <hello@datatalks.club>` under Relay’s existing DataTalks.Club identity. The browser still submits only an email or confirmation token. Source review and a passing workflow are separate from live endpoint and sender readiness.

The provider’s maintained template lives in Relay, not this static repository. `website/relay/confirm-signup.md` is the initial example supplied for the handoff, not proof of the deployed template. The reviewed Relay token code uses a 48-hour lifetime, matching its maintained confirmation copy. Actual operational readiness must be recorded after deployment.

## Production verification — 3 October 2026

The production deployment of [Relay revision 7dbd9ad](https://github.com/DataTalksClub/relay/commit/7dbd9ad8bbf2bfbd7850be7e814c6a00e5f5ce2f) completed in [workflow run 37096366069](https://github.com/DataTalksClub/relay/actions/runs/37096366069). The Relay owner confirmed separate organization, client, audience and confirmation template records, using the existing production `hello@datatalks.club` sender identity.

At 04:30 UTC, live checks returned preflight 204 with the exact website origin, invalid-address 400 and invalid-token 400. Both error responses included the expected CORS header. Existing PocketShell preflight and invalid-address checks also passed. These tests submitted no valid address or token and sent no email; actual inbox delivery was not exercised. The shared origin allowlist is a browser transport policy, not audience authorization.

The provider confirmation URL uses `/subscribe?token=…`; GitHub Pages may canonicalize this to `/subscribe/?token=…`. The client accepts both routes, removes the token before its request, and uses a no-referrer policy before loading any page asset. Signups require explicit consent and email confirmation. No newsletter campaign or automatic daily email schedule was created.
