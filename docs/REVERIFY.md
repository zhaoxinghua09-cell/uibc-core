---
facts: current
---

# Re-check everything in one command

Every number in this repository is supposed to be re-runnable. In practice
"re-runnable" meant eight commands in the right order, which nobody runs. One
command:

```powershell
pwsh tools/reverify.ps1              # offline, ~10 s
pwsh tools/reverify.ps1 -Network     # also take a fresh read-only reading of the platform
```

Expected output on a clean checkout:

| step | what it asserts |
|---|---|
| platform record is self-consistent | the recorded probes still support the sentences the page prints |
| one code, one agent | no duplicate `did` in the list, and one code resolved twice agrees with itself |
| real runs vs the pinned snapshot | every competitor run is at the commit the table pins |
| receipt vs this commit | the hashed file set equals this commit's file set |
| board vs the receipt | the page a reader sees was rendered from that receipt |
| evidence index | the index lists what is in the tree |
| doc numbers vs the records | no number in the docs disagrees with its record |

Any failure returns exit code 1. The failing step prints a `PROBLEM:` line naming
the observation that no longer holds — not "you are wrong", but "this sentence
is no longer supported".

## What this does not claim

It does not claim conformance to any standard, and it does not score anybody.
It re-checks our own records: that the observations were recorded, that the
records still agree with each other, and that the pages quote the records rather
than someone's memory. A green run means "the evidence chain is intact", not
"the platform is correct" and not "the competitors are worse".

## If you are on another machine

Clone `zhaoxinghua09-cell/uibc-core`, install the test extras, and run the same
command from the clone root. The only external dependency in the offline path is
Python; the `-Network` path also needs outbound HTTPS to `iaisp.teleinfo.cn`.
