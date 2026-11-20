# uibc-core

<!-- mcp-name: io.github.zhaoxinghua09-cell/uibc-core -->

**Name note:** UIBC here means *Uniform Identity-Behavior Chain* — an agent-evidence verifier.
It is **not** the clinical chemistry assay of the same acronym (unsaturated iron binding capacity),
and it is unrelated to the UIBCDF computational-biology organisation.

> **有人验过吗？先看 [EVIDENCE-INDEX.md](EVIDENCE-INDEX.md)** — 按 L1 自我复现／L2 异体审查／L3 第二实现／L3.5 外部语料／L4 外部节点分级；外部节点当前为 **1**（[EXTERNAL-NODE-001](external-review/EXTERNAL-NODE-001.md)：异体机、无特权、按 README 逐字跑，首跑即复现了我们自己报的 S4/S5 分歧），其余三行仍为 0。
>
> **不知道从哪进？先看 [STRUCTURE.md](STRUCTURE.md)** — 五层地图（规范／实现／工具／验证／存证）与三条阅读路线。
>
> **想知道现在到底到哪一步？看 [STATUS.md](STATUS.md)** — 一页纸，每个数字都由 `python tools/status_page.py` 从仓库里算出来，
> 它和仓库对不上时 `--check` 会红；六个维度的"我们缺什么"逐条列出，不留形容词。

## Verify it yourself — one command, no install, no account

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core && python tools/external_node_check.py
```

It prints `CONSISTENT` only when **both** hold: a second, independently written verifier agrees with the reference one, **and** three packages that must be rejected (timestamp without a zone, `1900-02-29`, uppercase UUID) are rejected. A checker that answers PASS for everything cannot pass this.

### Or don't clone at all — run the corpus in about sixty seconds

Fetch it anonymously, without cloning (no login, no token — measured 2026-11-20, the bytes match the pin exactly):

```bash
curl -fL -o corpus.zip \
  https://github.com/zhaoxinghua09-cell/uibc-core/raw/main/conformance/uibc-conformance-0.4.1.zip
