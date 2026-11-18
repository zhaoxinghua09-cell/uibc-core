# Three optimisations we tried on 20,000 files, and why we reverted all three

**2026-11-19.** `docs/SCALE.md` says a 20,000-entry package verifies in
1.104 s / 60 MiB. The obvious question is whether that is slow. Rather than
answer with adjectives, this page records the attempts, the measurements, and
what was done with them.

## Where the second actually goes

Timing hooks around the internal functions, one run, Python 3.12, warm page cache:

| stage | seconds of 1.158 | note |
|---|---|---|
| `_semantic_problems` (S12) | 0.354 | RFC 3339 match, calendar check, `datetime.fromisoformat`, future-skew test — per entry |
| `_strict_scan` (S11) | 0.278 | re-read bytes, depth scan (0.117 of it), `json.loads` with duplicate-key hook |
| `canonicalize` / `index_metadata_digest` (S7) | 0.154 | JCS re-serialisation of the index |
| `hash_file` (S4) | 0.152 | SHA-256 of every evidence file |

Measured separately, **hashing 20,003 files takes 0.170 s — 8.5 µs per file**.
So I/O is not the bottleneck and never was: two thirds of the time is JSON
semantics, one sixth is hashing.

That is 54 µs per entry for nineteen checks. As a reference point, starting this
Python interpreter takes about 150 ms — 2,800 entries worth of verification.

## Attempt 1: cache `realpath` per directory

`cProfile` put 0.449 s in `posixpath.realpath`, called once per evidence file for
the containment test. Resolving each *parent* once and reusing the answer
cannot change the result, so it looked free.

Measured: **1.093 s**, from 1.104 s. A 1% gain, because the OS already caches
those lookups; the profile was showing syscall-attributed time that the real
workload does not pay twice.

## Attempt 2: strip string literals before the depth scan

The nesting guard walks ten megabytes one Python character at a time, and
almost all of those characters are inside strings, where braces do not count.
A regex can remove string literals in C, and a second regex can drop everything
that is not a brace, leaving the same depth machine on roughly 1% of the input.
Semantically equivalent on valid JSON, with a fallback to the original loop when
a string is unterminated.

Measured: **1.146 s** — slower. The two `re.sub` passes over ten megabytes cost
more than the character loop they replaced, because the loop exits early on the
first limit breach and because `re` has to scan the whole text twice.

## Attempt 3: skip `fromisoformat` for timestamps that are clearly past

Rejected before it was written. It only helps when the evidence is old, and
a benchmark that is honest about its own timestamps is a benchmark with
timestamps near now — exactly the case where the shortcut cannot fire. An
optimisation that works only on inputs nobody submits is not an optimisation.

## What was done with all of this

`uibc_core/verify.py` is unchanged (`git checkout --`). Verifying a package is
the one place where the code must be obviously right; a 1% gain does not buy
the right to make the containment test two-step, and a 0% gain certainly
does not buy a regex that a future reader has to prove equivalent before
trusting it.

The measured floor stands: **54 µs per entry, nineteen checks, 60 MiB at
20,000 entries**, and the time is where the checks are, not where a profiler
suggests. Anyone who wants it faster has a specific place to aim —
`_semantic_problems` at 0.354 s is the largest single item, and it is dominated
by `datetime.fromisoformat` on values that are all distinct, which no cache
reaches.

## Reproduce

```
$ python3 /tmp/mkscale.py 20000 /tmp/s20
$ python3 /tmp/runscale.py /tmp/s20          # {"n": 20000, "secs": 1.1, "rss_mib": 60}
$ python3 -c "..."                            # timing hooks, see body of this page
```

Numbers move by about ±3% between runs on this machine; the 1.104 s in
`SCALE.json` and the 1.093–1.158 s here are the same measurement.
