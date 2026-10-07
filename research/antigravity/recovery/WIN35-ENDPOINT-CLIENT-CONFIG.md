# Win35 Endpoint Client Configuration & Public Trust Bundle (C3123)

## 1. Endpoint Connectivity Specification
- **Protocol**: HTTPS over Mutual TLS (`ssl.CERT_REQUIRED`, TLSv1.3)
- **Primary Public Endpoint (Hetzner)**: `https://135.181.114.209:8788/v1`
  - Bound to `0.0.0.0:8788` on host interface `enp35s0`.
  - Server certificate SAN verified: `DNS:localhost, IP:127.0.0.1, IP:135.181.114.209`.
- **Secondary / Loopback Endpoint**: `https://127.0.0.1:8788/v1`
- **Service Unit**: `agent-bus-win35-adapter.service` (running unprivileged under systemd user manager, `MemoryMax=300M`, `TasksMax=50`)
- **Server State**: Active (listening on `0.0.0.0:8788`, verified live with mTLS E2E tests)
- **Underlying Bus Store**: `/home/alexey/.local/share/agent-bus-win35/store` (isolated probe/candidate store, preserving canonical Bus source and leases)

## 2. Public CA Certificate Trust Bundle
Save the following certificate on the Windows client machine as `ca.crt`:

```text
-----BEGIN CERTIFICATE-----
MIIDITCCAgmgAwIBAgIUDXWdW/tDT7FbZ+QbxlkxBTBeC+YwDQYJKoZIhvcNAQEL
BQAwIDEeMBwGA1UEAwwVQWdlbnRCdXMtV2luMzUtUm9vdENBMB4XDTI2MTAwNzA2
NTE0OFoXDTI3MTAwNzA2NTE0OFowIDEeMBwGA1UEAwwVQWdlbnRCdXMtV2luMzUt
Um9vdENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtAlP/R8Djblq
qp4gU58kihSLXUNdgGgayMLJyQ3cB02ZKoO/jlWXxt2mPUM2FIQLQJbaTNHR0KgY
vYq3m1HDGevzD7+NJich4o+rL6RqztutUUbf2aCakKJEdwAl0AK/dEJNueUmXy1u
7d38/hnfCJ7NXiUrRkgTWX6KNFXiYXHFtvBB19UFOwgtat8WTb6/oQQemohlnIB4
96QcVe3glb1YPWxZtGFUxg+i21qytQ5aL3TvY9qwf4AbtedzZY6V7NS3VHOATB7s
563I8C1azxvacMoooTSCxIjpKHul8LCTwaazhphEGUtZyuk5FBpejcr3xvNt3G0W
nx1hs7P7fwIDAQABo1MwUTAdBgNVHQ4EFgQUhxKHVNOSe3Uq5pMrgj2FuN5KXoUw
HwYDVR0jBBgwFoAUhxKHVNOSe3Uq5pMrgj2FuN5KXoUwDwYDVR0TAQH/BAUwAwEB
/zANBgkqhkiG9w0BAQsFAAOCAQEAUkzYuyMObaj/NFTBlZGhbnZdJQhYjszdrXQs
58nwAI9/J49Ep3/HSV8MjKqXHRvfzKn5aD2lst9cFWFJxD/gbjJ0HR97FEv3o6BL
449CCTvy2vA9k8UHQQBlCxR/8iy4NPS+rvCsQWI8Ke6JHJTS03IkUGmiCE4cH/99
8j7/GSP01fPcE2xmMAYD6mV+rw5jafjFYWrih7R+YTYSJjTXyVldVA8ULaRGMfDn
3TH0L7NNgMmyEZjLG3NwzEAxeXSU7+sgw2SCcPIK0EqR/4JUtzHScdyG4YSUYNU3
WreUMNE0qfZhA4xHHBzz12NyEF8TgBw/nzLWbpS6CpwrtD0Yvw==
-----END CERTIFICATE-----
```

## 3. Enrolled Device Scopes & Allowlist
- **Enrolled Device ID**: `win35-device-01`
- **Enrolled Project ID**: `agent-bus-project`
- **Authorized Client Cert Fingerprint (SHA-256 DER)**:
  `c02c2376cbe9a529549f971dcdab5e35c3beb91d2be87d48b603091fca4eb940`
- **Allowlist Location**: `/home/alexey/.local/share/agent-bus-win35/secrets/allowlist.json` (mode 0600)

> [!NOTE]
> **Synthetic Test Fixtures vs Physical Device Enrollment**:
> The `client.crt` and `client.key` generated on the Hetzner host are synthetic local test fixtures used to verify mTLS and allowlist enforcement.
> For actual physical Win35 deployment:
> 1. The Windows client must generate its own RSA private key and certificate signing request (CSR) locally on device (never transmitting its private key).
> 2. The Root bootstrap process signs the CSR with `ca.crt` / `ca.key` or enrolls the client certificate's SHA-256 DER fingerprint into `/home/alexey/.local/share/agent-bus-win35/secrets/allowlist.json`.
> 3. Only enrolled fingerprints with valid device/project scopes are admitted.

## 4. Client Invocation Template (Windows PowerShell / CMD)
To connect the Windows client securely to the Hetzner public endpoint:
```powershell
python receiver.py `
    --adapter-url "https://135.181.114.209:8788/v1" `
    --agent-name "win35-agent" `
    --device-id "win35-device-01" `
    --project-id "agent-bus-project" `
    --ca-cert "ca.crt" `
    --client-cert "client.crt" `
    --client-key "client.key"
```
*(Where `client.crt` contains the enrolled client certificate signed by `AgentBus-Win35-RootCA` and `client.key` is its matching private key generated on device).*