sha256sum corpus.zip   # 711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f, 228,000 bytes
unzip -q corpus.zip -d corpus && cd corpus && python run.py
```

There is **no** release asset for `0.4.1` (the newest release, `v0.4.0`, carries `uibc-conformance-0.4.0.zip`, which is not this corpus) — the URL above is the entry point, and if it ever stops resolving that is a defect we want reported, not something to work around. The build is deterministic for a given tree, but "rebuilding gives the same bytes" is true only from the tree the archive was built from: `0.4.1` came out of commit `d72c4f9`, and the runner template was fixed for the unstartable-verifier case afterwards, so rebuilding `0.4.1` from today's tree yields a different archive (`083c0dbc…`). The builder now refuses to overwrite a pinned archive and prints both hashes instead (measured 2026-11-20, exit 3).

No repository, no network, no `pip install`: the archive carries its own verifier as a single file (`uibc_core.pyz`), and `run.py` uses it. Expected tail `strict 36/36` in about six seconds, and a `receipt.json` you can publish. A verifier that answers PASS to everything scores **6/36**, so refusing nothing does not pass.

The number above is **our own run**. It becomes an external node report only when someone else runs this same archive digest elsewhere and posts the receipt — the format, the checker (`tools/check_outward_receipt.py`) and the issue form are in [`docs/RECEIPT-FORMAT.md`](docs/RECEIPT-FORMAT.md), and the walk-through is [`docs/AUDIT-KIT.md`](docs/AUDIT-KIT.md). If no unrelated party has done that by **2027-05-19**, that sentence gets downgraded to "self-run only" rather than left standing; the clause is in AUDIT-KIT, written before the outcome was known.

**What a PASS means** — and nothing more:

> A uibc PASS means: within the observed evidence boundary, no violation was detected. It does not claim the agent was correct, safe, or wise; that the recorded inputs were true or complete; or that any real-world outcome followed.

**Current state, including what we are short of:** the full suite green on Linux / Python 3.12 (the exact count is pinned in `docs/EVIDENCE-INDEX.md`; a stale number here is worse than no number) (2 skipped with `.[verify,interop]`; it was 16 before that extra existed — see `docs/SKIPPED.md`); the CI matrix runs the same suite on 3.10-3.13 · the verifier needs no third-party package (Ed25519 is implemented in-repo) · **external verification nodes: 1** — see [EXTERNAL-NODE-001](docs/external-review/EXTERNAL-NODE-001.md): a named operator on Debian 13 we do not control, unprivileged, no `pip install`, README commands verbatim. His first run reproduced the duplicated-`evidence_id` divergence this repository had filed against itself, and his re-run on the fix branch returned `AGREEMENT: PASS` with no mismatch. Running the command above and sending back `external_node_result.json` makes it 2. While the number was 0, the independence of this repository's verification rested entirely on two implementations written by the same author. One node is a node, not a sample — it is third-party execution, not third-party interest.

**Seven machine reviews do exist, and they are not this number.** `docs/external-review/` holds seven receipts written on 2026-11-17 by an external model (DeepSeek-V3 via SiliconFlow) in four lenses (expert / process / adversary / outsider). Under `INDEPENDENCE.md` those are stage **S3m/S4m** machine reviews: they must be labelled `reviewer_type: machine`, and they may not be described as a third party, because no human and no separate administration stands behind them. Counted by category: human independent reproduction **1** (EXTERNAL-NODE-001 — third-party execution, requested, and he is a correspondent in the same working group, so not a disinterested auditor); external machine review 7; external document citing this repository 0; adoption by any group 0. Quoting any one of those four as "external 0" without saying which line is meant is the kind of collapse this repository exists to catch.

**Three version numbers, and they disagree — read this before installing:** `main` is **0.4.0**, unreleased. PyPI carries **0.3.3** (2026-11-15). The archived citation snapshot is **0.2.1** (2026-09-17). If you `pip install uibc-core` you get the 0.3.3 verifier, which reports six checks on the clean package where `main` reports eight — S11 (strict serialization) and S12 (identifier strictness, `evidence_count`) came after that release. The measurement, with commands and timings, is in [docs/STRANGER-TRIAL.md](docs/STRANGER-TRIAL.md). Cite the snapshot, run `main`, and do not assume the PyPI build is the one these documents describe.

**External conformance, measured against someone else's corpus** — a different number from the one above, and a different kind of claim:

| item | value |
|---|---|
| corpus | [`probityai/agent-evidence-vectors`](https://github.com/probityai/agent-evidence-vectors) 0.37.0, suiteRevision 32 |
| corpus digest | `bf3e5befd71640757ff1b3f0af63520364b823b5e3f9059678f72f64a46e11c1` |
| command | `uv tool run "agent-evidence-vectors==0.37.0" --verifier "python -m uibc_core.aee"` |
| result | **288 vectors, 288 pass, 0 fail** · `rail: external` · `vectorsExecuted 288 of 288` · `suiteRefusals 0` · `reasonParityMismatch 0` |

This is a corpus written by someone else, driving third-party verifiers through its own
contract, executed against `uibc_core/aee.py` with no vector refused. It covers the **AEE
predicate only** — it is not a claim that this repository passes every agent-evidence format,
and it does not turn the count above into 1: that counter is about people sending back this
repository's own node result.

**Three more commands, if you want to see the failure paths rather than the green ones:**

```bash
python -m unittest discover -s tests -p "test_*.py"        # full suite (Linux / Python 3.12, 2 skipped with .[verify,interop])
python tools/emit_receipts.py --package fixtures/clean.uibc --count 3   # 3 chained receipts
python tools/redteam_suite.py                              # 16 attacks, expected vs actual
```

**Check us without our code**: [`docs/conformance/vectors.json`](docs/conformance/vectors.json) —
29 language-neutral vectors across seven steps (canonical bytes, Ed25519 valid/invalid,
receipt envelope digests, the linear chain link, RFC 6962 Merkle roots and inclusion paths,
policy artefact digests, and anchor binding against a real RFC 3161 token). A checker that
imports nothing from this project reproduces all 29, verifying signatures with the third-party
`cryptography` library and reading the token with `asn1crypto`:
`python tools/conformance_check.py`.
What it does **not** prove: that a second implementation of the whole receipt exists —
it does not (see [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md)).

**Check what each reject case rests on**: [`docs/GROUNDS.md`](docs/GROUNDS.md) — one page,
twenty must-reject cases, the kind of basis each has (draft-mandated / borrowed idea / our
own choice), and the five sentences quoted verbatim, each re-found in the vendored draft by
`python tools/check_grounds.py`. The page is generated from the data and a test fails when
the two disagree. What it does **not** prove: that a quoted sentence is read the way its
author intended, or that a check implements all of it.

**Verify someone else's receipt, offline** — a receipt we did not issue, digested by our own code:

| item | value |
|---|---|
| sample | [Zambo](https://zambo.dev/run/5f908958-6c31-4293-b239-b2122699e14b) (AER-1, `draft-zambo-aer1-26`), fetched 2026-11-18 |
| canonical bytes | 678 B, `receipt_schema_version` `0.4` |
| their published digest | `sha256:b08808742328c65f1bb0b8e9c050f55aed3f4626e852043fa6d7b1428c3c82bc` |
| our `canonicalize()` output | **same 678 bytes, same digest** |
| `side_effects.declaration_hash` | `45aad38f…1bfee` — recomputes |
| envelope signature | **none**; the page itself states issuer authentication is not checked |

`python tools/zambo_interop_check.py` prints `DIGEST_BINDS_BYTES (issuer NOT authenticated)`.
What this proves: two independent implementations canonicalize the same receipt to the same
bytes, so a digest can travel between them. What it does **not** prove: that the issuer is
who it says (there is no signature to check), that we conform to AER-1's 143-vector suite
(we do not), or that offline anchoring beats published-relay anchoring — different
questions, kept apart in [`docs/INTEROP-ZAMBO.md`](docs/INTEROP-ZAMBO.md).

**What the demo catches that a digest cannot** — `python -m uibc_core.cli demo`, 8 steps, exit 0, measured 2026-11-18:

| step | scene | verdict |
|---|---|---|
| 5 | a stranger verifies with the published seal only — no key, no permission | `PASS` (assurance: `public-key`) |
| 6 | evidence edited behind the owner's back | `FAIL` (tampered content) |
| 7 | attacker recomputes **every** hash and re-seals with the attacker's **own** key | `PASS` — a substituted key verifies against itself |
| 8 | the same forged package, verified **pinned** to the owner's public key | `FAIL` (key substitution caught) |

Steps 7–8 are the pair we have not seen demonstrated by the receipt projects we compared
against: a forgery that looks entirely valid passes until the verifier pins a key, and
pinning is what turns it into a `FAIL`. Digest-level agreement (the section above) cannot
show this — it only shows two implementations agree on bytes, not that a verifier refuses
the right thing. Run it yourself; the whole demo leaves nothing behind but a temp dir.



**Verified vs not verified, in one place** (full detail in [`docs/EXTERNAL-ANCHOR.md`](docs/EXTERNAL-ANCHOR.md)):

| item | state | how you check it yourself |
|---|---|---|
| RFC 3161 external timestamp (Free TSA) | verified | `python tools/anchor_tsa.py --verify tests/fixtures/anchor/freetsa.tsr --data tests/fixtures/anchor/anchored_head.json --cabundle tests/fixtures/anchor/freetsa_ca.pem` — token, its CA bundle and the anchored file are all in the repo, so no network and no account |
| OpenTimestamps second anchor | **pending calendar only — not a Bitcoin anchor** | `python tools/anchor_ots.py --verify tests/fixtures/anchor/anchored_head.json --proof tests/fixtures/anchor/ots_head.ots` prints `pending_calendar` and never a Bitcoin claim; a block attestation would have to appear in the proof for it to be an anchor |
| Rekor entry + SET signature | written and verified | `rekor-cli get --log-index 3944456520 --rekor_server https://rekor.sigstore.dev`, then check the SET with the log public key published in `tests/fixtures/anchor/rekor_log_pub.pem` — the verification needs only that public key, never Sigstore's private infrastructure |
| Rekor **inclusion proof** | **does not verify** — ours and a third-party implementation both fail; published as-is | `python tools/anchor_rekor.py --verify tests/fixtures/anchor/rekor_entry.json --artifact …`; `python -m unittest tests.test_v13_rekor -v` shows the SET check passing and the inclusion proof not overclaimed. The failure is a defect we have not fixed, not a design choice |

