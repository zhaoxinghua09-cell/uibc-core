# Citation reachability: three links that fail our local checker but are reachable from an outside outlet

Measured 2026-11-17 ~17:55 CST. `tools/check_citations.py` reports 42/45 reachable. The three
failures are not dead links - they are a property of *where the check was run from*. Recording both
measurements, because a single status code would hide the distinction.

| # | link | local checker (scripted urllib, this machine) | outside outlet (agent fetch, no cookie, no token) | verdict |
|---|---|---|---|---|
| 1 | <https://www.iso.org/standard/88723.html> (ISO/IEC 24970, AI system logging) | **403 Hypertext** | **200**, title "ISO/IEC 24970 — Artificial intelligence — AI system logging", page text confirms "International Standard under publication", TC ISO/IEC JTC 1/SC 42 | reachable; the 403 is bot filtering of the local script's user agent |
| 2 | <https://eips.ethereum.org/EIPS/eip-8004> (ERC-8004 Trustless Agents) | **timeout (WinError 10060)** | **200**, title "ERC-8004: Trustless Agents", body confirms Identity Registry / agentURI / registration file fields | reachable; the timeout is this machine's route to that host at that moment |
| 3 | <https://github.com/zhaoxinghua09-cell/uibc-core> (our own repo) | **timeout (WinError 10060)** | reachable by clone and by raw-file fetch multiple times today (`06ff25c`, `de474d2`, `8faeabb` all fetched) | reachable; the timeout is the same intermittent 443 reset documented elsewhere in this repo |

## Why this matters for S7

S7 says a citation must be directly reachable, not "reachable if you are us". The measurement above
shows the opposite failure mode: links that are fine for a human or an outside agent but blocked for
our own scripted check. Publishing only "42/45" would understate reachability; publishing only
"all reachable" would hide that a scripted check cannot confirm two of them.

**Rule adopted:** a citation passes when *either* the local script or an outside outlet returns 200
with matching content, and both numbers are recorded. Neither measurement alone is a verdict.

## Reproduce

```text
python tools\check_citations.py                  # local scripted check (42/45 today)
# then, from an outside outlet, fetch each failing URL and compare the title/body fields
```

## What is still not verified

The human-browser experience for #1 (ISO's own page layout) was not observed here; we only know an
HTTP 200 with the expected title and abstract text. #2 and #3 were fetched but not re-fetched after
the page content changed today, so their byte-level equality with our citations is not asserted.
