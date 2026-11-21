# Admitting an artifact you did not build

Every competitor's product starts at "give us your package and we will tell you if it is
safe". That answer needs a threat model, a scanner, and a claim about behaviour. This
repo has never made that claim — its object is the **bytes and the seal around them**.
That left a gap a stranger falls into on their first minute: they have a wheel, we hand
them `verify`, and `verify` answers `INCONCLUSIVE` because a wheel is not a UIBC package.
Technically correct, practically useless.

`tools/admit_package.py` closes that gap with the only claim this repo can defend:

> **the bytes you hold are the bytes that were sealed.**

One command, no account, no network:

```
python tools/admit_package.py \
    --artifact dist/uibc_core-0.4.1-py3-none-any.whl \
    --out /tmp/admitted/uibc-core-0.4.1 \
    --agent-id uibc-core-0.4.1 --owner zhaoxinghua09-cell \
    --key owner.ed25519 --pinned owner.ed25519.pub
```

It hashes the artifact, enumerates its members (path, size, sha256 each), builds a UIBC
package around that, seals it with **your** key, and verifies it twice — open, and pinned
to your published key. Exit codes: `0` admitted and PASS, `1` verdict not PASS,
`2` usage or artifact error.

## Measured example (this repository's own wheel, 2026-11-20)

```
| artifact | uibc_core-0.4.1-py3-none-any.whl (zip/wheel, 128763 bytes) |
| artifact sha256 | d9becab959e8b0937022620ba309281307a5fe9f3091814b84a4c2b24ff58cf4 |
| members | 33 |
| verdict (open)   | PASS |
| verdict (pinned) | PASS |
| Non-PASS checks  | none |
```

`pip wheel . --no-deps` produced the artifact; it was admitted in 33-member form. Nothing
about that run is special except that it is real — the same command works on a wheel you
download, a zip someone emails you, a tar, a single file, or a directory of up to 50 files.

## Why the disclosure row says `n/a`

The seven-field row this project audits other people with has a numerator and a
denominator. One artifact has **no rate**: there is no "false-accept rate" over a single
admission, and the rule we apply to everyone else — *n < 30 must not be reported as a
percentage* — applies to us first. So the row prints:

| convention | numerator | denominator | truth | corpus | na_policy | coverage |
|---|---|---|---|---|---|---|
| pinned (owner public key) | n/a | 1 artifact | bytes sealed by the admitting key at admission time | single artifact, 33 members (zip/wheel) | INCONCLUSIVE kept as INCONCLUSIVE; no rate computed for n<30 | artifact sha256 + full member inventory; no content analysis |

A row that fills that cell with `100%` would be the exact failure this whole document set
exists to prevent.

## What a PASS from this tool does and does not mean

**Does mean**

- the artifact's sha256 and every member's sha256 were recorded at admission time and are
  reproducible from the package;
- any later change to the sealed bytes is detected (S4) — verified by the negative control
  in `tests/test_admit_package.py`, which flips one byte and expects FAIL;
- the seal names the key that made it, and pinning that key catches key substitution (S6).

**Does not mean**

- the artifact is safe. There is no malware scan, no heuristic, no code review here;
- anything about behaviour after install — no execution, no sandbox;
- anything about dependencies or the transitive graph;
- that a third party admitted it. The key is whoever ran the command.

## The decision, not just the verdict

`verify` answers "do these bytes match the seal". The **gate** answers "may this be
installed", folding revocation and dispute overlays into one decision:

```
| admission decision | ALLOW — verify PASS, no revocation, no dispute |
```

Both are printed, because they fail differently: `verify` can be PASS while the gate is
DENY (a revoked key, a disputed package), and a caller who reads only the verify field
would miss exactly the case the overlays exist for. Exit code follows the **decision**
(`ALLOW` → 0, `DENY` → 1). `--no-gate` still exists for debugging the package itself, and
says so in the record — the weaker answer is labelled weaker.

