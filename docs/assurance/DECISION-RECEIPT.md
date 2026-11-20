# The decision receipt: a verdict somebody else can redo

**One-line claim** — `tools/admit_package.py` writes a receipt next to the package, and
`tools/verify_decision.py --package <pkg> --receipt <file>` recomputes every field of it
from the bytes alone, printing `MATCH` or naming the field that moved.

**It is not** a signature by an authority, a transparency-log entry, or a statement that
`ALLOW` was the right call. It is a description of a decision that can be checked.

## Why this exists

A record that says `admission decision: ALLOW` is something a reader has to *trust*. The
whole point of the assurance pages is that claims should be recomputable rather than
believed, and the admission record was the one place where that rule was not applied to
ourselves: the decision was prose in a file we wrote.

So the decision now travels as data with three parts:

| part | what it pins | example |
|---|---|---|
| `package_root` | the sealed package's whole file tree | `a9447bdb…59d3` |
| decision fields | `decision`, `reason`, `verify_result`, `revocation`, `dispute`, versions | `ALLOW` / `verify PASS, no revocation, no dispute` |
| `receipt_sha256` | the receipt's own canonical bytes | `233b5b6a…2a38` |

`package_root` is a sha256 over sorted `path\0size\0sha256` lines of every file in the
package, using relative paths — so a copy of the package on another machine, in another
directory, has the same root, and a package that differs in one byte of one file does not.

## What the checker actually does

```
python tools/verify_decision.py --package /tmp/admit \
    --receipt /tmp/admit.decision.json --pubkey owner.key.pub
```

1. Re-hash the receipt's canonical bytes → compare `receipt_sha256`.
2. Re-hash the package tree → compare `package_root`.
3. Re-run `uibc gate` on the package (with the pinned key if given) → compare each
   decision field, one row per field.

Exit `0` when all rows match, `1` when any row differs, `2` on usage or missing input.
The `--json` form emits the same rows for machines.

## The three negative controls (measured on this repository)

| tampering | what turns red | why it must |
|---|---|---|
| one byte flipped inside the sealed artifact | `package_root`, `decision`, `reason`, `verify_result` | the receipt described different bytes; the decision genuinely changed |
| one field edited in the receipt, then re-hashed by the forger | `package_root` only | the receipt is internally valid — self-consistency alone proves nothing |
| one field edited, *not* re-hashed | `receipt_sha256`, and that field | the file was edited after it was written |

The second row is the one worth keeping: a checker that only validates the receipt's own
hash would pass a forged receipt. That is why `package_root` is computed from the package
on disk rather than trusted from the receipt.

Measured run on 2026-11-20, Windows 11 / Python 3.13.15, 33-member wheel:

```
| receipt_sha256 | 233b5b6a1b93… | 233b5b6a1b93… | MATCH |
| package_root   | a9447bdb2865… | a9447bdb2865… | MATCH |
| decision       | ALLOW         | ALLOW         | MATCH |
… all rows MATCH, exit 0
```

After flipping byte 4 of the sealed wheel: `package_root`, `decision`, `reason`,
`verify_result` all `MISMATCH`, exit 1.

### A second machine, and a copy at another path (measured 2026-11-20)

Linux 6.6.95 / Python 3.12.11, fresh clone of `a7210af`, fresh venv, wheel built there:

| run | result |
|---|---|
| admit the wheel just built (129387 B, sha256 `16a15b28d5c7…`) | `ALLOW`, `package_root 24f0f7c6b85a…`, receipt written |
| `verify_decision.py` on the same package | all rows `MATCH`, exit 0 |
| same bytes copied to a different directory, then checked | all rows `MATCH`, exit 0 |

The receipt contains **no absolute path** — not the package, not the temp dir, not the
wheel name with a separator. Measured on the written file: zero occurrences of the
working directory. That is enforced by a test
(`test_the_receipt_carries_no_machine_specific_paths`) and by
`test_a_package_copied_to_another_path_keeps_the_same_root`, because otherwise
"third party can recompute" would quietly mean "third party on the same disk can
recompute".

## The stranger's case: artifact + receipt, no package

The full recomputation needs the sealed package, which is ours. Somebody who downloaded a
wheel has the file and (at most) the published receipt. So there is a second mode:

```
python tools/verify_decision.py --artifact pkg-1.0.whl --receipt pkg-1.0.decision.json
```

Four fields are checkable from the file alone — `subject.name`, `subject.sha256`,
`subject.bytes`, `subject.members` — plus the receipt's own hash. The remaining eight
(`package_root` and the seven decision fields) are printed as **NOT CHECKABLE**, not as
passes:

```
**MATCH on every checkable field** — 8 field(s) could not be checked without the sealed
package: package_root, decision, reason, verify_result, gate_version, verifier_version,
revocation, dispute. What is proven here is narrower than the full recomputation, and the
report says so instead of printing a bare MATCH.
```

This is the honest half of "the decision applies to your download": it proves *the receipt
is about this file*, and it refuses to imply *the decision was redone*. A different file
turns `subject.sha256`, `subject.bytes` and `subject.members` red and exits 1. A **renamed**
copy of the same file does not: a browser saving `pkg (1).whl` is the ordinary case, so
`subject.name` is printed as `NOTE` and stays out of the verdict — the bytes decide.

