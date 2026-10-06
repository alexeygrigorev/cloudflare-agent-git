# Appendix — full sanitized op transcript (artifacts-spike, 2026-10-03)

> **Provenance — this file is a hand-assembled reconstruction, not a raw capture.** It was assembled by
> the executor from per-op log lines after the session. Corrections applied during the 2026-10-03
> independent review, none of which change payload values, hashes, ids or ms timings:
> `O111`/`O112` label-concatenation artifacts renamed to `O11`/`O12` (the O12 payload is demo-agent-2
> and its label now says `get-fork2`), physical lines that had joined the O4/O5, O5/O6, O9/O10 and
> O10/O11 entries were split, and the personal git author email in O16 was redacted post-hoc. The
> trailing token-shape attestation line was added post-review (structural only, hex elided).
> **O29 has no capture here** — see the RESULTS.md ledger row and PLAN-L1-REAL.md §5.9. A reviewer
> cannot distinguish transcription slips from misreads in a reconstruction; future spikes should land
> the raw per-op capture alongside the assembled appendix.

```
[O1 ns-get ms=1178] {"result":null,"success":false,"errors":[{"code":10200,"message":"Namespace not found","documentation_url":"https://developers.cloudflare.com/artifacts/api/errors#10200"}],"messages":[]}
[O1 ns-get ms=1178] HTTP=404 TIME=1.161152
[O2 ns-create ms=1116] {"result":{"namespace":"agent-branches-dev","jurisdiction":"unrestricted","repo_count":0,"created_at":"2026-10-03T16:57:42.016Z","updated_at":"2026-10-03T16:57:42.249Z"},"success":true,"errors":[],"messages":[]}
[O2 ns-create ms=1116] HTTP=201 TIME=1.086719
[O3 ns-get ms=181] {"result":{"namespace":"agent-branches-dev","jurisdiction":"unrestricted","repo_count":0,"created_at":"2026-10-03T16:57:42.016Z","updated_at":"2026-10-03T16:57:42.249Z"},"success":true,"errors":[],"messages":[]}
[O3 ns-get ms=181] HTTP=200 TIME=0.161299
[O4 repo-create ms=3046]
[O4] {"result":{"id":"u7usp14xkllei2on","name":"demo-canonical","description":"agent-branches demo canonical base (spike)","default_branch":"main","remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-canonical.git","token":"<redacted-repo-token>"},"success":true,"errors":[],"messages":[]}
[O5 token-mint ms=179]
[O5] {"result":{"id":"e78473xkdxtgr1n9","plaintext":"<redacted-repo-token>","scope":"write","expires_at":"2026-10-03T17:58:29.832Z"},"success":true,"errors":[],"messages":[]}
[O6 ls-remote-empty ms=4] fatal: bad config line 1 in file /home/alexey/.config/cloudflare/.artifacts-git-header|EXIT=128|
[O6 ls-remote-empty ms=970] EXIT=0|
BASE_SHA=b4346112b18a208d5f480e986b22c59d8339abb4
[O7 push-base ms=416] To https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-canonical.git| * [new branch]      main -> main|EXIT=0|
[O8 ls-remote-verify ms=269] b4346112b18a208d5f480e986b22c59d8339abb4	HEAD
b4346112b18a208d5f480e986b22c59d8339abb4	refs/heads/main
EXIT=0
[O9-fork1 ms=4486]
[O9-fork1] {"result":{"id":"z23vslwndyq9lz2b","name":"demo-agent-1","description":"agent fork (spike)","default_branch":"main","remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-1.git","token":"<redacted-repo-token>","objects":15},"success":true,"errors":[],"messages":[]}
[O10-fork2 ms=3396]
[O10-fork2] {"result":{"id":"nzhkzbxleu7eyjds","name":"demo-agent-2","description":"agent fork (spike)","default_branch":"main","remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-2.git","token":"<redacted-repo-token>","objects":15},"success":true,"errors":[],"messages":[]}
[O11 get-fork1 try1 ms=134] {"result":{"id":"z23vslwndyq9lz2b","name":"demo-agent-1","description":"agent fork (spike)","default_branch":"main","created_at":"2026-10-03T17:00:31.496Z","updated_at":"2026-10-03T17:00:33.963Z","last_push_at":null,"source":"artifacts:agent-branches-dev/demo-canonical","read_only":false,"remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-1.git"},"success":true,"errors":[],"messages":[]}
[O11 get-fork1 try1 ms=134] HTTP=200
[O12 get-fork2 try1 ms=118] {"result":{"id":"nzhkzbxleu7eyjds","name":"demo-agent-2","description":"agent fork (spike)","default_branch":"main","created_at":"2026-10-03T17:00:35.968Z","updated_at":"2026-10-03T17:00:37.971Z","last_push_at":null,"source":"artifacts:agent-branches-dev/demo-canonical","read_only":false,"remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-2.git"},"success":true,"errors":[],"messages":[]}
[O12 get-fork2 try1 ms=118] HTTP=200
[O13 fork1-log ms=172] {"result":[{"hash":"b4346112b18a208d5f480e986b22c59d8339abb4","treeHash":"6adc109f3a08e4d1c4581259e70866603b2ea87e","message":"demo-target base state: shortlinks service (cloudflare-agent-git ff4decd, no .harness)","author":{"name":"zc-artifacts-1","email":"zc-artifacts-1@aplexer.local"},"committer":{"name":"zc-artifacts-1","email":"zc-artifacts-1@aplexer.local"},"parents":[],"authoredAt":1791046799,"committedAt":1791046799}],"success":true,"errors":[],"messages":[]}
[O13 fork1-log ms=172] HTTP=200 TIME=0.153248
[O14 clone-fork1 ms=500] EXIT=0| HEAD=b4346112b18a208d5f480e986b22c59d8339abb4
[O15 push-fork1 ms=346] To https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-1.git|   b434611..c809475  main -> main|EXIT=0|
[O16 fork1-log-readback ms=130] {"result":[{"hash":"c8094754895554f89cf816d55eee8207d14c9692","treeHash":"ba1ea03d9d1d9f9b1858292459ba1e42d59365c8","message":"spike: 1-line README change from demo-agent-1","author":{"name":"Alexey Grigorev","email":"<redacted-email>"},"committer":{"name":"Alexey Grigorev","email":"<redacted-email>"},"parents":["b4346112b18a208d5f480e986b22c59d8339abb4"],"authoredAt":1791046878,"committedAt":1791046878}],"success":true,"errors":[],"messages":[]}
[O16 fork1-log-readback ms=130] HTTP=200 TIME=0.114298
MATCH local=c8094754895554f89cf816d55eee8207d14c9692 remote=c8094754895554f89cf816d55eee8207d14c9692 -> YES
[O17 repos-list ms=450] {"result":[{"id":"z23vslwndyq9lz2b","name":"demo-agent-1","description":"agent fork (spike)","default_branch":"main","created_at":"2026-10-03T17:00:31.496Z","updated_at":"2026-10-03T17:00:33.963Z","last_push_at":null,"source":"artifacts:agent-branches-dev/demo-canonical","read_only":false,"remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-1.git","status":"ready"},{"id":"nzhkzbxleu7eyjds","name":"demo-agent-2","description":"agent fork (spike)","default_branch":"main","created_at":"2026-10-03T17:00:35.968Z","updated_at":"2026-10-03T17:00:37.971Z","last_push_at":null,"source":"artifacts:agent-branches-dev/demo-canonical","read_only":false,"remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-2.git","status":"ready"},{"id":"u7usp14xkllei2on","name":"demo-canonical","description":"agent-branches demo canonical base (spike)","default_branch":"main","created_at":"2026-10-03T16:58:27.113Z","updated_at":"2026-10-03T16:58:28.193Z","last_push_at":null,"source":null,"read_only":false,"remote":"https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-canonical.git","status":"ready"}],"success":true,"errors":[],"messages":[],"result_info":{"page":1,"per_page":50,"total_pages":1,"count":3,"total_count":3}}
[O17 repos-list ms=450] HTTP=200 TIME=0.433991
[O18 ls-remote-fork1 ms=218] c8094754895554f89cf816d55eee8207d14c9692	HEAD|c8094754895554f89cf816d55eee8207d14c9692	refs/heads/main|EXIT=0|
[O19 ls-remote-canonical ms=348] b4346112b18a208d5f480e986b22c59d8339abb4	HEAD|b4346112b18a208d5f480e986b22c59d8339abb4	refs/heads/main|EXIT=0|
[O20 wrangler-ns-list ms=1092] [
    {
        "namespace": "agent-branches-dev",
        "jurisdiction": "unrestricted",
        "repo_count": 3,
        "created_at": "2026-10-03T16:57:42.016Z",
        "updated_at": "2026-10-03T17:00:40.997Z"
    }
]
EXIT=0
[O21 wrangler-repos-list ms=1082] [
    {
        "id": "nzhkzbxleu7eyjds",
        "name": "demo-agent-2",
        "description": "agent fork (spike)",
        "default_branch": "main",
        "created_at": "2026-10-03T17:00:35.968Z",
        "updated_at": "2026-10-03T17:00:37.971Z",
        "last_push_at": null,
        "source": "artifacts:agent-branches-dev/demo-canonical",
        "read_only": false,
        "remote": "https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-2.git",
        "status": "ready"
    },
    {
        "id": "z23vslwndyq9lz2b",
        "name": "demo-agent-1",
        "description": "agent fork (spike)",
        "default_branch": "main",
        "created_at": "2026-10-03T17:00:31.496Z",
        "updated_at": "2026-10-03T17:00:33.963Z",
        "last_push_at": null,
        "source": "artifacts:agent-branches-dev/demo-canonical",
        "read_only": false,
        "remote": "https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-agent-1.git",
        "status": "ready"
    },
    {
        "id": "u7usp14xkllei2on",
        "name": "demo-canonical",
        "description": "agent-branches demo canonical base (spike)",
        "default_branch": "main",
        "created_at": "2026-10-03T16:58:27.113Z",
        "updated_at": "2026-10-03T16:58:28.193Z",
        "last_push_at": null,
        "source": null,
        "read_only": false,
        "remote": "https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-canonical.git",
        "status": "ready"
    }
]
EXIT=0
[O22 tokens-list ms=207] {"result":[{"id":"e78473xkdxtgr1n9","scope":"write","state":"active","created_at":"2026-10-03T16:58:29.832Z","expires_at":"2026-10-03T17:58:29.832Z"},{"id":"mrmg43tumvev6bhr","scope":"write","state":"active","created_at":"2026-10-03T16:58:28.137Z","expires_at":"2026-10-04T16:58:28.137Z"}],"success":true,"errors":[],"messages":[],"result_info":{"page":1,"per_page":30,"total_pages":1,"count":2,"total_count":2}}
[O22 tokens-list ms=207] HTTP=200
initial-create-token-id=mrmg43tumvev6bhr (minted=e78473xkdxtgr1n9)
[O23 token-revoke-canonical-initial ms=267] {"result":{"id":"mrmg43tumvev6bhr"},"success":true,"errors":[],"messages":[]}
[O23 token-revoke-canonical-initial ms=267] HTTP=200
[O24 tokens-list-f2 ms=238] {"result":[{"id":"46d0o63cx0a301a7","scope":"write","state":"active","created_at":"2026-10-03T17:00:37.916Z","expires_at":"2026-10-04T17:00:37.916Z"}],"success":true,"errors":[],"messages":[],"result_info":{"page":1,"per_page":30,"total_pages":1,"count":1,"total_count":1}}
[O24 tokens-list-f2 ms=238] HTTP=200
[O25 token-revoke-f2 ms=217] {"result":{"id":"46d0o63cx0a301a7"},"success":true,"errors":[],"messages":[]}
[O25 token-revoke-f2 ms=217] HTTP=200
[O26 mint-read-token ms=197] id=jni5lv543os37xnm
[O27 push-with-read-token ms=52] fatal: unable to access 'https://<account_id>.artifacts.cloudflare.net/git/agent-branches-dev/demo-canonical.git/': The requested URL returned error: 400|EXIT=128|
[O28 token-revoke-read ms=218] {"result":{"id":"jni5lv543os37xnm"},"success":true,"errors":[],"messages":[]}
[O28 token-revoke-read ms=218] HTTP=200

[token-shape structural attestation — added 2026-10-03 post-review; NOT a captured call]
Shape observed on every real token issued during this spike:
  art_v2_x_<40 hex, elided>?expires=<epoch seconds>
The docs' documented shape is art_v1_<40 hex>. Whole tokens were redacted at capture time, so the
prefix is attested from the executor's redaction pass (RESULTS.md finding 1), not recoverable from the
lines above; ?expires= semantics are corroborated by O5/O22/O24 expires_at deltas.
```
