# SDK invalid-input guarantee needs a negative test

Source checked 2026-10-05T12:10:45.445530+00:00: `/home/alexey/git/agent-branches`, clean HEAD `10d9d505e12b227582e8f2e56ad0cfcfe7d5ca7c`. This is independent source review, not an executed test result.

`agent_branches/client.py:395` describes upfront validation as guaranteeing zero partial coordinator mutation for invalid inputs. Its first loop validates event shape, head SHA and agent resolution. It does not normalize `files_changed`. The execution loop calls `push`, which converts a non-string `files_changed` with `list(files_changed)` before dispatch.

A concrete falsification case is a valid first event followed by a second event whose `files_changed` is the integer42, using explicit agent IDs. Source suggests the first event can dispatch before the second raises a local TypeError. That would refute the broad zero-mutation guarantee for all invalid inputs. The current stop-on-error/no automatic mutating retry policy can still be correct. The report should distinguish local normalization failure before dispatch from an ambiguous network failure after dispatch.

Offered canonical slice45 to the genuine launcher head in message C2521 for an independent tiny private negative test and evidence report. Head acceptance and actual executor output are pending. No production HTTP, new coordinator service, cloud spend, build, or peer source edits are needed. Do not call the hypothetical result reproduced until its actual test artifact arrives.
