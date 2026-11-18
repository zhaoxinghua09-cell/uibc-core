# Scale: what the verifier costs as the package grows

**2026-11-19.** Every number below was measured on this host, not estimated.
Data: `docs/SCALE.json`. Command: `tools/build_scale_svg.py`.

Most of this repository's evidence is about *what* a verifier refuses. This
page is about *what it costs* — because a verifier that is right but unusable at
size is a specification, not a product, and the first question a reviewer asks
about a five-thousand-event agent run is whether anyone can afford to check it.

## Method, stated so it can be argued with

Synthetic packages were built from `fixtures/clean.uibc`: N evidence files with
correct content hashes, an `evidence_root` re-derived over them, a matching
`evidence_count`, and `signatures/` removed. Unsigned, so the correct verdict is
INCONCLUSIVE — the measurement is of the verification path, not of a verdict.

## Python

| evidence files | wall clock | peak RSS |
|---|---|---|
| 100 | 0.007 s | 23.6 MiB |
| 1,000 | 0.055 s | 25.1 MiB |
| 5,000 | 0.282 s | 31.2 MiB |
| 20,000 | 1.104 s | 60.3 MiB |

**Linear.** Cost per evidence file is about 55 µs and about 1.9 KiB of resident
memory; 20,000 files verify in 1.1 s. Nothing quadratic hides in the root
computation, because the root is one SHA-256 over a canonical list of hashes
rather than a per-pair tree walk.

## JavaScript, the second implementation

| evidence files | wall clock | peak RSS |
|---|---|---|
| 1,000 | 0.204 s | 70.3 MiB |
| 5,000 | 0.303 s | 104.1 MiB |
| 20,000 | 0.829 s | 221.7 MiB |

The JavaScript figures include Node process start-up (about 0.15 s on this
host), which the Python figures do not. They are comparable as *the cost of a
command a person types*, not as kernel time. The growth is linear too, and
20,000 files land in under a second.

## Two findings the scale run produced

**1. S12 refused a package built with a timestamp in the future.** The first
synthetic build wrote `created_at` eight hours ahead of the host clock, and S12
reported it as `26306 s in the future` rather than accepting it. That was not
planned; it is recorded here because a check that fires on a mistake the author
actually made is worth more than one demonstrated on a prepared fixture.

**2. The two implementations disagreed on what "unsigned" means.** On the same
1,000-evidence package, Python returned INCONCLUSIVE and JavaScript returned
FAIL, with S6 saying *"package is unsigned; provenance is not attested"*. The
JavaScript line treated the absence of a signature as a conviction.

That is the exact distinction this project is built on: **three-valued
adjudication.** "No violation within the evidence boundary" is neither a pass
nor a finding; a package nobody signed has not been proven bad, it has not been
proven at all. The JavaScript verifier was wrong, and it was wrong in the one
place the 36/36 conformance agreement did not look, because every conformance
case carries some seal.

Fixed in `tools/verify-js/verify.mjs` (S6 now pushes INCONCLUSIVE on a missing
`signatures/`), with a regression test that pins both implementations to the
same answer on an unsigned package:
`test_an_unsigned_package_is_inconclusive_in_both_languages`.

## What this page does not claim

It does not compare against `agent-action-capsule` at the same sizes. Its
package format differs and a same-input comparison would compare two different
work; the honest statement is that we measured ourselves and have not measured
them at scale. `docs/COMPETITORS.md` records that as an outstanding item rather
than dressing up a number we did not take.

## Reproduce

```
$ python3 /tmp/mkscale.py 20000 /tmp/scale20000     # build the package
$ python3 /tmp/runscale.py /tmp/scale20000
{"n": 20000, "secs": 1.104, "rss_mib": 60.3, "result": "INCONCLUSIVE", ...}
```

Both scripts are two files of about forty lines each and are quoted in the
measurement log; they are not shipped because they exist only to make this
table, and a stranger can rebuild the same package from the description above.