That was a defect found by running the tool on the second machine, not by reading the
code: the first version compared the name like any other field, so `cp wheel.whl other.whl`
flipped the whole verdict to `MISMATCH`. The control is now a test
(`test_a_renamed_download_is_not_a_failure`).

## The overlay is recomputable too

Until this round, the receipt recorded `revocation: {status: REVOKED}` but could not prove
it: a reader could redo the verify verdict on the bytes, and had to **take our word for the
part that turned a PASS into a DENY** — which is exactly the part worth checking, and the
only capability here that a competitor does not have at all.

Now the receipt pins the overlay:

```json
"overlay": {
  "revocation_id": "r-abb042d4c930a9d6",
  "target_root": "3364e90c…",
  "body_sha256": "6459e594…",
  "key_id": "2a82cdf4…",
  "algorithm": "Ed25519",
  "reason_code": "OWNER_REQUEST"
}
```

`body_sha256` is the sha256 of the canonical revocation body (everything except
`signature`) — computed by `uibc revocation-digest`, i.e. by the **same** canonicalization
the signer and the gate use. A second implementation here would be the #319 bug in slow
motion: two canonicalizations drift, and a valid signature stops verifying.

A reader holding four files — package, receipt, `revocation.json`, owner's `--pubkey` —
now redoes the whole decision:

```
python tools/verify_decision.py --package pkg --receipt pkg.decision.json \
    --pubkey owner.key.pub --revocation revocation.json
```

Measured on this repository:

| control | result |
|---|---|
| four files, nothing edited | **MATCH** on 15 fields, `decision DENY` reproduced, exit 0 |
| the revocation file not supplied | decision/reason/overlay printed **NOT CHECKABLE**, `MATCH on every checkable field`, exit 0 |
| receipt's `body_sha256` edited and the receipt re-hashed | only `overlay.body_sha256` red, exit 1 — the self-hash alone would have passed the forgery |
| revocation body edited (`OWNER_REQUEST` → `EVIDENCE_INVALID`) | signature no longer verifies → gate `HOLD`; `decision`, `overlay.body_sha256`, `overlay.reason_code` red, exit 1 |

The second row is a deliberate choice: a reader who forgot an input must **not** be accused
of holding a lying receipt. The tool says the result is narrower and names what is
missing, instead of printing `MISMATCH` for its own absent input.

## Boundaries

- **Scope**: the receipt covers the package tree and the gate's answer on it. It does not
  cover the artifact's content, its behaviour, or its dependencies — same three
  `not_covered` lines as the admission record, copied into the receipt so a downstream
  report cannot drop them.
- **No witness**: `receipt_sha256` is self-referential. Anyone can recompute a receipt over
  a package they built; what it proves is that *this* receipt and *these* bytes agree, not
  that the decision was made at the time it claims. Timestamps remain unanchored.
- **No rate**: the receipt carries the seven-field disclosure row with `n/a` in the
  numerator and `1 artifact` in the denominator. One decision is not a sample.
- **Same person, two machines is not independence**: reproducing the decision elsewhere
  is E2. A stranger running the checker is E4, and that has not happened yet.

## 中文摘要

`admit_package.py` 现在在包旁边写一份**决策回执**（`package_root` + 决策字段 + 自哈希），
`verify_decision.py` 只凭"包 + 回执 + 公钥"就能把每个字段重算一遍，逐行打 `MATCH`/`MISMATCH`。
三条反向对照都实测过：改包内一字节 → 根与决策一起红；改回执一个字 → 只有自哈希与那一行红；
**伪造者改完再重算哈希** → 回执自洽但 `package_root` 对不上——所以光验自哈希不够，
根必须从磁盘上的包现算。它不证明 `ALLOW` 判得对，只证明"这份回执说的就是这些字节现在的结果"。
证据等级不动：同一持有人复现仍是 E2。

**本轮新增（覆盖层也可复算）**：回执原来只记录"撤销 → `REVOKED`"，读者只能信——因为
把 `PASS` 翻成 `DENY` 的那一步恰恰最值得查，也是对手完全没有的那条能力。现在回执多一段
`overlay`，钉住撤销体的规范哈希（`body_sha256`，由 `uibc revocation-digest` 算，与签名方、
gate **共用同一套规范化**，避免 #319 那种"两份规范化各写一份"的坑）。
读者拿四个文件（包、回执、`revocation.json`、owner 公钥）就能自己重做整个判决，
实测四种对照：四件齐全 → 15 字段全 `MATCH`、`DENY` 复现、exit 0；**不给撤销文件** →
相关字段打 `NOT CHECKABLE` 而不是 `MISMATCH`（读者漏了输入，不该被指控为伪造）、
exit 0 且明说"比全量复算窄"；改回执里的 `body_sha256` 再自算哈希 → **只有那一行红**；
改撤销体（`OWNER_REQUEST`→`EVIDENCE_INVALID`）→ 签名验不过、gate 转 `HOLD`，
`decision`/`body_sha256`/`reason_code` 三行红，exit 1。