The two Rekor indices are different objects and must not be conflated: `2883389783` is the
entry for the earlier release bundle in `dist/`, `3944456520` is the entry for the anchor of
this repository's head digest. Each is distinct within the log; neither is a claim that the
other exists.

**Not** a QMS, and **not** a competing receipt standard: it answers one question a platform cannot answer about itself — *can a stranger recompute your conclusion, offline?*

**What has been reviewed, and what it changed**: [`docs/REVIEW-LOG.md`](docs/REVIEW-LOG.md) — seven rounds by an external model under four different question sets, the receipts verbatim, what was accepted, and one suggestion that was **refused** because we could not substantiate it.


> **在线门户 Portal**：https://zhaoxinghua09-cell.github.io/lgd-hub/ — LGD 生态全景（理论 / 参考实现 / 技能全库），一跳即达。


> **获取仓库 / Get the repo**：`git clone https://github.com/zhaoxinghua09-cell/uibc-core.git`（若 clone 失败，请点仓库页 **Code → Download ZIP** 获取源码包）。

> **层级定位**：**可执行协议层（Protocol）** — LGD 生态中 registry / evidence / gates 的参考实现。词汇表与全景见 [LGD 门户](https://zhaoxinghua09-cell.github.io/lgd-hub/)。
## 许可说明 · License Notice

- **权利状态**：本仓库以 **Apache-2.0** 许可发布，可依该许可证条款自由使用、修改与再分发。
- **引用建议**：引用时请标注仓库名与原文链接 `https://github.com/zhaoxinghua09-cell/uibc-core`
  与权利人「赵兴华 / Steven Zhao·China」。
- **品牌状态限定**：MedXpert、SynomosAI、LGD 等为相关项目标识，
  **均未申请实体注册、未申请商标注册**；出现仅作来源标识，
  不构成对法人实体或商标权的任何主张。
- **完整条款**：见仓库根目录 [LICENSE](https://github.com/zhaoxinghua09-cell/uibc-core/blob/main/LICENSE)。
- **联系**：zhaoxinghua09 [at] gmail [dot] com ｜ ORCID 0009-0001-0512-1237

---

<!-- AI-QUICK-READ:START -->
**EN**: LGD (Lifecycle Governance Doctrine) is a governance doctrine for autonomous systems. Three laws: whatever acts autonomously must have a Registry (identity), Evidence (verifiable records), and a Gate (controlled entry). Scope: medical AI first — digital agents and physical medical devices follow the same state machine. Verifiable artifacts: reference implementation github.com/zhaoxinghua09-cell/uibc-core (Apache-2.0), concept DOI 10.5281/zenodo.22456647, Sigstore Rekor logIndex 2883389783. Cite as: "LGD (Lifecycle Governance Doctrine), DOI 10.5281/zenodo.22456647."

**中文**：LGD（全程治理论）是面向自治系统的治理论。三律：凡自治之物，有籍、有证、有门禁。适用域：医疗 AI 优先，数字 Agent 与物理医械同一状态机。可核验：参考实现 uibc-core（Apache-2.0）、概念 DOI 10.5281/zenodo.22456647、Rekor logIndex 2883389783。引用：LGD (Lifecycle Governance Doctrine), DOI 10.5281/zenodo.22456647。
<!-- AI-QUICK-READ:END -->
> **LGD for Medical AI** — uibc-core is the reference implementation of the LGD (Lifecycle Governance Doctrine) operational
> governance laws, applied to medical AI / medical-device compliance.
> **Verifiable today** — every artifact is independently checkable: Sigstore Rekor transparency log
> (logIndex 2883389783), concept DOI 10.5281/zenodo.22456647, SWHID
> `swh:1:ori:819530c8be2adf6da901256ce9fd28063f8f1296` (ISO/IEC 18670).
> Reproduce: `python -m unittest discover -s tests -p "test_*.py"` (full suite, Linux / Python 3.12) · `python independent_verifier/cross_check.py`.
> **Honest boundary** — no third-party quality review to date; any operational use is self-reported
> (see ENDORSEMENTS.md: 存证 ≠ 参与 ≠ 认可). Context: [FG-TIDA themes #27](https://github.com/FG-TIDA/themes/issues/27).


[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/zhaoxinghua09-cell/uibc-core/badge)](https://api.scorecard.dev/projects/github.com/zhaoxinghua09-cell/uibc-core)
[![CI](https://github.com/zhaoxinghua09-cell/uibc-core/actions/workflows/ci.yml/badge.svg)](https://github.com/zhaoxinghua09-cell/uibc-core/actions/workflows/ci.yml)

> **万物互联，数智共生** —— Everything Connected, Digital-Intelligence Symbiosis.

UIBC Core 参考实现 v0.3.3 —— Agent 生命周期证据包与验证器：三值裁决（PASS / FAIL / INCONCLUSIVE，未决不洗成通过）＋ Ed25519 公开封签（任何人可验、可钉住公钥）。

> 版本口径：PyPI 上已发布到 `0.3.3`；本仓 `zenodo_deposit/` 备好的存缴包是 **0.3.0** 那一版快照（419 项），两者不是同一份字节。

理念（LGD）：**有籍 · 有证 · 有门禁** → Registry（身份注册）/ Evidence（内容哈希证据 + 封签）/ Gates（生命周期状态机 + 验证门禁）。

> ⚠️ 状态：PROPOSAL，非正式标准。验证结果是**限定范围的证明**（scoped proof）：
> PASS 仅表示"在观测到的证据边界内未发现违规"，不声称绝对可信。

> 🔏 发布产物已进入 Sigstore Rekor 公共透明日志（条目 `2883389783` 属早期发布产物 `dist/*.cosign.bundle`；另有条目
> `3944456520` 记录本仓 head 摘要的外部锚，见 `docs/EXTERNAL-ANCHOR.md`）。
> **包含证明（inclusion proof）目前验不过**：我们的 RFC 6962 走法与第三方库 `rekor_log_verifier` 同时失败，如实记在文档里。
> Zenodo **概念 DOI** `10.5281/zenodo.22456647` 属 LGD 理论本体；**本包 0.3.0 的单独 DOI 尚未分配**（存缴包已备，需本人登录上传）。
> Software Heritage SWHID 见 `CITATION.cff`。
> 以上均为**存证**，非质量认可。

## The claim we make (and the claim we refuse to make) · 窄声明

> **A uibc PASS means: within the observed evidence boundary, no violation was detected.
> It does **not** claim the agent was correct, safe, or wise; that the recorded inputs were
> true or complete; or that any real-world outcome followed.**

中文：uibc 的 PASS 只表示"在观测到的证据边界内未发现违规"，不表示 agent 正确、安全、明智，
不表示记录的输入为真或完整，也不表示任何现实结果已经发生。本仓库任何位置出现的数字，
都不得被读成"可信度"或"通过率"。

## Terminology alignment · 术语与上游对齐

本项目**不自造词**。下列术语与已有草案是同名或上下位关系，写清楚是为了让评审方一眼判断
哪些是我们的增量、哪些是复用。完整映射见 `docs/TERMINOLOGY.md`；
我们的定位与"不主张什么"见 `docs/COMPOSITION-VERIFIER.md`。

**可复算的度量衡**：`python benchmark/run.py` —— 21 类篡改 × 3 种观测模式，输出两个不同
的数字（接受率 / **未被设计解释的接受数**）。当前 open 9.5%（2/21，均为设计边界）、
pinned 4.8%（1/21）、head-pinned 0.0%，**三档未解释接受均为 0**。见 `benchmark/README.md`。

**500 例确定性语料（逐例可查）**：`benchmarks/corpus/mutation-corpus-500.json` 把同一批族
扩到 500 例，每例一行、带各模式裁决与被触发的检查 id。外人可一条命令复算并出具回执：

```bash
python tools/corpus_selfcheck.py --receipt my-receipt.md
```

目前 open 60/500（12.0%）、pinned 20/500（4.0%）、head-pinned 0/60（0.0%）；`open` 档被
接受的 60 例全部落在 rollback 与换钥两族——无锚点时按设计判不了的那两类。族清单由我们自己
选定、未经外部审过，因此这组数字不构成强度主张。见 `docs/MUTATION-CORPUS.md`。

| uibc 用词 | 上游用词（出处） | 关系 |
|---|---|---|
| 证据包 / package + manifest + 离线验证 | Package Digest（`draft-raskar-scitt-agent-provenance-00`）；AIVS bundle（`draft-stone-aivs-01`） | **同形态**。我们不加新格式，只在包上给出一个裁决 |
| 三值裁决 PASS / FAIL / INCONCLUSIVE | EP-AEC-02 五档 `admissible / missing_evidence / stale / conflicted / unverifiable` | **粗化投影**：我们的 INCONCLUSIVE 覆盖后四档中的"判不了"，不细分 |
| （不做）决策结果 | GAR-08 `governance_decision` = ALLOW / DENY / ESCALATE / SUSPEND | **正交两维**：GAR 给"放不放行"，我们给"验不验得清"。我们不输出决策 |
| `trust_level` = anchored / unanchored / unattested | 1F916 `witnessed`（独立见证人联署） | **子集**：`witnessed ⊃ anchored ⊃ unanchored`。我们没有见证人，故**永远不声称** witnessed |
| `checkpoint_head`（S8 / S9） | RFC 6962 STH；1F916 5 分钟 checkpoint | **同类不同强度**：我们是"生命周期 head + 证据根 + 索引元数据 + 条数"的单哈希，无 Merkle 树、无一致性证明 |
| 生命周期状态机（5 态） | 无直接对应 | 设备/agent 的生命周期状态；与 EP-AEC 的**证据分级**不是同一对象 |
| `principal_type`、`sequence_number`、`policy_hash` | noa-01 逐字枚举；GAR-08 `cap_profile_hash` | **逐字复用**，一字段同时满足两家 |
| 门禁 ALLOW / HOLD / DENY | APort(OAP) 的 pre-action authorization；COGITATOR 的 phantom entry | 同目的（执行前拦），我们的判据是"PASS + anchored 才放行" |

**明确不做**：不自建 `uibc://` URI scheme；不自造生命周期事件名（复用 GAR 的 ALE 六类）；
不复刻 OTel 命名空间（只加 `uibc.verdict` / `uibc.rule_id`）；不做单一评分。

规范标识：`SPEC_VERSION` 为字面常量，另给 `SPEC_ID = <version>@<12 hex>`（对本包全部模块
内容取 sha256），使"版本号相同、字节不同"无法冒充。`python -c "import uibc_core as u; print(u.spec_id())"`。


## 安装 · Install

```bash
pip install uibc-core
```

装好后：`uibc` 是命令行，`uibc-mcp` 是只读 MCP 服务器（stdio）。从源码跑见下方 Quickstart。

## 5 分钟 Quickstart

**30 秒先看效果（无需任何准备）：**

```bash
python -m uibc_core.cli demo   # 一键演示：建包→签封→验证 PASS→篡改→FAIL 捉获
```

```bash
pip install -e .

# 0. 生成封签密钥（可选，v0.2 推荐）
uibc keygen --out owner.key        # 密钥自己保管，绝不放进包里

# 1. 建包
uibc init demo.uibc

# 2. 注册 agent（有籍）
uibc register demo.uibc --agent-id my-agent-001 --owner alice

# 3. 生命周期事件（门禁状态机管理）
uibc event demo.uibc --type ACTIVATE

# 4. 附加证据（有证：自动记录 SHA-256）
uibc evidence demo.uibc --type ACTION --file report.txt --note "agent action log"

# 5. 封包 + 签署（计算 Evidence Root 并写 HMAC 封签）
uibc submit demo.uibc --key owner.key

# 6. 验证（门禁）：exit 0 = PASS
uibc verify demo.uibc --key owner.key   # 严格模式：伪造/换钥包在 S6 被拦
uibc verify demo.uibc                   # 开放模式：仅完整性检查
```

## 运行测试（外人复现三件套）

```bash
python -m unittest discover -s tests -p "test_*.py"   # 全量套件（实测输出形如 `Ran N tests in ~42s, OK (skipped=2)`，N 的确切值钉在 `docs/EVIDENCE-INDEX.md`，Linux / Python 3.12.11，已装 `.[verify,interop]`；未装该 extra 时为 `skipped=16`，逐步查清见 `docs/SKIPPED.md`；stress 7 场景单跑，见下条）
python -m unittest tests.stress_test        # 压力 7 场景
python independent_verifier/cross_check.py  # 独立第二实现交叉核验（70 项，0 分歧）
```

零第三方依赖，`pip install -e .` 可选（只为获得 `uibc` 短命令）。

## 验证什么（v0.3 检查项）

| 检查 | 内容 |
|------|------|
| S1 | 包结构完整（manifest / identity / lifecycle / evidence index） |
| S2 | identity 与 manifest 的 agent_id 一致 |
| S3 | 生命周期状态机（REGISTER 开头、previous_event 链、REVOKE/RETIRE 终态、非法转移报 lifecycle state violation） |
| S4 | 证据文件 SHA-256 逐一重算比对（**内容篡改**由 S4 逐文件哈希与 S5 Evidence Root 捕捉；S3 只管生命周期事件序列与转移合法性，**不检测内容篡改**；封签（S6）作用于 identity+manifest，也不覆盖证据内容） |
| S5 | Evidence Root 重算比对 manifest |
| S6 | **封签签名**：Ed25519 封签（v0.3 新增）在开放模式下即可公开核验——包里带公钥，任何人可验；HMAC 封签（v0.2）需 `--key` 严格模式核对；未签包 INCONCLUSIVE。判定语义（三值裁决）见 `docs/verdict-and-seal-semantics.md` |
| S17 | **线性回执链**（包内有 `evidence/chain.json` 时运行）：逐条重算前驱信封的 SHA-256(JCS)，与声明的 `previous_receipt_hash` 比对；首条必须是 64 个 0；改中间信封、丢首条、乱序、空链、无法规范化一律 FAIL |
| S18 | **策略制品解析**（包内有 `evidence/policies.json` 时运行）：每个 `sha256:<hex>` 必须与随包 JSON 制品的 SHA-256(JCS) 相符；回执声明的 `policy_digest` 若解析不到即 FAIL |

## 验证模式（v0.3）

| 模式 | 命令 | 语义 |
|------|------|------|
| 开放 | `uibc verify pkg` | Ed25519 已签包 → 公开核验 S6（PASS/FAIL）；HMAC 已签包 → S6 INCONCLUSIVE（对称封签无法公开核对）；未签包 → INCONCLUSIVE。**v0.3 起裁决为三值：任一检查 INCONCLUSIVE，则总结果封顶 INCONCLUSIVE，不再藏在 PASS 之下** |
| 严格 | `uibc verify pkg --key owner.key` | 业主持钥：HMAC 封签必须存在且有效，伪造与换钥在 S6 被拦 |
| 钉扎 | `uibc verify pkg --pubkey owner.pub` | Ed25519 公钥钉扎：封签记录的公钥须与钉扎值一致，换钥重签在 S6 被拦 |

仓库内 `examples/sample-package/` 是一个完整的已签样本包，外人零密钥即可验证（见 `examples/README.md`）。

## 报告纪律（总档案 §16/§17）

每份验证报告必须包含：`scope`（范围）、`limitations`（局限）、`checked`（查了什么）、`not_checked`（没查什么）。
明确不查：生命周期事件签名（封签只覆盖 identity+manifest）、外部时间戳锚定、行为评估、记忆忠实性/连续性。非对称/第三方签名已于 v0.3 落地（Ed25519，纯标准库实现，RFC 8032 向量锁定）。

## 已知边界（诚实清单）

- **HMAC 封签（v0.2 保留）为对称方案**：验证需持有密钥、无第三方可验证性、无不可否认性——这些缺口已由 v0.3 的 Ed25519 公开封签化解；HMAC 模式仅建议用于业主自验场景。注：v0.3 的 Ed25519 为纯 Python 实现（非恒定时间），大批量签名场景应替换为原生实现（接口不变）。
- **密钥单点失效（两种封签共有）**：私钥/种子一旦泄露或丢失，封签前提即崩塌，本版本无吊销/轮换机制。生产部署须将私钥纳入密钥管理（HSM / 分片 / 定期轮换）；吊销列表留待后续版本。
- **换钥攻击只能靠钉扎检测**：攻击者可用自己的密钥重新签署整个包——其封签对自己的公钥是有效的；只有验证者钉扎了真业主的公钥（`--pubkey`，或 HMAC 的 `--key`）才在 S6 被拦。故业主应把公钥发布在可被钉扎之处（仓库、注册表条目、论文附带）。常设动机案例见 fixtures/malicious-keyswap 与 `uibc demo` 第 7–8 步
- Evidence Root 算法为临时版（sorted hashes 的 SHA-256），待 canonical serialization 定稿后升级为 Merkle 树
- 时间戳未做外部锚定（生产用 OTS/Rekor，见行动计划）

## 生态组件（Ecosystem）

| 组件 | 位置 | 说明 |
|------|------|------|
| MCP server（只读） | `mcp_server/` | 7 个工具，stdio JSON-RPC |
| Registry 服务（只读） | `registry_server/` | 三大登记处 HTTP 查询；静态查询页 `registry/index.html` |
| A2A 适配器 | `adapters/a2a/` | JSON-RPC 2.0 over HTTP：`card` / `uibc/verify` / `uibc/gate` / `uibc/inspect` |
| 示范应用（完整生命周期） | `examples/showcase.py` | 一个 agent 的可验证生命周期；实录 `examples/SHOWCASE.md` |
| 失败语料 | `failure_corpus/` | 真实失败 F-001~F-006（根因/教训） |
| 赛事包 | `contest/` | 章程/赛题/评审/提交规范/内测实录 |
| AI 发现 | `llms.txt` + `ai/` | 机器可读入口 |
| Runtime hooks | `uibc_core/runtime.py` | 一行式 `record_action` / `seal` / `event` / `snapshot` |
| 英文文档 | `README.en.md` | English documentation |

## 对应规范

- 《LGD/UIBC 历史讨论总档案 v0.1.0》§9-§26
- 《UIBC 工程实现摘录 v0.1.0》
- SPEC 提案：`docs/SPEC-PROPOSAL-v0.1.md`（v0.2 增补见文末）

## Golden Fixtures (archive SS30)

Benchmark as executable evidence — eight mutation categories, each a runnable,
owner-signed submission.uibc package:

```text
fixtures/              open 模式        strict(--key) 模式   变异
├── clean.uibc         PASS (S6 不定)   PASS (S6 PASS)    基线
├── tampered.uibc      FAIL (S4)        FAIL (S4)         证据内容改写
├── deleted.uibc       FAIL (S4)        FAIL (S4)         证据文件删除
├── duplicated.uibc    FAIL (S5)        FAIL (S5)         索引条目重复
├── reordered.uibc     FAIL (S3)        FAIL (S3)         生命周期换序
├── migrated.uibc      FAIL (S5)        FAIL (S5)         部分迁移未重封
├── malicious.uibc     PASS (S6 不定)   FAIL (S6)         全自洽伪造——v0.1 盲区，
│                                                          v0.2 严格模式已拦截
└── malicious-keyswap  PASS (S6 不定)   FAIL (S6)         换钥重签——仅业主密钥
                                                          可检（v0.3 动机案例）
```

**封印的作用域是 `identity+manifest`，不含证据内容。** 所以改写/删除/换序证据
**不会**让签名失效——上面前五行的 strict 结果只有 S4/S5/S3，S6 仍是 PASS，检测
来自那些检查而非签名；只有动了 manifest 的伪造（`malicious`）才会破坏封印。
请把 `S6=PASS` 读作"封印未被扰动"，**不能**读作"内容为真"。

Regenerate + re-verify: `python fixtures/generate_fixtures.py` (writes
`fixtures/EXPECTED.md` with expected-vs-observed per archive SS31 fields,
both modes + attacker-key column).

两个 fixtures 生成器都**带门禁**：实测结果与手工推导的期望矩阵逐格机器比对，
任何偏差即以非零码退出。散文写的 Expected 列永远"不会失败"，矩阵才会——
上面那句 `S4+S6` 的错述，正是靠着这道门禁才被发现。

## Reproduce the published numbers in one command

If you do not want to take our arithmetic on trust, there is one command that re-derives it
locally, without needing the network, and with no account:

```
python tools/reproduce_gate.py --repo . --uibc <path-to-uibc[.exe]> \
       --profile docs/assurance/far-profile.json --out receipts
```

It does five things and prints one receipt. What the receipt claims about the network —
and the four things it deliberately does not claim — is stated separately in
[`docs/assurance/NETWORK-SCOPE.md`](docs/assurance/NETWORK-SCOPE.md).

| step | what it re-derives |
|---|---|
| environment | python, uibc version (read from `pyproject.toml`, with the source stated), git HEAD (three-level fallback; `UNAVAILABLE` if it truly cannot tell), whether any probe target answered (information, never a failure), and the number of outbound connection attempts **the driver process made** during the run |
| fixture matrix | **8 packages × 3 pinning conventions = 24 comparisons**, each against `fixtures-v041/RESULTS.json`, comparing the whole non-PASS set and not just PASS/FAIL |
| corpus | regenerates the 500-case corpus and compares row hashes |
| vectors | `tools/conformance_vectors.py --check` |
| denominators | re-adds every published per-family count and every mode's accepted count against the corpus file, including the `0/60` head-pinned denominator that must never be quoted as `0/500` |
| convention axis | rebuilds artifacts sealed under a superseded scheme (which a current verifier genuinely cannot judge), then reports the same case set under `strict` / `lenient` / `excluded` — the 500-case corpus has no such verdicts, so on it all three readings return 12.0% and the axis would otherwise look flat |

Exit code is 0 only if every comparison matches; a single disagreement prints expected vs
observed and exits non-zero. The tool never repairs its own inputs — a reproduction script that
can pass by adjusting what it compares reproduces nothing.

The receipt states, in its own text, that it is **self-issued**: running it proves the numbers
reproduce on that machine, not that an independent party checked them. To get from "reproduces"
to "checked by someone else", see `REPRODUCTION-REGISTER.md` — the rows there are written by the
people who ran it, and disagreements stay in the file.

Timing on a laptop: ~30 s (21 s of that is the corpus hashing). If it ever takes much longer,
the corpus or the fixtures have grown and the README claim is stale.

## Memory Migration Fixtures (UIBC-MEM)



`python fixtures/generate_memory_fixtures.py` —— 22 个具名威胁，打的是可验证
记忆迁移（M0 输入结构 / M1 条目完整 + 四项 Preservation）：重复、注入、换 id、
丢失、畸形输入、真空输入、换序、已记录边界、594 条规模。输出
`fixtures/MEMORY_EXPECTED.md`，同样门禁。

其中三个 case 是**回归锁**，锁住这套语料挖出的真实缺陷（两者原本都是静默通过）：
往 target 塞一个与真条目同 `memory_id` 的假条目（被 dict 折叠吞掉，报告却写
"no injections"），以及空到空的迁移在四项 Preservation 上全拿 PASS。

## Permanent Archive / 永久存档

[![Software Heritage](https://archive.softwareheritage.org/badge/origin/save/https://github.com/zhaoxinghua09-cell/uibc-core/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https%3A%2F%2Fgithub.com%2Fzhaoxinghua09-cell%2Fuibc-core%2F)

- **Software Heritage Visit ID**: `2559486` — 本仓已由 Software Heritage 永久存档（不可篡改证据），为该生态资产的长期可引用性提供基础设施级保证。
