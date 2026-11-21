# The overlay, shown doing its job: same bytes, clean verify, still denied

**One-line claim** — `tools/demo_revocation.py` builds two packages (one HMAC-sealed, one
Ed25519-sealed) and runs the gate eight times, and every run behaves as the decision rules
say. On the HMAC-sealed package:

| run | decision | exit | reason |
|---|---|---|---|
| no overlay | `ALLOW` | 0 | `verify PASS, no revocation, no dispute` |
| valid owner revocation | `DENY` | 2 | `package is revoked by valid owner revocation` |
| same revocation, no key | `HOLD` | 3 | `revocation UNVERIFIABLE: … no --key provided` |
| revocation signed by another key | `HOLD` | 3 | `revocation UNVERIFIABLE: signature invalid for supplied key` |

The package's tree hash is printed before and after and is identical —
`321decd4eef3…` on the measured run. **The denial came from the overlay, not from the bytes
changing**, which is the only version of this demo worth running.

## Why the two HOLD rows matter more than the DENY row

The shortcut every hurried implementation takes is: a revocation I cannot verify is a
revocation I can ignore, therefore `ALLOW`. Both rows exist to make that impossible to
claim later: no key at all, and a signature that does not verify, are two different causes
with two different reasons, and both end at `HOLD` with a non-zero exit.

The failure is asymmetric on purpose:

- an unverifiable **revocation** blocks the automatic answer (`HOLD`),
- a garbage **dispute** does not block (`HOLD` only when it is malformed; a well-formed
  dispute on a passing package gives `ALLOW_DISPUTED`, flagged).

Revocation = owner says *this is void*. Dispute = a third party says *I object*. Different
powers, so different defaults.

## A limitation this demo exposed, and then closed

The first version of this demo found that revocation signatures were **HMAC-only**
(`gate.py::_verify_body`). Our product path seals with Ed25519, and there was no way for the
gate to check an HMAC signature against an Ed25519 public key — so an Ed25519 package with a
revocation attached landed on `HOLD (UNVERIFIABLE)`, and "revocation blocks" was true only
for v0.2-era packages.

That is now closed, asymmetrically:

- `uibc revoke --key owner.key --out revocation.json` signs the revocation body with the
  owner's Ed25519 seed and records `algorithm: "Ed25519"` plus `key_id` = sha256(public key);
- the gate verifies it against `--pubkey`, so **any third party holding the public key can
  check that the owner really voided the package** — without ever holding the owner's secret.

The demo gained four more rows on a second, Ed25519-sealed package:

| run | decision | exit | reason |
|---|---|---|---|
| `ed25519 package, no overlay` | `ALLOW` | 0 | verify PASS |
| `ed25519 revocation, pinned pubkey` | `DENY` | 2 | `package is revoked by valid owner revocation` |
| `ed25519 revocation signed by another key` | `HOLD` | 3 | `revocation key_id does not match the pinned public key` |
| `ed25519 revocation, no pubkey` | `HOLD` | 3 | `… no --pubkey provided: cannot verify` |

And the bytes still do not move: the Ed25519 package's tree hash is identical before and
after all four runs (`test_the_bytes_never_move` asserts both packages).

### The bug this round produced, kept because it is instructive

The first `revoke` implementation signed the four base fields and then added `algorithm` and
`key_id` to the file. The gate strips only `signature` before canonicalizing, so it
reconstructed six fields and every valid signature failed (`HOLD`, "signature invalid").
**Signer and verifier must canonicalize the same set of fields** — the fix was to sign the
finished body. A cross-machine run would not have caught this; a first-run test did.

### What is still not true

`key_id` mismatch currently reports `UNVERIFIABLE` rather than `MISMATCH`: a foreign-key
revocation is refused, but the gate does not distinguish "someone else revoked" from
"signature bytes are broken". Both HOLD, so the decision is safe; the reason string is
coarser than it could be. Left as-is rather than guessed at, and noted here.

## Reproduce

```
python tools/demo_revocation.py --work /tmp/revdemo --python <python>
```

Exit 0 means all eight runs matched and neither package's tree hash moved; 1 means at least
one run diverged. `--json` emits the rows plus both sets of hashes.

## 中文摘要

`tools/demo_revocation.py` 现在在两个包上跑八遍门禁：HMAC 包四遍（无覆盖层 `ALLOW` / 有效撤销
`DENY` exit 2 / 无钥匙 `HOLD` / 他钥签名 `HOLD`），Ed25519 包四遍（同上，但用**公钥**验撤销）。
两个包的树哈希前后各自一致——证明翻红来自覆盖层而不是字节变动。

本轮把上一轮照实写下的限制关掉了：撤销签名现在支持 **Ed25519**，`uibc revoke` 用 owner seed 签、
gate 用 `--pubkey` 验，**任何拿到公钥的第三方都能自己确认"持有者真的作废了这个包"**，
不需要持有者本人出手。

顺带记下一个自己踩的坑：第一版 `revoke` 只签了四个基础字段，签完才补 `algorithm`/`key_id`，
而 gate 规范化时只剥掉 `signature` —— 于是每一份"合法"撤销都验不过。**签名方与验证方必须
规范化同一组字段**。这个坑一次首跑就能发现，跨机反而发现不了。
