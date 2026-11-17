# Architecture

One page, then the boundaries. Nothing here is aspiration — it describes what the code in this repository actually does at v0.3.3.

## What this repository is responsible for

Packaging an agent's lifecycle as **evidence**, sealing it, and producing a **verifiable verdict** that a stranger can reproduce without permissions.

## What it is explicitly not responsible for

- **Not runtime blocking.** There is no inline proxy, firewall or "shut down the agent" capability. Verification happens on a package, after the fact. A runtime component exists under `runtime/` for experiments only and is not part of the verdict path.
- **Not certification or licensing.** No result here grants permission to operate anything.
- **Not content truth.** A seal binds bytes to a key. It does not make the bytes accurate. `docs/verdict-and-seal-semantics.md` is normative on this.
- **Not identity issuance.** A registry can record an agent; that is a record, not an authoritative identity provider.

## Data flow

```
register ──▶ manifest (identity, owner, capabilities, lifecycle)
   │
   ├─ event ──▶ append-only lifecycle events
   ├─ evidence ─▶ files hashed, index written
   ▼
submit ──▶ evidence_root computed over the index (canonical serialisation)
   │        seal: Ed25519 over the canonical package digest, records key_id
   ▼
verify ──▶ S1..S6 checks ──▶ three-valued verdict ──▶ report
```

## The six checks (normative list)

| Check | Asks | Fails when |
|---|---|---|
S1 | Is the package structurally well-formed? | Required files/fields missing or unparseable |
S2 | Is the identity consistent across files? | agent_id / owner disagree between manifest and events |
S3 | Does the lifecycle state machine hold? | An event order impossible under the declared transitions |
S4 | Do the evidence content hashes match the bytes? | Any file changed, added or removed |
S5 | Does `evidence_root` match the index? | Index rewritten or reordered |
S6 | Does the seal verify against a trusted key? | Signature invalid, or no key available and none pinned |

Each check returns PASS / FAIL / INCONCLUSIVE (and SKIP only where it does not apply). The top-level verdict:

| Condition | Verdict |
|---|---|
any check FAIL | **FAIL** |
else any INCONCLUSIVE | **INCONCLUSIVE** |
else | **PASS** |

PASS is therefore reserved for packages where every applicable check actually resolved. This is a v0.3 change and it exists because of a demonstrated defect: in v0.2 a fully self-consistent forgery — evidence rewritten, all hashes recomputed — verified PASS in open mode, since the only provenance-relevant check was unresolved while the top-level verdict said PASS. The detail line was honest; the verdict was misleading. See `docs/adr/ADR-001-three-valued-verdict.md`.

## Three invariants

1. **No verdict without a reason.** Every check records which condition produced it; a verdict with no reason is a bug, not a shortcut.
2. **A seal binds origin, not ownership.** Unpinned, a substituted key verifies against itself. Only pinning answers "whose".
3. **Version identity travels with the evidence.** Package, policy and engine versions are recorded; a change invalidates prior verdicts by design, not by convention.

## Module map

| Module | Role |
|---|---|
`canonical.py` | Deterministic serialisation and file hashing — the basis of every equality claim |
`lifecycle.py` | Event append and the state machine checked by S3 |
`gate.py` | Governed decision: ALLOW (0) / DENY (2) / HOLD (3) |
`verify.py` | S1–S6 and the three-valued verdict |
`signing.py`, `ed25519.py` | Seal generation and verification, `key_id` derivation |
`certificate.py` | Certificate issuance over a verified package, and its verification |
`mcp_server.py` | MCP surface (`uibc-mcp`) |
`runtime.py`, `memory.py` | Experimental; not on the verdict path |
`independent_verifier/` | Second implementation written against the semantics text, not against this code |
`fixtures/EXPECTED.md` | The pinned outcome matrix every implementation must reproduce |

## Where to go next

`QUICKSTART.md` (five verified minutes) → `docs/verdict-and-seal-semantics.md` (what a verdict means) → `fixtures/EXPECTED.md` (what must stay true) → `SUCCESSION.md` (how someone else takes this over).

---

# 架构说明

一页说清，然后说边界。以下描述的是本仓 v0.3.3 代码**实际在做的事**，不是计划。

## 本仓负责什么

把一个 Agent 的生命周期打包成**证据**、封签，并产出**任何人都能复现的判定**。

## 本仓明确不负责什么

- **不做运行时阻断**：没有内联代理、防火墙或"关停 Agent"的能力。验证发生在包上、发生后。`runtime/` 下的运行时组件仅供实验，不在判定路径上。
- **不是认证、不是许可**：任何结论都不授予运营权限。
- **不证明内容真实**：封签只把字节绑到钥匙上，不保证字节准确。规范文本见 `docs/verdict-and-seal-semantics.md`。
- **不做身份签发**：登记簿可以记录一个 Agent，那是记录，不是权威身份源。

## 数据流

```
注册 ──▶ manifest（身份、所有者、能力、生命周期）
   ├─ 事件 ──▶ 只增生命周期事件
   ├─ 证据 ─▶ 文件哈希 + 索引
提交 ──▶ 依规范化序列化算出 evidence_root ──▶ Ed25519 封签（记录 key_id）
验证 ──▶ S1..S6 ──▶ 三值判定 ──▶ 报告
```

## 六项检查（规范性清单）

| 检查 | 问什么 | 何时 FAIL |
|---|---|---|
S1 | 包结构是否完好 | 必需文件/字段缺失或不可解析 |
S2 | 身份在各文件间是否一致 | manifest 与事件的 agent_id / owner 不一致 |
S3 | 生命周期状态机是否成立 | 事件顺序在声明转移下不可能 |
S4 | 证据内容哈希是否对上字节 | 任何文件被改、增、删 |
S5 | `evidence_root` 是否对上索引 | 索引被改写或重排 |
S6 | 封签能否对着受信钥匙验通 | 签名无效，或无钥匙且未钉住 |

顶层判定：任一 FAIL → **FAIL**；否则任一 INCONCLUSIVE → **INCONCLUSIVE**；否则 **PASS**。因此 PASS 只留给"每一项适用检查都真正解决了"的包。这是 v0.3 的改动，起因是一个被实证的缺陷：v0.2 下一个完全自洽的伪造件在开放模式下被判 PASS——详情行是诚实的，顶层判定却是误导。见 `docs/adr/ADR-001-three-valued-verdict.md`。

## 三条不变量

1. **无理由的判定不成立**：每项检查记录是哪一条条件触发的结论。
2. **封签绑来源，不绑归属**：未钉住时，替换的钥匙对自己有效。
3. **版本随证据同行**：包/策略/引擎版本入证；版本一变，旧判定即失效。

## 模块表

见英文段落中的 Module map 表格（`canonical` / `lifecycle` / `gate` / `verify` / `signing`+`ed25519` / `certificate` / `mcp_server` / `runtime`+`memory` / `independent_verifier` / `fixtures`）。

## 往下读什么

`QUICKSTART.md`（实测五分钟）→ `docs/verdict-and-seal-semantics.md`（判定是什么意思）→ `fixtures/EXPECTED.md`（什么必须一直成立）→ `SUCCESSION.md`（别人怎么接手）。
