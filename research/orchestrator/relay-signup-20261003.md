# Relay signup published — 3 October 2026

Human33 requested email capture using the PocketShell Relay pattern and delegated implementation. The website head coordinated a frontend executor, independent Relay reviewer and the existing Relay owner; principals remained monitors.

Live signup: https://alexeygrigorev.com/cloudflare-agent-git/subscribe/
Privacy: https://alexeygrigorev.com/cloudflare-agent-git/privacy/

The inline signup across 31 pages and dedicated signup page use the established editorial design, explicit consent and double opt-in. The separate `agent-git-lab` Relay audience does not reuse PocketShell subscribers. Public requests require no frontend credentials. Confirmation tokens are removed from the URL before requests; no-referrer precedes every subresource. An independent review found and corrected the original referrer ordering.

Website revision cfb7ca8fc8bbcd23cf47ce93f57b3f305b64b560 was deployed successfully in Pages run37096821539. Relay [PR40](https://github.com/DataTalksClub/relay/pull/40) was independently reviewed, passed CI and merged as7dbd9ad8bbf2bfbd7850be7e814c6a00e5f5ce2f. Production deployment37096366069 succeeded. Its genuine owner response confirmed the separate organization/client/audience, durable multi-list configuration, existing production verified sender and 48-hour confirmation expiry. Sender availability is owner-reported production evidence; actual inbox delivery was not tested.

Verification: 25 mocked JavaScript DOM/transport tests passed, including duplicate submits, consent, timeout and strict response handling. The website head checked all31 pages and live public routes. Live Relay OPTIONS and invalid-email/token requests passed, with exact website-origin CORS; PocketShell negative checks continued to pass. Root independently tested the published invalid-token page in the browser: invalid/expired status, restored controls, and URL cleaned to `/subscribe/`. No valid email or token was submitted; no test email was sent and no campaign was created. Mock tests do not prove inbox delivery.

The origin allowlist is shared across public lists: permitted origins may call either list. Separate audiences provide subscription separation; CORS is not list-specific authentication. Subscriber addresses, credentials and private request logs are excluded from the public repository.

Temporary private preview and coordination services are completed; private evidence is preserved. Email campaign scheduling is a separate future task. Daily reports continue to publish on the website.
