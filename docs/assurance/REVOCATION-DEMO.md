# The overlay, shown doing its job: same bytes, clean verify, still denied

**One-line claim** — `tools/demo_revocation.py` builds one package, then runs the gate four
times on it, and every run behaves as the decision rules say:

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

## A limitation this demo exposed (stated, not smoothed)

Revocation signatures are **HMAC-only** (`crypto/gate.py::_verify_body`). Our product path
seals with Ed25519, and there is no way for the gate to check an HMAC signature against an
Ed25519 public key. So an Ed25519-sealed package with a revocation attached lands on
`HOLD (UNVERIFIABLE)` — the honest answer, but it means **"revocation blocks" is true only
for HMAC-sealed (v0.2-era) packages today**.

That is a real gap, not a wording problem. It is asserted by
`test_ed25519_package_with_revocation_holds` so that a future change which starts returning
`ALLOW` there is caught as a regression rather than celebrated as a feature.

The fix, when it is worth doing, is an asymmetric revocation: sign the revocation body with
the Ed25519 owner seed and verify it against the pinned public key, keeping HMAC support for
old packages. Not done in this round — no test corpus of "which key revoked what" exists yet,
and inventing one quietly is exactly the habit this repository is trying to lose.

## Reproduce

```
python tools/demo_revocation.py --work /tmp/revdemo --python <python>
```

Exit 0 means all four runs matched and the tree hash did not move; 1 means at least one
run diverged. `--json` emits the same rows plus the hashes.

## 中文摘要

`tools/demo_revocation.py` 在一个包上跑四遍门禁：无覆盖层 → `ALLOW`；有效撤销 → `DENY`（exit 2）；
撤销但没给钥匙 → `HOLD`（exit 3）；撤销由别的钥匙签 → `HOLD`。**包内字节前后哈希完全一致**——
这是"覆盖层让决策变红、而不是字节变了"的唯一可信演示。
两行 `HOLD` 比 `DENY` 更重要：草率实现会把"验不了的撤销"当成"没有撤销"而放行，这两行堵死这条路。
顺带暴露的真实限制：撤销签名目前只支持 HMAC，Ed25519 封的包附撤销只能 `HOLD`——所以
"撤销即阻断"今天只对 v0.2 HMAC 包成立。该限制有测试钉住（返回 ALLOW 会被判为回归）。