Negative control: `test_a_tampered_package_is_denied_not_only_failed` flips a byte, then
asserts `gate.decision == DENY` **and** `verify_result == FAIL`. Two assertions because the
interesting case is when they disagree.

### Two machines, same decision (measured, 2026-11-20)

Same commit `1ca32c6`, a clean clone on each side, `pip install .` in a fresh venv, then
`tools/admit_package.py` on the wheel that machine had just built:

| machine | wheel | decision | exit | negative control (one byte flipped) |
|---|---|---|---|---|
| Windows 11 / Python 3.13.15 | 128763 B | `ALLOW` — verify PASS, no revocation, no dispute | 0 | — |
| Linux 6.6.95 / Python 3.12.11 | 129205 B, sha256 `8bf7a93ecfd4…` | `ALLOW` — same reason string | 0 | `DENY` — `verifier FAIL: S4; S8`, gate exit 2 |

The wheels differ in size again, which is the earlier section's point holding under the
new code path: the decision is a statement about the bytes that were sealed, not about
the source they came from.

One asymmetry worth naming rather than smoothing over: `uibc gate` itself exits **2** on
DENY, while `admit_package.py` collapses any non-ALLOW decision to **1**. Both are
non-zero, so a shell `if` behaves the same; a caller that branches on the *specific*
code gets a different number from the two tools. If you need the gate's own code, call
`uibc gate` directly — the wrapper documents its own coarseness instead of hiding it.

And the standing caveat: both rows were produced by the same person, on two machines he
controls. That is a reproduction, not an independent verification; evidence level does
not move.

## The same source produced two different wheels (measured)

Building this repository's wheel on two machines, from the same commit `e83d93f`, gave:

| machine | bytes | sha256 |
|---|---|---|
| Windows 11 / Python 3.13.15 | 128763 | `d9becab959e8b093…` |
| Linux 6.6.95 / Python 3.12.11 | 128999 | `14edf0f4300bc33f…` |

Both admitted PASS with 33 members. **The artifact is not byte-reproducible**, and that is
the reason this tool seals the artifact rather than its source: any claim of the shape
"from this source anyone can rebuild the identical package" is false for a wheel by
default (timestamps, zip metadata, compression). A signature over source would tell you
nothing about the bytes you are about to install; a hash over those bytes tells you
exactly which ones were admitted.

Anyone publishing reproducible-build claims should be asked for the machine, the
toolchain and the build flags — the two rows above are what "same input" produces without
them.

## Directory artifacts, stated precisely

A directory has no single byte sequence, so rather than invent an archive format and then
call its bytes "yours", this tool seals **each member individually** (up to 50 files) and
binds the set with an inventory. Above that bound it refuses and tells you to package the
artifact first. A tool that silently repacks a tree and claims a hash is lying about which
bytes were judged.

## Boundaries on the tool's own honesty

- **One operator.** The pinned key is published by whoever ran the admission; that is a
  self-assertion of provenance, not a third-party statement.
- **No rate.** See above.
- **No coverage claim.** The inventory says what was hashed, never that hashing is
  sufficient for any particular threat model. The record ships a `not_covered` list in the
  machine-readable output so a downstream report cannot quietly drop it.

## 中文摘要

这道工具补的是"陌生人第一分钟"的空档：他们手里是一个 wheel，我们给的是 `verify`，
而 `verify` 判不了 wheel（只想说 INCONCLUSIVE）。工具只主张一件能守住的事——**你手里的字节，
就是被封印的字节**：一条命令完成 哈希→成员清单→建包→用你自己的钥匙封→两次验证（open 与钉扎）。

- 单件没有"率"：分子写 `n/a`，因为 n<30 不得报百分比——我们量别人的规矩，先量自己。
- 反向对照：改一个字节即 FAIL（S4），不是"看过了"而是"抓得住"。
- 目录不臆造压缩格式：逐成员封印（上限 50 个文件），超限就拒绝并让你先打包。
- 不覆盖：无恶意扫描、无沙箱执行、不判依赖图、不代第三方背书。
