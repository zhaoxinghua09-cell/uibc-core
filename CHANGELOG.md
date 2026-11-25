## 未发布 — 2026-11-25（DID 对接：BID 协议层，按《星火·链网BID协议》正文实现）

主题：上一版把 `did:bid` 的通路做通了（GET + errorCode + id 校验），但没有读懂回来的文档。读完协议正文后发现三处真缺口，这一版补齐，且每一处都对着条款写测试。

- **§4.2.5 的 11 档响应码不再被压成一个异常**（`uibc_core/bid_protocol.py::BID_RESPONSE_CODES`）：协议给了 0–10 共 11 个码，旧实现把非 0 一律抛成同一句话，于是"没找到"（6，重试无益）和"服务器繁忙"（3，重试有效）在日志里长得一模一样，而"验签失败"（9）这个安全信号也被混进了传输错误。现在每个码带协议原文名字和一个处理类（ok/refused/protocol/transient/security/not_found），`retryable` 与 `not_found` 是可问的属性；未记载的码也保留数字，不假装认识。
- **BID 文档不是 DID Core 文档，这一版把文档读懂**（`parse_bid_document`）：协议 §4.2.1 的文档带 `publicKey[]`（`publicKeyHex`/`controller`/`type`）、`authentication`、`alsoKnownAs{type:Int}`、`extension`（ttl/type/attributes/encrypt/acsns/verifiableCredentials）、`service`、`proof{creator,signatureValue}`。逐条校验：id 必须等于请求的 BID；`publicKey.id` 文档内唯一且必须带 `#`；`controller` 必须是 BID；`publicKeyHex` 必须是十六进制；`authentication` 不能引用未定义的键；`alsoKnownAs.type` 必须是 Int；`DIDSubResolver` 必须有 `serviceEndpoint` 且 `protocol ∈ 0..3`（附录一第 5 张表）；`ttl` 非负整数；`attribute.encrypt ∈ {0,1}`；时间戳必须是 ISO-8601；`proof.creator` 必须是本文档的键。附录一点名的码值之外的值只记 `warnings` 不拒收——附录自己写着"待扩展"。
- **`to_did_core()` 单向投影**：DID Core 侧只认 `verificationMethod`/`authentication`/`service`/`alsoKnownAs`，而 BID 侧是 `publicKey`/`extension` 等；投影时 BID 自有字段全部保留在 `extension` 里，丢掉信息不如不投影。
- **§5 签名真的能跑了**（`sign_bid_document` / `verify_bid_document`）：去 `proof` → 按 RFC 8785/JCS 规范化 → 签名 → Base58。JCS 用的就是仓里已有的 `canonical.canonicalize`（它已与 JS 实现逐字节对齐），所以第三方拿任意 JCS 工具就能重算待签字节；补了 Bitcoin 字母表 Base58（含前导零字节）。Ed25519 闭环自签自验；`proof.creator` 必须同时出现在 `authentication` 里，否则拒绝。SM2 **不做**：没有可独立复算的向量，宁可在文档里写明"此处不可验证"也不假装验过。
- **§4.2.3 子链递归解析**（`resolve_bid_chain`）：主链文档里 `service.type=DIDSubResolver` 指向子链解析地址 → 再解析。带跳数预算和已访问端点集合，环会给 `cycle` 而不是转圈；端点必须是 HTTP(S)。
- **§4.3 二进制解析明确拒绝**（`refuse_binary_resolution`）：用协议自己的 5（operation not supported），不猜格式。
- **`did_cn.resolve()` 的 bid 分支改用同一套信封解析**：错误信息不再坍缩，仍以 `DIDCNError` 抛出以兼容既有调用方；需要码与可重试性的调用方用 `bid_protocol.resolve_bid`。
- 测试 `tests/test_bid_protocol.py` 37 条，每条在名字里写明它钉的是哪一条款（§4.2.1 / §4.2.5 / §5 / 附录一 / §4.2.3）。
- **跨实现核验（这是本轮最该被外人复查的一条）**：签名不是我们自己验自己。`tools/verify-js/bid.mjs` 用**另一套 RFC 8785 实现**（JS 里按 RFC 原文重写，未复用 Python 代码）规范化、用 **node/OpenSSL** 验 Ed25519，对 `fixtures/bid/signed_document.json` 给出 `signature-verified true`，并打印规范化字节的 sha256 与 Python 逐字符比对。两次实现算出同一个 sha256，才叫"第三方能重算"。夹具由 `tools/make_bid_fixture.py` 以固定种子生成（随机种子会让已提交的夹具无法复现，等于把可证伪性换成了一次性快照）。测试 `tests/test_bid_crossjs.py` 4 条：夹具仍能自验、node 能验、两侧 sha256 相同、改一个字段 node 必须拒。
- 证据：`uibc_core/bid_protocol.py`、`tests/test_bid_protocol.py`、`tests/test_bid_crossjs.py`、`tools/verify-js/bid.mjs`

## 0.5.3 — 2026-11-25（一致性语料 36→58，第二实现对齐）

- **语料 36 → 58 条**：新增 `tools/redteam_scale.py`（22 条 scale 组变体）与 14 条补充变体（第二文件翻转/截断、第二条非法日期、第二条哈希截断、proof 索引偏移、截断 proof、清零 back-link、倒序 receipts）。期望值全部由实测 `failed_checks` 导出，不手填。
- **6 条如实跳过**：`no check fired; not exportable as a vector`（未知 status、索引倒序、删 seal、砍 seal 签名、schema 拼错、媒体类型换标）。`tests/test_conformance.py` 由「skipped 必须为空」改为「每条 skipped 必须带规定 reason」——把静默跳过，而不是跳过，定义为缺陷。
- **第二实现对齐 58/58**：`tools/verify-js/verify.mjs` 补「两条记录共用同一 evidence_id」与「逐条 created_at 存在但非法（`2026-11-31`）」两项检测；把两边检查编号不一致的 8 条按「一个缺陷一个编号」重划（S4 字节完整性 / S7 索引元数据 / S12 标识与日期 / S3 生命周期语义）。`python tools/assert_second_impl.py` → 58/58、18 检查、0 out of scope。
- **覆盖 16/19**：S9 / S16 / S19 无直接用例，`conformance/coverage.json` 如实标注。
- **发布资产**：`uibc-conformance-0.5.3.zip`，312,642 字节，sha256 `5f3a72cb277dac8f285cd50df304dd9befe762caf42f40b98b907bcfc20cce8c`；归档 = oracle（`SOURCE_DATE_EPOCH=1794700800` 重 emit）= MANIFEST（790 文件）= pin 四者同源。
- **两处发布事故，如实记录**：`v0.5.1` 因先建非 draft release 再上传资产被 immutable 拒绝，删除重建又把 tag 名永久占用；`v0.5.2` 资产可下载，但 oracle 语料仍带旧版本串，不是本树语料。详见 `docs/KNOWN-LIMITS.md` 第 11–12 条。
- **已知脱链**：`v0.5.3` 的 tag 指向 rebase 合入前的提交 `b60a2a00`，不在 `main` 祖先链；immutable release 使 tag 无法移动（422）。字节证明不受影响，但「tag 指向 main 某提交」这句话不成立。
## 未发布 — 2026-11-25（DID 对接：补 did:peer）

- **`did:peer` numalgo 0/2 支持，全离线**：文档由标识本身推导，不需要端点也不需要注册中心。`0z<multibase ed25519>` 与同键 `did:key` 的文档键材料一致（规范明说二者等价）；`2` 解析 `.A/.E/.V/.I/.D` 键元素与 `.S<base64url>` 服务元素，按规范把 `t/s/r/a`、`dm` 还原成全称。
- **numalgo 1/3/4 报 `UNRESOLVED` 而不是 `INVALID`**：它们的文档不在标识里（1 是创世文档的哈希、3 是 numalgo-2 DID 的哈希、4 短形态是长形态的哈希），需要对方提供。新增 `NotSelfResolving` 异常，适配器单独接住——这是同一类"错误信息坍缩"的第三例（前两例是 RegistryEndpointRequired 与线上 did:cn 形态）。
- 明确不声明 `keyAgreement`：从 Ed25519 公钥推 X25519 需要双有理映射，本实现没做，宁可不给也不给一个看起来对的错键。
- 测试 `tests/test_did_peer.py` 24 条，向量取自 Peer DID 方法规范原文样例。

## 未发布 — 2026-11-24（DID 对接：补 did:jwk / did:bid + 修线上 did:cn 误判）

主题：把"身份无关"从口号变成能点名的清单。两件事，一件加能力，一件修错误结论。

- **新增 `did:jwk`**（`uibc_core/did.py::did_jwk_document`）：离线解析（文档就是标识）。两条硬拒绝：JWK 里出现 `d/p/q/dp/dq/qi/oth/k` 一律拒绝（DID 是公开标识，解析器不该替人搬运私钥）；JWK 超过 4096 字节拒绝（不让一条长字符串把本地解码变成无界工作量）。ed25519 → `VERIFIED`，其它键型 → `INCONCLUSIVE`。测试 `tests/test_did_jwk.py` 15 条
- **修 `did:cn` 线上形态被误判为 `INVALID`**：信通院线上平台发的 `did:cn:agent:<base58>` 不在已发布 ABNF 内，`validate()` 拒绝是对的，但适配器把这次拒绝说成了"标识写错了"——等于告诉一个分配正确的智能体它的标识非法。现改为 `UNRESOLVED` 并保留标签（形态可识别 ≠ 分配已确认），回归测试钉住。这是本仓第二次"错误信息坍缩"（第一次是 `RegistryEndpointRequired`）
- **新增 `did:bid`**（`uibc_core/did_cn.py::_check_bid`）：星火·链网 BID，ABNF 两种形状——主链 `ef<base58>`（首字符加密算法、次字符编码算法，按规范两张表读出）与子链 `AC01:<suffix>`；`did:bid:byol` 作为规范明列的例外单独识别，不硬塞进正则。`read` 走 HTTP GET，`errorCode` 非 0 直接抛出，端点必须调用方给（不默认 URL）。测试 `tests/test_did_bid.py` 14 条
- **记下一处规范间冲突**：BID 的 ABNF 允许 `acsn ":" 0*1(suffix)` 的空后缀形态（如 `did:bid:AC01:`），但 DID Core 的 `method-specific-id` 必须以 idchar 结尾；两者不能同时满足。我们按 DID Core 拒绝，冲突写在测试与 `docs/DID-LANDSCAPE.md` §4，不装作看不见
- 新增 `docs/DID-LANDSCAPE.md`：DID 对接全景（9 种已接、主流方法矩阵、三档策略、与 Universal Resolver 的差距口径）
- `docs/EVIDENCE-INDEX.md` 由生成器重算（静态用例数 1557），口径改为"静态计数 ≠ 运行期收集数（参数化会更多、平台跳过会更少）"；`check_doc_facts` 0 mismatch
- 证据：`tests/test_did_jwk.py`、`tests/test_identity_adapter.py`、`docs/DID-LANDSCAPE.md`
## The suite count, counted where it cannot drift

- `docs/EVIDENCE-INDEX.md` carries one published number, and the tool that generates it (`suite_size()` in `tools/build_evidence_index.py`) asked `unittest` discovery how many cases the suite has. That number depends on **where** you run it: the same commit counts **1157 on Linux and 1156 on Windows**, because discovery imports modules and platform-gated imports differ. So the page was guaranteed to be stale on one platform, and `test_the_doc_in_the_repo_matches_a_fresh_build`, `check_says_what_it_means` and `test_index_number_matches_what_is_measured` failed there. This was found the honest way — `uibc-bench` D1 ("outsider runs the whole suite") failed on a clean Linux clone of main.
- Fix: `tools/suite_count.py` counts `def test_*` (AST, including async) under `tests/`, importing nothing. `build_evidence_index.suite_size()` and `check_doc_facts.measure()` both call it. Same commit → same number on every platform and in every checkout: **1510** on Linux and on Windows, verified 2026-11-24.
- The published line now says what it counts: static `def test_*` count, cross-platform, runtime discovery is slightly lower because of platform skips. Anything else still cites the page rather than retyping a number.
- Note for the record: the previous 1156 had also gone stale against a later commit on its own platform (PR #423 added `tests/test_interop_*`), which is the same defect with a different cause — a single typed digit that nothing re-derives.
- No version bump, same reason as above: the number is bound to a built archive.
## Ten documents, two orderings, measured

- Read all ten ACPs documents (`acps-specs/01`…`10`, each **v02.02**): `docs/ACPS-SPEC-MAP.md` maps what each is, how many times it names AIC, and which ones actually consume the code — ATR (certificate `CN`/`URI:acps://{AIC}`), AIA (mTLS peer check), ADP (`forwardChain`, loop detection), AAC (`agent:{aic}` subject IDs), AMP (logs, `kid` needed because AIC alone cannot pick a key).
- **Contradiction found and measured**: `ACPs-spec-AIC` §3 puts the version arc at position 5; `ACPs-spec-overview` §5.2 puts it at position 9; `ACPs-spec-ATR` §3.1 follows the overview in words. Nine distinct ten-arc samples exist across the corpus; seven carry a checksum that recomputes under salt `0x1234`, and the two that do not are AIP's `…0JU1` / `…0JU2` — `0JU4` with the last character bumped, i.e. placeholders.
- Consequence, stated rather than papered over: **the checksum is order-agnostic** (it hashes arcs 1-9 as text), so both orderings produce codes that verify. The defect is field naming, and it matters downstream (AAC subjects, ADP chains, ATR certificate matching) even though integrity is unaffected. We follow AIC §3, `scope` says so, and there is no invented crosswalk.
- Four new tests pin the corpus measurements, including "both orderings verify" and "AIP's two trailers are placeholders". Conformance file: 21; cross-implementation: 17; with the reader tests, 56 passed across the three files.
- Access recorded: `git clone --depth 1` works (1,937 files); the `contents` API rate-limits (429); `git/tree` returns zero entries. A Windows checkout differs from the API copy by CRLF only (8,149 vs 8,043 bytes, same `sha256:38242a01…23ab` after normalising).
- **No version bump.** `pyproject.toml` stays 0.5.0: this repository's release chain is pinned by `anchors/pins/uibc-conformance-0.5.0.sha256`, a hash of a *built* archive, and `STATUS.md` plus the README digest quote that pin. Bumping the number without building and publishing a new archive broke `test_pin_resolvability`, `test_outward_receipt` and `test_status_page` — measured on a clean Linux tarball: 16 failed at 0.5.2, 49 passed at 0.5.0 across the same seven files. Everything here is recorded as unreleased until an archive exists.

## The AIC text itself, and a checksum we can now decide

- Found the document, not just a crate's copy of it: `ACPs-spec-AIC-v02.02` at `aip-pub/ACPs-community`, path `acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md`. Copy pinned by `sha256:38242a01…23ab` in `docs/ACPS-SPEC-IN-HAND.md`. The earlier "the ACPs repositories are empty" reading came from the `git/tree` endpoint; `contents` returns the tree.
- `uibc_core/acps_identity_code.py`: spec references corrected v02.01 → v02.02; new `verify_acps_code(code, salt)` recomputes arc 10 (CRC-16/CCITT-FALSE over arcs 1-9 ++ salt, Base36 four chars) and returns `VERIFIED` / `INVALID` / `INCONCLUSIVE`. `VERIFIED` carries an evidence entry whose digest is the sha256 of the exact bytes hashed. Without a salt the answer is still "checksum NOT checked", never a guess.
- The document's own worked example passes byte for byte: `salt 0x12 0x34` → `crc 0x646C` → arc 10 `0JU4` on `1.2.156.3088.1.1.34C2.478BDF.3GF546`; `0xFFFF → 1EKF` matches the range the text states for arc 10.
- Third implementation as oracle: `aipub-protocols` 0.0.3 (crates.io, lib `protocols`) compiled unpatched on a Linux VM (cargo 1.100.0, 2026-11-24) and asked for checksums over 16 boundary cases (lowercase, salts 2→16 bytes, both ends of each segment range, ontology form, foreign prefixes). 16/16 agree; the answers are pinned in `tests/test_acps_cross_implementation.py` so they keep agreeing or fail loudly.
- Tests: `tests/test_acps_spec_conformance.py` (21, built only from the text's example, its stated range, deliberate mutations and the other documents' samples) + the cross-implementation file (17). Together with the existing reader tests: 56 passed across the three files.
- **No version bump**, and `CITATION.cff` stays 0.4.2 on purpose: it pins the Zenodo archive, not the working tree. `pyproject.toml` 0.5.0 → 0.5.1 was tried and reverted for the same reason as above — the number is bound to a built archive, not to a code change.

## Anchor: a frozen root, four calendar receipts, no Bitcoin attestation yet

- `docs/anchors/ROOT-28a23ff.txt` and `.ots`: the claims are frozen against commit `28a23ff` (tree `d4656d1`), `sha256(ROOT) = 20c8d31b07bd…bf72`, submitted 2026-11-24 18:30 +08:00 to four OpenTimestamps calendars.
- `ots upgrade` answers `Pending confirmation in Bitcoin blockchain` on all four. So the proof establishes "existed no later than submission, witnessed by four calendars", and **not** "attested on Bitcoin".
- RFC 3161 came back empty: `freetsa.org/tsr` 404, `timestamp.digicert.com` 400 (http) / timeout (https), `timestamp.sectigo.com` 404. The registry keeps `RFC3161 = rejection`; the row is not deleted.
- `docs/ANCHOR.md` states both, and why the root also lives in the repository (GitHub as a second, weaker witness).
## Measured numbers now have to name the commit they came from

- `tests/test_measured_facts_are_pinned.py`: any doc quoting a measured constant (file count, executed test count, tarball size) must also name a commit, or the suite fails.
- Reason, stated in the test itself: `check_doc_facts.py` can recompute everything derived from the tree, but "1,865 files" and "1471 passed" are properties of one commit on one machine. They go stale when `main` moves, and a stale number with no date is how a document starts lying without anyone editing it.
- `docs/REPRODUCTION.md` now declares **Commit under test: `8a41372`**; `docs/COMPETITIVE-LANDSCAPE.md` pins its two counts to the same commit.
- Two new tests; index rebuilt on this branch.
## The other document: the ten-arc code, read on its own terms

- `uibc_core/acps_identity_code.py`: a reader for `ACPs-spec-AIC-v02.01` — ten arcs, per-arc Base36 and length rules, prefix noted rather than pinned.
- **The checksum is never judged.** The salt is per-ARSP and unpublished; a code with a deliberately wrong trailer returns `INCONCLUSIVE`, and `scope` says so. A salt-holder's check would be strictly stronger, and the document says that instead of hiding it.
- Each reader refuses the other document's shape with an explicit reason instead of coercing it; `detect_profile()` labels which one a string belongs to. There is no crosswalk, because neither text contains one.
- `docs/TWO-DOCUMENTS-ONE-CODE.md` puts the two texts side by side and states the consequence: "supports the national agent identity code" is ambiguous until the document is named.
- 18 new tests. EVIDENCE-INDEX rebuilt on this branch; `paper/paper.md` module count updated 35 → 36.
## The third-party implementation, executed in both directions

- `docs/THIRD-PARTY-DIVERGENCE.md`: `aipmc-basic` 0.0.2 fetched from crates.io, built unmodified, and run against our parser — and our parser run against its examples.
- Result: the two families **reject each other**. Its ten-arc form (declared alignment: `ACPs-spec-AIC-v02.01`) fails our parser with profile `aip-acps`; a GB/Z 185.2-shaped eight-arc code fails its `parse`.
- Correction to `docs/COMPETITIVE-LANDSCAPE.md`: "deviates from the standard" was the wrong frame. It implements **a different document**, which makes this an interoperability question for the authors of both.
- Two findings recorded rather than assumed: its `parse` does not verify the checksum (a deliberately wrong CRC still constructs, against its docs' "构造即校验"), and its spec example fails under the published default salt — which is how the private salt becomes visible.
## From one public URL to a green suite, on a machine we did not author on

- `docs/REPRODUCTION.md`: public tarball → fresh venv → `check_doc_facts.py` → `pytest` → `probe_reference_repos.py`, with the exact commands and the observed numbers.
- Observed 2026-11-24 on a Linux host: tarball 200 / 2,568,257 bytes / 1,865 files; `check_doc_facts.py` → 0 mismatch; `pytest` → **1471 passed, 33 skipped, 105 subtests passed** in 426.73 s.
- Two counts are stated side by side because they differ and both are real: 1,173 test functions in the evidence index, 1,471 executed after parametrisation.
- Row 6 stays **partial**: this removes "only works on the author's machine", not "the author is judging the author". 33 skips are a skip, not a pass.
## What the reference implementation lets an anonymous reader see

- `tools/probe_reference_repos.py`: no account, no token, one API call per repo, prints what each default branch actually contains.
- Result 2026-11-24: `ACPs-community` main → **0 files**; the other eight repositories → **README.md only**. The 16.45 K downloads on the landing page are not inspection.
- Consequence recorded in `docs/COMPETITIVE-LANDSCAPE.md`: we may say we **read** its version history and protocol names, and we may not say we cross-checked against its code.
- The same question put to this repository returns **1,865 files** anonymously, tarball 200 without a token. That contrast is the one place on this track where "ahead" means "inspectable", and it is measured rather than asserted.
## The competitive table, with the rows we lose

- `docs/COMPETITIVE-LANDSCAPE.md`: three tracks, every row carrying 标准 / 规范 / 实测 / 读码 as its basis.
- Corrections it forces on us: the reference implementation is at **v2.2.0** (2026-08-31), not the v2.1.0 of the July release; it adopted the OID form in v2.0.0; and **AAC shipped in v2.2.0**, so it is not a concept we can claim to have introduced.
- It also records that the reference repo's `main` currently returns an empty tree, so our cross-check is against its published changelog rather than its code — a partial, not a pass.
- Eight "what best means" criteria scored: five pass, two partial, one zero. The zero is independent evaluation by a separate identity, and it stays zero until someone else does it.
## The did:cn namespace the platform serves is not the one the README publishes

- Measured on `agent.idfactory.cn`: every registered agent reads
  `did:cn:agent:<base58>`, while the CN DID Method Specification fixes
  `2DIGIT.3*5DIGIT.1*128DIGIT`. Until now our adapter refused **all** of them —
  correct against the published ABNF, useless against the live namespace.
- `validate()` is unchanged and still refuses the live form: loosening it would
  mean the adapter no longer checks the document it claims to check.
- `validate_live_agent_id()` is new: it recognises `did:cn:agent:<22-44 base58>`,
  labels itself `published_abnf: False`, and states that shape proves nothing
  about allocation. Two entry points, two labels, no silent merge.
- `docs/TWO-CODES-DIFF.md` puts the two codes side by side across ten
  dimensions, each row citing 标准 / 规范 / 实测. Three divergences are now
  written down instead of inferred: the live namespace has no published ABNF;
  `service` lives in the DID Document for `did:cn` but has no document at all
  for the national code; and **neither track can answer "after revocation, is a
  previously issued credential still valid"**.
- 10 new tests.
## Agent identity code: we read the shape, and stop there

- `uibc_core/agent_identity_code.py` parses `GB/Z 185.2—2026` identity codes
  (the national OID scheme, prefix `1.2.156.3088`) strictly by the published
  clauses: five dot-separated parts over a four-arc prefix, version `1` of a
  35-value range, provider and requester of 1–6 characters, sequence bounded at
  19 (9 ontology + 10 instance, **derived and labelled as derived**).
- **The ceiling is `INCONCLUSIVE`, by construction.** `_verdict()` has one
  return value and no branch that produces `VERIFIED`: allocation belongs to a
  registration service provider, and the standard defines no resolution
  endpoint. A shape check that returned `VERIFIED` would be reporting "this
  identity is real" on the strength of "this string is shaped correctly".
- A reserved version is `UNSUPPORTED`, not `INVALID` — first real use of the
  seven-state vocabulary on a national standard: *not implemented is not wrong*.
- Found and documented a **third-party reading that adds two levels and a
  checksum**: `aipmc-basic` (MIT, crates.io) reads ten arcs, separating ontology
  and instance serials and appending a four-character Base36
  CRC-16/CCITT-FALSE with a non-public salt. None of that is in the standard as
  published, and we cannot recompute the checksum, so `detect_profile()` names
  the profile and `parse_agent_code()` refuses it *with the reason attached*.
  We do not silently accept a private convention, and we do not pretend to
  verify it.
- `duplicates()` exposes management requirement 6(d) (one code, one agent) as a
  report rather than a decision.
- 27 new tests; `docs/AGENT-IDENTITY-CODE.md` states the boundaries and the
  remaining gaps (no issuer, no resolver, AIP reference implementation not yet
  compared); module count 34 → 35 and the evidence index rebuilt.
### Where coverage stops, and why

- `docs/COMPETITIVE-COVERAGE-AAC.md` gains a table of the classes we probed and
  deliberately did **not** run: `standard-history-v0` (69 cases counting rules —
  reproducing them means copying their spec, so it would not be an independent
  check), CBOR classes (no decoder here), MMR classes (different hash family),
  COSE classes (no library), and the registry/text layers.
- Stated conclusion: **2 of 40 is the ceiling for standard-library-only
  recomputation, not laziness.** Running all 40 would first require
  implementing MMR, COSE and CBOR — the numbers would then no longer be
  independent.

### A second class of their vectors, and it agreed the first time

- `tools/crosscheck_aac_history_frame.py` reproduces the `table_binding` /
  `pack_binding` verdicts of `vectors/history-frame-v0`:
  `properties: 22  disagreements: 0` → `OUR JCS REPRODUCES THEIR BINDING VERDICTS`.
- No fix was needed here: our RFC 8785 form over the JSON values they ship
  yields exactly the digests they list, and the five negative cases
  (`pack-digest-mismatch`, `table-digest-mismatch`, `pack-for-another-instance`,
  `pack-translated-in-place`, `pack-carries-checked-string`) disagree as intended.
- Scope stated plainly: this tests **binding** (the digest names the right
  document), not their counting rules.
- `docs/COMPETITIVE-COVERAGE-AAC.md` now counts **2 of 40** classes (5%):
  `json-nesting` (which found a limit we lacked) and `history-frame-v0`
  (which agreed on first run). Both numbers are kept.
- 6 new tests.

### One of their forty vector classes, and the limit we did not have

- `tools/crosscheck_aac_json_nesting.py` runs the `json-nesting` cases from
  `action-state-group/agent-action-capsule` against our reader and JCS.
- First run: `cases: 9  mismatches: 4` — the four 129-deep negatives were all
  accepted. Their spec states a **128-level** JSON nesting limit shared by four
  languages (interop-profile-v1 §5.2, draft Conventions); we had no such limit.
- Fix: `canonical.MAX_NESTING_DEPTH = 128`, `nesting_depth()`,
  `check_nesting()`, called at the head of `canonicalize()`. Re-run:
  `cases: 9  mismatches: 0` → `WE MATCH THEIR NESTING CONTRACT`.
- `docs/COMPETITIVE-COVERAGE-AAC.md` maps all 40 vector directories: exactly
  **1** (2.5%) is computable with the standard library alone; the other 39 need
  MMR, COSE, ed25519, or are registry/text layers — a different stack, so a
  numeric comparison there would be misleading.
- The added limit changed the diagnostics in `conformance`, so
  `docs/THESIS-CH5-TABLES.md` was regenerated by `tools/build_thesis_tables.py`
  (table 5-4: `0 / 0` → `4 / 14`, theirs `4 / 5`). The numbers are computed, not
  hand-edited.
- 8 new tests.

### We ran their vectors, and wrote down the first run that failed

- `tools/crosscheck_scitt_cose_vectors.py` folds the inclusion paths in the
  `scitt-cose` set published by `ietf-wg-scitt/examples` using only
  `uibc_core.merkle`; no COSE library is needed to check a path.
- First run: **all five vectors disagreed** — because we read `leaf_entry` as a
  leaf hash, when it is the leaf *input* digest (RFC 9162: `H(0x00 || leaf_input)`).
  That was our error; corrected run: `vectors: 5  mismatches: 0`.
- Outcomes: `valid-eddsa` and `valid-es256` fold onto their stated roots;
  `fail-tampered-path` folds away as it must; the signature and VDS negatives
  are reported but not adjudicated here, since those failures live outside the
  tree layer.
- `docs/external-review/CROSSCHECK-SCITT-COSE.md` states plainly what this is
  not: not an audit of `scitt-cose`, not a claim of verifier agreement, and not
  a place in anyone's record — their `INTEROP.md` still does not list us.
- 5 new tests, including a note test that fails if the "not an audit" sentence
  or the failed-first-run record is removed.

### The upstream submission is now a package, not a plan

- `tools/build_scitt_vector_package.py` builds and self-verifies a
  SCITT-shaped vector set at `docs/upstream-package/scitt-rfc9162`: five
  vectors (two `VALID`, three named failures) covering the **RFC 9162 SHA-256
  tree and inclusion-path layer only**. Each `expected.json` carries
  `root_true` and a **computed** `reconstructed_root`, so positives must match
  and negatives must differ without any code from this repository.
- Shape copied from the vector set the IETF SCITT WG `examples` repository
  already merged: `v1/<id>/expected.json`, `manifest.json`, `SHA256SUMS`,
  `.gitattributes` pinning files as non-normalized. `sha256sum -c` gives 6/6.
- `docs/UPSTREAM-PR-CHECKLIST.md` closes the three pre-submission checks that
  were open: format (verified against upstream HEAD `727ee03`, verbatim
  quotation of their "a mismatch … is exactly the report the authors want"),
  licensing (both Apache-2.0, SPDX per-directory), and **the one check nobody
  can do for the author** — IETF Note Well / IPR consent, which needs the
  author's own account.
- What the package does not cover is in its README, not an appendix: no
  COSE_Sign1 bytes (no COSE library here), no log receipts, no witness
  cosignatures, no TSA. It is narrower than `scitt-cose` and is not a
  replacement for it.
- Submission status: **not sent.** Opening the PR is an outbound action.

### The external-record gap is an order of magnitude, not a tie

- `docs/LANDSCAPE-2026-11.md` §8: the other draft's `INTEROP.md` lists **nine
  independent parties**, each `ran & verified` with a linked public record
  (EMILIA, Songbo Bu, Tyche, Microsoft/CCF, NANDA/MIT, GlyphZero, APS,
  A2A boundary-seal, GAR/SOOS). This repository has one, and it wrote that
  record itself. `INTEROP.md` does not mention us.
- Their registry states the rule worth copying: *"A name is not evidence;
  a digest is."*
- The only way to close it is to have someone else write us into their record,
  which is an outbound action and is not taken here.
- `tests/test_landscape_corrections.py` (+3): fails if that 9-vs-1 line, or the
  "we are not in their record" line, is edited away, and if any line outside a
  disclaimer claims the gap is closed.

### Two claims about the competition were wrong

- `docs/LANDSCAPE-2026-11.md` §7: an author of another draft states that
  **"an independent party has run the full vector suite … and reproduced 32/32"**
  (SCITT list, 2026-07-14). "Third-party execution" is therefore **not** this
  repository's exclusive property, and the comparison that implied it has
  been retired.
- The same section records that Agent Passport System holds a public
  **OpenChain Community of Conformance** record (2026-07-17), so "no external
  organisation has published anything about it" was also wrong. The precise
  statement is: no organisation has *adopted the protocol*; an organisation
  *published a conformance record* about it.
- What still holds: their independent runs pass in full (32/32, zero
  divergence across implementations); ours produced **two disagreements** on
  a foreign host, and those two rows are now a check that fails if they
  return.
- `tests/test_landscape_corrections.py` (4) fails if either correction is
  edited out, or if the retired comparison reappears outside a line that
  says it is wrong.

# Changelog

All notable changes to `uibc-core` are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one project-specific rule: **any change to what produces which verifier
verdict (PASS / FAIL / INCONCLUSIVE) is a breaking change**, regardless of how
small the code diff is.

Status reminder: everything up to and including `0.2.1` is a **PROPOSAL**.
Nothing here is a ratified standard.

---

## [0.4.1] - 2026-11-19

Released so that the version number, the published artifact and the repository
HEAD all name the same bytes. `0.4.0` on PyPI was built on 2026-11-18; `main`
kept moving afterwards (#241, #242), which left the citable artifact behind the
tree it claimed to be. `0.4.1` is built from `main` and is what the registry
record carries.

- No intentional behaviour change beyond what is listed under `[Unreleased]`
  below: the verification path, the twenty checks and the three-valued verdict
  semantics are the same code. Anyone who needs the 2026-11-18 bytes can still
  install `0.4.0`; both are pinned.
- What is different for a reader: `docs/` now carries the external-baseline
  measurements of 2026-11-19 and the one-click outsider run (#242), so a citable
  DOI finally points at a tree a reader can also browse.
- Version strings in `pyproject.toml` and `uibc_core/__init__.py` move together;
  `SPEC_VERSION` stays `uibc-core/0.3.3-proposal` on purpose - it names the wire
  format, not this package's release number, and changing it would silently
  invalidate every package already sealed under it.

## [Unreleased]

### Six China-registry DID methods, each at the level its own text allows (2026-11-24)

- `uibc_core/did_cn.py` (new, standard library only) accepts `did:cn`, `did:ioa`,
  `did:cndid`, `did:ctid`, `did:oan` and `did:cndomain` by their published ABNF,
  and resolves the four that publish a channel — never with a guessed default URL:
  `did:cn` via `GET {base}/did/resolve/<did>` (spec §3.2), `did:ioa` / `did:cndid`
  via an `operation: "read"` envelope (§5.2), `did:cndomain` via HTTPS publication.
  `did:ctid` (vendor SDK, SM2 keys) and `did:oan` (no HTTP read API in the spec)
  are validated and then refused, with the reason stated per method in
  `matrix()`.
- `did.resolve()` gains `endpoint=None` and dispatches the six names to
  `did_cn`; `UnsupportedMethod` now lists what is actually supported.
- The "no published specification, 11 paths returned 401/404" sentence is
  **deleted**, not reworded: all six methods (and `did:wba`) do have public text.
  Replaced by `docs/spec-sources/did-cn-specs.md` (spec URLs, byte counts,
  ABNF, per-method support matrix).
- Recorded finding, in code comments and in the doc: an offline DID document
  cannot be rebuilt from a `did:ioa` / `did:cndid` identifier. The suffix is capped
  at 42 characters, leaving ≤40 for the key body, while a 32-byte Ed25519 key
  needs 43–44 in base58 — the arithmetic, not our laziness, closes that door.
- `tests/test_did_cn.py` (41 cases): spec examples accepted, out-of-grammar
  neighbours refused, endpoint-never-defaulted, envelope shape, document-id
  mismatch, matrix fields, the suffix-length arithmetic, and three CLI cases —
  `register` refuses an `identifier_only` binding, requires `--did-endpoint` for a
  registry method, and proves resolvability before writing the binding.
  `tests/test_did.py`'s "refused not guessed" case is split accordingly: `did:wba`
  and `did:lgd` still raise `UnsupportedMethod`; `did:cn` / `did:ioa` strings
  outside the published grammar now raise `IdentifierError`.
- CLI: `register` / `verify` / `gate` gain `--did-endpoint`; `register` resolves
  the identifier once at write time rather than accepting a binding nobody can
  check, and `resolve_ed25519_key()` passes the endpoint through.
- No version bump in this entry: 0.5.1 would drag ~20 generated-artifact
  consistency tests into red, so the change is booked here and the bump is a
  separate job (regenerate first, then bump).

- CI fix: `actions/checkout` now uses `fetch-depth: 0` in `ci.yml`. The test that
  recomputes the outsider's figures at `8a95747` needs that commit to exist in the
  clone; on a shallow clone it now reports **skipped** with the reason, rather than
  failing, because a missing input is not a passing test either.

### The outsider's receipt is recomputed here, not quoted (2026-11-19)

- `EXTERNAL-NODE-001.md` quoted two figures - `Ran 605 tests` and
  `checks compared: 70, mismatches: 2` - from a host we do not control. Quoting
  numbers nobody here can recompute is the smallest form of hearsay, under a
  heading that says "third-party evidence".
- `tools/verify_external_node_report.py` exports `8a95747` into a scratch
  directory and runs the same two commands. Result on our side:
  `605 tests`, `mismatches: 2`, `AGREEMENT: FAIL - SPEC BUG` - both figures
  match his exactly.
- The skip count does not match: he saw 22, we see 1. Skips follow installed
  extras, which is why no document should carry one.
- The point of the match: **605 and 2 are properties of that commit, not of his
  machine.** A different OS and Python arrived at the same pair because the code
  produced them.
- `tests/test_verify_external_node_report.py` (3 cases): the tool's expected
  figures are read back out of the report itself, the two-line shapes parse, and
  a `--quick` run recomputes the comparison and prints its scope sentence.

### Conflicts on generated files get a script, not a person's afternoon (2026-11-19)

- `docs/EVIDENCE-INDEX.md` and `docs/EVIDENCE-DASHBOARD.svg` are script output.
  Both sides of a parallel branch regenerate them, so every merge conflicted on
  them; one round spent five rebases, two of which were hand-regenerating files
  a script had already known how to print.
- `tools/resolve_generated.py` reads the conflicted paths mid-rebase and
  regenerates the ones a generator owns, then stages them. If a conflicted path
  is not generator output it prints it and exits 1 - a tool that "picks a side"
  on hand-written files can silently drop someone's work, so it refuses to.
- `tests/test_resolve_generated.py` (3 cases): the allow-list stays at exactly
  two paths, every listed generator exists, and outside a rebase the tool
  changes nothing.

### The defect an outsider found is now a check that can fail (2026-11-19)

- External node 001 (Wang Guigui, Debian 13, uid 1001, no `pip install`, README
  commands verbatim) ran `cross_check.py` on `8a95747` and got exit 1: two rows
  on `fixture:duplicated` disagreed (S4 `FAIL` vs `PASS`, S5 `INCONCLUSIVE` vs
  `FAIL`). He then re-ran on `343d906` on his own initiative and got 0 mismatches.
- `tools/external_node_regression.py` re-runs that comparison and fails if the
  two implementations ever disagree on `fixture:duplicated` again. The exit code
  of `cross_check.py` is deliberately not the signal: it was 0 after the fix and
  1 before, and this check has to accept the first and refuse the second.
- Ninth item in `tools/run_all_evidence.py`; `--online` is now
  `9 ok, 0 failed, 0 skipped, 22.8 s`, and the dashboard carries nine rows.
- `tests/test_external_node_regression.py` (2 cases): the parser recognises the
  exact line shape from his report, and the limit ("this does not establish that
  his run is reproducible today") travels with the claim.
- `docs/external-review/RE-RUN-REQUEST.md`: draft, unsent. Asks the same operator
  to run today's `main` on the same host - first run found the defect, second
  confirms the repair, which makes a verification line rather than a second node.
- No claim about being stronger, better, or first appears in any of this.

### The suite size is counted in one place (2026-11-19)

- Eight documents carried the literal test count. Every parallel branch rewrote
  the same eight lines, so every pull request arrived in conflict; this round
  spent four rebases on it before the cause was obvious.
- `README.md`, `README.en.md`, `AGENTS.md`, `docs/COMPOSITION-VERIFIER.md`,
  `docs/CONFORMANCE.md`, `docs/ECOSYSTEM-MAP.md`, `docs/INTEROP-MATRIX.md` and
  `docs/ONE-COMMAND-AUDIT.md` now cite `docs/EVIDENCE-INDEX.md` instead of
  typing the count.
- `tools/build_evidence_index.py` prints what it measured (`641 个用例`); a
  number a generator counts is a number nobody has to retype.
- `tools/check_doc_facts.py` reports a typed count anywhere in `TARGETS` as a
  mismatch even when the number is right: "cite docs/EVIDENCE-INDEX.md instead
  of typing the count".
- `tests/test_doc_facts_cite.py` (2 cases): a correct-but-typed count fails, and
  the index carries the measured number.

### The signature primitive gets a third-party referee (2026-11-19)

- `tools/external_crypto_check.py`: `uibc_core/ed25519.py` is pure Python, so
  verifying our own seals with it is self-consistent even if it were wrong.
  The check verifies the same facts with `cryptography` (OpenSSL): `06` ok/ok and
  `36` fail/fail, agreeing package by package, plus a negative probe - one byte
  changed in the payload must be refused by the third party.
- Eighth item in `tools/run_all_evidence.py`: `--online` runs eight checks
  (`8 ok, 0 failed, 0 skipped, 20.5 s`); the dashboard regenerates with eight rows.
- Limit stated in the tool and in `docs/PAPER-EVIDENCE.md` row 8: RFC 8785
  canonicalisation still uses this repository's JCS implementation and no
  third-party JCS library is installed here, so that layer is not cross-checked.

### The recheck, the adoption note, and a test that exhausted the inode table (2026-11-19)

- `docs/LANDSCAPE-2026-11.md` gains a dated recheck. On specification and
  ecosystem the gap widened: `-05` is 61 pages with seven IANA registry requests;
  `draft-pidlisnyi-aps-04` ships 17 repositories in four languages and two hosted
  services; `draft-munoz-scitt-permit-profile-01` is a third independent author.
- The same recheck finds adoption at zero **across the field**: `arXiv:2606.04193`
  says it in its own words. An adoption count is not a competitive metric -
  nobody leads it, including the largest draft.
- `docs/ADOPTION-MEASUREMENT.md`: the four-bucket method published as something
  copyable, its four limits stated, the UIBC/UPnP name collision recorded, and a
  message draft marked **draft, unsent**.
- `tests/test_verify_js.py::cases_root()` unpacked the archive **once per call**.
  Measured 2026-11-19: `/tmp` held 1,387 `uibc-js-cases-*` directories at 449
  inodes each; the machine's inode table hit 100% (655,360/655,360) and every
  later test failed with "No usable temporary directory". Now one extraction per
  process, removed at exit, with two regression tests; a full run leaves zero
  such directories.
- `tools/check_citations.py` gains four references; the three IETF ones resolve
  at 200.

### v0.4.0 tagged, and the suite is downloadable without an account (2026-11-19)

- Tag `v0.4.0` on the commit that carries the PyPI bytes; release
  `uibc-core 0.4.0` with `uibc-conformance-0.4.0.zip` (114,576 B, sha256
  `9a1ca72f...`) as an asset - a branch moves, an asset does not.
- The stranger's path was exercised rather than assumed: the asset was
  downloaded, its hash compared with the tree, then run against a verifier
  invoked only through the documented CLI contract - `strict 36/36, refused 30/36`.
- `docs/UPSTREAM-SUBMISSION-PLAN.md` now marks steps 1 and 2 done and still says
  steps 3 and 4 are unsent.

### The suite is now addressed to strangers (2026-11-19)

- **`docs/CONTRIBUTION-FALSIFIABILITY.md`**: the 36-package suite stated as an
  offer to any agent-evidence verifier - the CLI contract, the accept half that
  stops a refuse-everything verifier scoring full marks, the two current results,
  and the four limits including the one this document exists to invite someone
  to close.
- **`tools/run_conformance.py --name`**: a third party's result can carry its
  own implementation label instead of ours.

### Adoption is a measurement, not an adjective (2026-11-19)

- **`tools/check_adoption.py`**: asks four parties we do not run - another
  repository, another codebase, a standards body, the nearest SCITT profile.
  All four currently return zero; a non-zero bucket exits 1 so nobody can quietly
  start claiming more.
- **`docs/LANDSCAPE-2026-11.md`**: what the nearest project actually has
  (`draft-mih-scitt-agent-action-capsule-05`, an IETF 126 interop report, two
  PyPI packages, four framework adapters) against what we have (nothing in that
  column). It says the number plainly: not ahead, behind. Then three routes that
  could move adoption off zero, ranked by cost.

### One command, seven checks, one exit code (2026-11-19)

- **`tools/run_all_evidence.py`**: runs the seven things this repository claims,
  offline by default, `--online` for the three that need Zenodo, PyPI, GitHub and
  Software Heritage. 16.3 s, `VERDICT: OK`, exit 0.
- **`docs/EVIDENCE-DASHBOARD.svg`**: the same seven, as a picture, generated by
  `--svg` so it cannot disagree with the run.
- **`docs/PAPER-EVIDENCE.md`**: claim -> command -> measured value -> what it
  cannot support. Including the three limits that would be dishonest to omit.

### The 0.4.0 bytes, pinned and checked across three sources (2026-11-19)

- **`tools/pin_release.py`**: asks PyPI what it serves, downloads both artefacts,
  recomputes SHA-256, and writes `anchors/pins/uibc-core-0.4.0.sha256` in plain
  `sha256sum` format. 1.457 s, both artefacts matched.
- **`tools/check_pins.py`**: the release asset, the index, and the download must
  all agree - any two agreeing is not enough. 2.229 s, `VERDICT: OK`.
- **Release `release-pins-0.4.0`**: the pin published on a channel PyPI cannot
  rewrite.
- **0.4.0 itself** was published by the parallel line on 2026-11-18T17:19Z;
  this entry pins it, it does not claim to have shipped it.

### The anchor moves to a channel the package cannot reach (2026-11-19)

- **Release `anchor-001`**: the same `anchor.json`, published as a downloadable
  asset, so editing the package can no longer edit the anchor in one commit.
- **`tools/check_channel.py`**: takes the anchor from the release and the
  package from the repository, reassembles them, and asks the verifier whether
  they still belong together. 1.383 s, `VERDICT: OK`.
- **`docs/ANCHOR-CHANNEL.md`**: the four channels considered and why this one,
  including what it does not buy (same platform, same account).

### The first anchor inside the repository (2026-11-19)

- **`anchors/001/`**: `seq 1`, a new key, `checkpoint_head sha256:2935c3f4…`.
  The package is the demo fixture, so the head is the number the demo pages
  already print; the key is not the demo key, which is public and must never
  sign a publication.
- **`tests/test_published_anchor.py`**: five offline checks in CI - well-formed,
  ANCHORED, chain accepts it, the JavaScript implementation agrees, and a
  one-byte edit to an evidence file makes S4, S8 and S9 fire.
- **`docs/FIRST-ANCHOR.md`** and **`anchors/README.md`**: what it is, what it
  is not, and how to withdraw it. The anchor and the package share one channel,
  which proves the mechanism and not yet the separation; that needs a channel
  decision, not a commit.

### Three witnesses of the artefact, re-checked (2026-11-19)

- **`tools/check_witnesses.py`**: asks Zenodo, Software Heritage and Sigstore
  Rekor, live, whether what they hold is what we cite. 6 s, exit 0 only if every
  digest matches. Both digests (Rekor SHA-256, Zenodo md5) equal the file in
  `dist/`.
- **`docs/WITNESSES.md`**: what each one proves and does not - witness of the
  artefact, never adoption of the format.
- **`docs/IMPLEMENTATION-STATUS.md`**: a new section 0 separates the two
  numbers. The previous page reported "zero external evidence"; that was a
  counting error, and hiding a DOI that already exists is worse than having none.
- **Not in CI, on purpose**: a third party's outage should not turn our CI red.

### One command, one stranger, both implementations (2026-11-19)

- **`tools/verify-js/chain.mjs`**: the anchor line judged with node:crypto, no
  shared code with `anchor_chain.py`. Five scenarios frozen as *agreement*:
  sound line, gap, replay, rewritten predecessor, withheld anchor (STALE).
- **`tools/outsider_chain_audit.py`**: one command that builds two bundles,
  links them, and answers four questions with both implementations in a
  stripped environment - 0.877 s end to end, exit 0 only on VERDICT OK.
- **Deliberate duplication, stated**: the six lines of JCS are repeated rather
  than shared; a shared helper is one more thing that can drift, and the rule is
  tiny.
- **What it does not prove**: the line is not real. No `anchors/` directory,
  no publication - `docs/IMPLEMENTATION-STATUS.md` still reads zero.

### Anchors that name their predecessor (2026-11-19)

- **`anchor.json` gains `seq` and `prev_anchor_digest`.** A single anchor cannot
  distinguish "current" from "yesterday's, still perfectly self-consistent"; a
  line of anchors that each name the digest before them can.
- **`tools/anchor_chain.py`** judges a directory of anchors: gap, replayed
  position, rewritten predecessor, and a first anchor claiming a predecessor are
  all CHAIN BROKEN; a chain shorter than what the caller already knows is
  **STALE** (exit 5), because "absent" and "withheld" are the same danger.
- **`make_release_bundle.py --prev-anchor`** fills `seq+1` and the predecessor
  digest; **`anchor_check.py --prev`** refuses a rollback by comparing the two.
- **Eight frozen scenarios** in `tests/test_anchor_chain.py`.
- **What it cannot do, stated:** withholding cannot be countered by arithmetic
  here - only by where the anchors are published - and seq 1 has no way to
  prove itself current without an outside record.
- **No real chain exists yet**; `docs/IMPLEMENTATION-STATUS.md` still reads zero.

### The publisher check, done twice (2026-11-19)

- **`tools/verify-js/anchor.mjs`**: the anchor verdict with node:crypto and
  `verify.mjs` - no shared code with `anchor_check.py`, no call into it. Seal
  verified under the anchor's key, `checkpoint_head` compared via
  `--expect-head`, exit 0 only for ANCHORED.
- **The Node path refuses to judge the RFC 3161 block** and says so
  (`timestamp: not judged here`) rather than borrowing the other
  implementation's answer.
- **Four frozen scenarios** (`tests/test_anchor_second_impl.py`): baseline
  ANCHORED on both; a zeroed head, a swapped key and a missing anchor all
  refused by both. Exit-code conventions differ deliberately; the verdict word
  is what gets frozen.
- **`docs/ANCHOR-SECOND-IMPL.md`** states what agreement does not buy: both
  read the same bytes, and no external anchor exists yet.

### A timestamp inside the anchor (2026-11-19)

- **`anchor.json` gains an optional `tsa` block**: an RFC 3161 token plus the CA
  bundle it is checked against, so a stranger can date the anchor offline.
- **Two cover modes, and the difference is printed rather than smoothed over:**
  `covers="anchor_digest"` proves *this claim existed at that time* (token over
  JCS of agent_id/key_id/pubkey/head); `covers="file"` proves some bytes existed
  and is reported as `unbound`, because it dates a publication, not the claim.
- **Four refusals, all tested:** token over other bytes, token without a CA
  bundle ("an unchecked timestamp is not a timestamp"), an unknown cover mode,
  and `anchor_digest` mode given a token that covers something else.
- **The positive path is a real FreeTSA signature** (`tests/fixtures/anchor/
  freetsa.tsr`, 2026-11-17T08:11:35Z), verified offline against the shipped CA -
  a TSA we do not control on bytes we did not design. It covers a release-status
  file, so it exercises `covers=file`; the `anchor_digest` path has full negative
  coverage and needs a live stamp for a positive one.
- **`make_release_bundle.py`** prints the `anchor_digest` to stamp and accepts
  `--tsa-token/--tsa-cabundle` to attach it. A live stamp is a network call to a
  third party, so CI does not perform one.
- **`docs/TIMESTAMP-IN-ANCHOR.md`** states the remaining status plainly: no
  published anchor carries a timestamp yet.


### One file, no install (2026-11-19)

- **`tools/build_zipapp.py`** builds `dist/uibc.pyz`: the verifier, the CLI and
  the anchor check in one standard-library file. `verify`, `explain` and `anchor`
  work with no pip, no network and no checkout.
- **`uibc_core/__init__.py`** reads its own modules through the archive when the
  package sits inside a zipapp, so `SPEC_ID` stays equal to the checkout it was
  built from. A packaged verifier that reported a different provenance than its
  source would be reporting the packaging.
- **`tests/test_zipapp.py`** runs the zipapp from an empty directory with
  `PYTHONPATH` stripped: verify works, `spec_id` matches, `anchor` returns
  ANCHORED on a publisher bundle and exit 1 on a bundle with one byte changed.
- **`docs/ZERO-INSTALL.md`** also records what this does not solve: we build the
  zipapp, it carries no anchor, and it is not signed. It is a different point on
  the convenience axis than a hosted endpoint, not a better one everywhere.


### Anchoring the publisher (2026-11-19)

- **`tools/make_release_bundle.py`**: a publisher bundle = the sealed package plus
  `anchor.json` (public key, key_id, checkpoint head). The head goes into the
  manifest *before* signing - a signed manifest edited afterwards is exactly the
  forgery that row A catches and row B repairs.
- **`tools/anchor_check.py`**: the one command a stranger runs.
  `VERDICT: ANCHORED` only when the signature matches the anchor's key *and* the
  state matches the anchor's head; `NOT ANCHORED` when verification fell back to
  a key the package supplied; refuses to run without an anchor file, because an
  anchor read out of the bundle is the bundle vouching for itself.
- **Measured contrast, now a test:** a repaired, re-signed forgery (row C of
  `docs/FORGERY-ENVELOPE.md`) still verifies `PASS, unanchored` on its own, and
  fails S6 the moment the publisher's anchor is applied. The anchor is the
  only thing that changes the answer, which is why it has to travel separately.
- **`docs/PUBLISHER-IDENTITY.md`**: the five-step release procedure, why the
  key and the head must leave through a channel the package cannot reach, and
  the three things this does not do. Status stated plainly: no release in this
  repository has published an anchor, so every verdict here today is at best
  `PASS, unanchored`.
- **`tests/test_anchor_check.py`** freezes: own bundle anchored; wrong head
  refused (S9); wrong pinned key refused (S6); forgery refused against a real
  anchor while still clean without one; anchor without a key refused.


### A forgery that agrees with itself (2026-11-19)

- **`tools/composed_forgery.py`**: every previous audit measures a *change this
  project can see*. This one performs the attack: rewrite one evidence file, then
  repair the content hash, the evidence root, the index digest and the checkpoint
  head - all of them arithmetic on bytes the attacker owns.
- **Six attacks, measured.** Undeclared rewrite -> FAIL (S4). Repaired rewrite ->
  INCONCLUSIVE (the owner's seal cannot be checked). Repaired and re-signed with
  a key of the attacker's own -> **PASS, `unanchored`**. Same with the publisher's
  key pinned -> FAIL (S6). Same with a published head pinned -> FAIL (S9).
  Seal deleted -> INCONCLUSIVE, never better.
- **The point is row three**, and it is written into the tests rather than the
  pitch: a stranger with no publisher key produces a clean verdict, and the
  verdict says `unanchored` because that is exactly what it can support. PASS
  there means *this key signed these bytes*, not *the publisher wrote them*.
- **`docs/FORGERY-ENVELOPE.md`** prints the six rows, names why each one stops
  where it does, and lists the three things that actually close the gap:
  publish the key (`--pubkey`), publish the head (`--expect-head`), anchor the
  head to an external timestamp or receipt.
- **`tests/test_composed_forgery.py`** freezes all six outcomes, row three
  included, so the boundary cannot drift into a stronger claim later.


### Two defects at once (2026-11-19)

- **`tools/check_combinations.py`**: every other audit here asks about one
  change. This asks about two, which is the question a composed forgery poses -
  a second defect that supplies exactly the consistency the first one broke.
  Fourteen independent mutations, each caught alone; then all 91 pairs and all
  364 triples.
- **Measured: 91 of 91 pairs and 364 of 364 triples fail somewhere.** Zero
  combinations are silent, and zero show the cancelled pattern (both halves
  caught alone, the combination caught nowhere). Under a second, so it is a CI
  step and a test, not a ceremony.
- **The probe corrected itself once:** the undeclared file first went into
  `evidence/files/`, where the format deliberately keeps structural members and
  resolves each by its own check, so nothing moved. The same mutation at the
  package root - where a note that contradicts the evidence has no owner - made
  S1 fail at once. Same defect, two positions, two correct verdicts.
- **`docs/COMBINATIONS.md`** carries the matrix and states the limit plainly:
  three at a time is not "any number", and the family is single-field defects,
  not a chained forgery.


### Two identifier fields that identified nothing (2026-11-19)

- **`evidence_id` was read by no check** for presence or uniqueness. Two entries
  could share an id, or one could carry none, and S4 still called the evidence
  intact - the index is read by position everywhere, so identity was never
  needed. `S4` now requires a non-empty, unique `evidence_id` per entry, in
  Python and JavaScript (F-009).
- **A gap stated is not a gap closed.** `docs/FIELD-COVERAGE.md` had said
  "duplicates are not checked - stated rather than implied". That was honest
  about the hole and still left it open; this closes it, and the document says
  which mutations the new check does and does not catch.
- **The lesson worth keeping:** a field silent to a *changed* value is not
  silent to a *repeated* or *absent* one. For identifiers, the interesting
  mutation breaks identity rather than alters it - which is exactly what a
  value-swapping probe cannot see.
- **One rule attempted and withdrawn in the same PR:** `identity.status` was
  compared against the state the lifecycle reaches, and the clean fixture failed
  - `REGISTERED` against a chain that ends `ACTIVATED` - because the two fields
  describe different things. Withdrawn rather than re-tuned until green; the gap
  stays listed in `docs/FIELD-COVERAGE.md` as a known gap.


### Every field, and who notices when you change it (2026-11-19)

- **`tools/check_field_coverage.py`** asks the F-007 question by measurement:
  for each of the 59 leaf fields a package writes, replace the value with a
  different one of the same shape, run verify, and record every check whose
  result moved - in either direction, not only to FAIL. 36 alterations move
  something; 23 move nothing.
- **The 23 are not a list of holes, they are a list of reasons**, and every one
  is written down: descriptive fields (schema tag, version, media type, note),
  unreferenced values (the chain's last event id, evidence ids, whose uniqueness
  is not checked - stated rather than implied), undecidable ones (per-event
  signatures the format defines no payload for; an HMAC seal whose secret the
  verifier does not hold, where INCONCLUSIVE is the correct answer), and two
  enums nothing validates yet.
- **One real hole, fixed:** `payload_hash` was written by every lifecycle event
  and read by nothing - replace the `null` with any string and every check said
  what it said before (F-008). `S12` now requires 64 lowercase hex when the field
  is declared, in both implementations. This checks the shape of the claim, not
  its correspondence to a payload the package does not ship.
- **Frozen gate:** `tests/test_field_coverage.py` fails if a field becomes
  silent without a reason on record, and also fails if a listed one stops being
  silent (both directions, so the document cannot quietly rot).
- **`docs/FIELD-COVERAGE.md`** carries the full 59-row matrix.


### A field that existed and nobody read (2026-11-19)

- **Second shapes for the five single-sample checks.** Writing them found a
  defect instead of a confirmation. Changing `lifecycle.events[0].agent_id`
  to another agent produced verdict `INCONCLUSIVE` with **S2 PASS and S3 PASS**:
  the identity check compared `identity.json` with `manifest.json` and never
  read the `agent_id` the events themselves carry, so a package could attribute
  its whole lifecycle to somebody else's agent and still be called consistent.
- **S2 now reads it**, in Python and in the JavaScript implementation, and
  reports the event id and both agent ids. The forged package fails S2 and only
  S2 (S3 stays PASS, so the report is not merely "something is wrong").
- **`failure_corpus/F-007.json`** records the finding; regression test
  `tests/test_identity_in_lifecycle.py` asserts both directions.
- **Matrix after the fix:** S1, S2, S3, S11 each have two independent shapes;
  S7 keeps one, because it only runs when the package declares an index
  metadata digest and the fixture does not — a package that makes no claim
  cannot be caught lying about it.
- **529 tests green** (2 skipped), `check_doc_facts` 0 mismatches, second
  implementation agrees on 36/36 cases with 30 named.


### Every check, and something that breaks it (2026-11-19)

- **`tools/check_falsifiability.py`** asks what a verifier project rarely asks
  itself: for each of the nineteen checks, is there a published artefact that
  makes it say FAIL? It collects the answer from the thirty-six exported
  conformance cases (seventeen checks) and from `tools/outsider_audit.py`
  (S16: a real FreeTSA token and four mutations; S9: a pinned head and a
  rollback only the pin can see).
- **Measured: 19 of 19, zero holes.** The tool exits non-zero if that stops
  being true, and CI runs it in the second-implementation job, after the suite
  is exported.
- **`docs/FALSIFIABILITY.md`** records the matrix and the uneven column: five
  checks (S1, S2, S3, S7, S11) rest on a single artefact, which proves they
  are not decoration but not that they catch every shape of forgery.

### Three optimisations on 20,000 files, all reverted (2026-11-19)

- **Profiled the 1.1 s** it takes to verify 20,000 entries: S12 semantics 0.354 s,
  S11 byte scan 0.278 s (0.117 of it the depth walk), JCS canonicalisation 0.154 s,
  SHA-256 of the evidence 0.152 s. Hashing all 20,003 files on its own is 0.170 s
  (8.5 us a file), so I/O is not the bottleneck and never was.
- **Caching `realpath` per directory:** 1.104 s -> 1.093 s, 1%. The OS already
  caches those lookups; the profile was showing time the workload does not pay twice.
- **Stripping string literals with a regex before the depth scan:** 1.146 s. Two
  passes over ten megabytes cost more than the loop they replace.
- **Skipping `fromisoformat` for clearly-past timestamps:** rejected before
  writing it - it only fires on old evidence, and honest benchmarks are near now.
- **All three reverted.** `verify.py` is unchanged; the containment test stays
  one step. `docs/PERF-LOG.md` records the attempts and the floor: 54 us per
  entry, nineteen checks, 60 MiB at 20,000.

### The sixteen tests that were skipping (2026-11-19)

- **Audited `OK (skipped=16)`.** Fifteen of the sixteen were skipping for one
  reason: `.[verify]` does not carry `opentimestamps-client`, `langchain-core`,
  `coincurve`, `pynostr` or `agent-action-capsule`. CI installs the same extra,
  so the interop check against the peer, the live-LangChain measurement, the OTS
  proof check and both Nostr anchors had **never run in CI**. They were in the
  suite, counted in the total, and executed nowhere.
- **They all pass once installed** (`527 OK (skipped=2)`, 42.4 s). Nothing in
  the tests needed fixing, which is the finding: the code was right and the
  gate was hollow.
- **New extra `interop`**, and a new CI job `test-with-extras` that runs the
  full suite with it and then fails on any skip whose reason contains
  "not installed". Green can no longer mean "the hard half was skipped".
- **`docs/SKIPPED.md`** records the list, the categories, and the two skips that
  remain (both deliberate).
- **The new gate caught a second category on its first run:** five
  `test_aee_rail.py` tests were skipping on "agent_evidence_vectors corpus not
  installed" — the rail that reads somebody else's conformance corpus had never
  run in CI either. `conformance` existed as an extra; no job installed it.
  `test-with-extras` now installs `.[verify,interop,conformance]`.

### The neighbourhood, surveyed rather than admired (2026-11-19)

- **`docs/PEER-SURVEY.md` + `docs/PEERS.json`**: six neighbouring projects measured
  from one PyPI JSON and one GitHub REST request each, with no figure quoted from
  a README. Three are the same problem answered differently; three are adjacent
  infrastructure and are used as a maturity bar, not as opponents.
- **The honest split:** last of the seven on distribution (4 releases against
  23-78, 11 stars against 2-1,056) and first, by a wide margin, on
  re-checkability (second implementation, CI agreement assertion at 36/36,
  one-command stranger audit, hostile-input suite, public conformance corpus,
  cost measured to 20,000 evidence files). The second implementation is the
  strongest asset and, by the peer's own RFC 7942 rule, not independence.
- The page states what this changes: the next gain is not another check, it is
  the first row in the adoption table.

### Scale, and a semantic disagreement between the two implementations (2026-11-19)

- **`docs/SCALE.md` + `docs/SCALE.json` + `docs/SCALE.svg`**: verification cost
  measured at 100 / 1,000 / 5,000 / 20,000 evidence files. Python: 0.007 / 0.055 /
  0.282 / 1.104 s, 23.6 / 25.1 / 31.2 / 60.3 MiB peak. Linear at about 55 us and
  1.9 KiB per file.
- **Found by the scale run:** the JavaScript verifier reported **FAIL** for an
  unsigned package where Python reported **INCONCLUSIVE**, both on the same bytes.  The
  absence of a signature is a missing attestation, not a violation; three-valued
  adjudication is this project's claim, and the second implementation was
  contradicting it in the one place the 36/36 conformance agreement never looked,
  because every conformance case carries some seal.
- **Fixed** in `tools/verify-js/verify.mjs`, with a regression test pinning both
  implementations to one answer: `test_an_unsigned_package_is_inconclusive_in_both_languages`.
- Also recorded: S12 refused a first synthetic build whose `created_at` was eight
  hours in the future (`26306 s in the future`) - an unplanned demonstration that
  the check fires.
- `docs/COMPETITORS.md` keeps the missing item: no same-size comparison against the
  peer has been run, because the package formats differ and that would compare
  two different kinds of work.

### 0.4.0 dry run: the package now checks itself (2026-11-19)

- **The sdist could not run its own tests.** First build collected 290 of 526
  tests and produced 6 failures + 97 errors, all of them missing fixtures and
  tools. Fixed in three measured passes (290 -> 475 -> 482 -> 526) by grafting
  every top-level directory instead of guessing which ones tests read.
- **`MANIFEST.in`** now carries everything the suite reads, with the
  measurements and the reasoning written into the file.
- **Wheel verified:** `pip install` of the built 0.4.0 wheel reports 0.4.0 and
  the same eight checks as `main` on the clean package, including S11 and S12
  that 0.3.3 lacked.
- **CI guard:** a new `sdist-self-check` job builds an sdist and runs the suite
  from the unpacked archive, so a directory missing from `MANIFEST.in` fails on
  the pull request rather than in a stranger's hands.
- **`docs/RELEASE-DRY-RUN.md`** records the whole run with commands and timings.

### A stranger's ten minutes, measured (2026-11-19)

- **`docs/STRANGER-TRIAL.md`** records a first run in a directory that had never
  seen this project: clone in 2.3 s, `tools/outsider_audit.py` in 0.3 s, `VERDICT:
  OK` — two commands, no credentials, no dependencies.
- **The same trial found the sentence that stops adoption.** `pip install
  uibc-core` gives 0.3.3, which reports **six** checks on the clean package;
  `main` is 0.4.0 and reports **eight**. The code is better than the package,
  and the package is what a stranger gets.
- **README now states the three version numbers** (`0.4.0` unreleased / `0.3.3`
  on PyPI / `0.2.1` archived) and which one an installer actually receives, with
  a link to the measurement. The previous line called 0.3.3 "the current
  implementation", which stopped being true when 0.4.0 work began.

### Adoption, measured the peer's own way (2026-11-18)

- **`docs/COMPETITORS.md` gains an adoption table**, each merged claim checked
  against GitHub rather than taken from the peer's page: a contribution merged
  into the IETF SCITT working group's shared repository, a third-party product
  shipping their verifier, an independent draft building on theirs, a public log
  with 15134 entries. Ours: zero rows.
- **`docs/IMPLEMENTATION-STATUS.md`** records that in the RFC 7942 four-bucket
  format they use. All four buckets are empty, and the page says so in their
  words rather than in ours.
- **`docs/UPSTREAM-SUBMISSION-PLAN.md`** lists what each external route would
  cost and in what order they have to happen. Nothing in it has been sent.
- The distinction this round makes explicit: a second implementation written
  here is *internal* evidence, however independent it is in code. Only someone
  else running it is external evidence.

### The comparison now re-checks itself (2026-11-18)

- **`tools/check_competitors.py`** re-fetches what a stranger can fetch (PyPI
  JSON, GitHub repo record) for both projects, diffs it against
  `docs/COMPETITORS.json`, and exits non-zero when the world has moved. An
  endpoint that fails to answer is recorded as unmeasured, not estimated.
- **`docs/COMPETITORS.svg`**, built by `tools/build_competitors_svg.py` from the
  recorded baseline, so the picture cannot go stale on its own. Four of its six
  rows point their way; the two that point ours are the two a test count cannot
  buy.
- **`tests/test_competitors.py`** holds the offline half: the baseline is
  complete, and the picture states the same numbers. The network half is
  deliberately not in CI - a flaky gate teaches people to ignore gates.

### A depth ceiling, and a measured peer (2026-11-18)

- **Nesting ceiling, both implementations.** 4000 levels of `[` used to end in a
  stack exhaustion reported as S0 - "the verifier broke", a statement about us
  and not about the input. `MAX_NESTING = 512`, counted outside string literals,
  refuses it as S11. Taken from `agent-action-capsule`, which refuses at 128 with
  a message naming the limit.
- **A manifest that parses as an array** used to reach `.get()` on the Python
  side and raise `AttributeError`, again landing on S0. S1 now reports it.
- **Both sides stop when the bytes never became JSON**: invalid UTF-8, a repeated
  member name, a document past the ceiling, unparseable bytes. Nothing downstream
  is claimed about bytes nobody read.
- **`docs/COMPETITORS.md`** measures `agent-action-capsule` 0.17.0 and this
  project on the same day, with the command for each number, and states plainly
  where this project is behind (specification standing, release cadence, surface
  area, test count) as well as ahead (a second implementation, gated in CI).

### Hostile input: ten cases, ten verdicts, no crashes (2026-11-18)

- **`tools/redteam_robustness.py`** builds ten packages that are not packages:
  not JSON, an array where an object belongs, duplicate member names, a bare
  `NaN`, 4000 levels of nesting, invalid UTF-8, a path that climbs out of the
  package, a symlink to the host, an empty directory, an 8 MB manifest. All
  ten are answered by both implementations and refused by both.
- **A real hole, closed:** Python's `json` module accepts `NaN` by default.
  A manifest carrying `"remark":NaN` used to parse, pass every element check,
  and come out **INCONCLUSIVE** - an honest-looking answer about bytes that
  are not JSON. S11 now refuses it, on both sides: Python via
  `parse_constant`, JavaScript via `JSON.parse` inside S11.
- **S11 moved first in the JavaScript verifier, with an early return.** Bytes
  that are not JSON cannot be judged by any later check; falling through
  reported S0 ("the verifier broke") and hid the check that had the answer.
- `docs/ROBUSTNESS.md` records the table and explains why the two verdict lists
  differ on early failures without being inconsistent.

### The two implementations now agree on every package (2026-11-18)

- **S3 in JavaScript**, both families of rules: the L1-L7 state machine and the
  L8-L12 semantic layer. Coverage 18 of 19; the only check absent is S0, which
  exists only when the verifier itself throws.
- **`agree_with_python: 36 of 36`.** The cross-implementation check no longer
  asks only "does it name an expected check" - the same set of failing checks
  now comes out on every package. It was five apart.
- **A hole found in the Python verifier by the JavaScript one.**
  `manifest.evidence_count` was never compared with the number of index entries,
  so a package declaring two entries and shipping one passed. Fixed.
- **One root cause scored twice.** The JavaScript verifier derived the evidence
  root from hashes S4 had just shown to be wrong, reporting S5 as a second
  failure. S5 is now INCONCLUSIVE when S4 fails, matching Python: it is the
  same finding, not a second one.
- A test that had been naming a case directory that no longer exists
  (`09-edit-the-evidence-root`; the case is `10-...`) was corrected - it had
  been passing against a stale unpacked fixture rather than the shipped suite.

### The second implementation verifies a stranger's timestamp (2026-11-18)

- **S16 in JavaScript, with no dependency and no shared code.** `tools/verify-js/rfc3161.mjs`
  reads an RFC 3161 token with a minimal DER reader built from `node:crypto` alone, checks
  the CMS signature over `signedAttrs` (encoded as `SET OF`, not `SEQUENCE` — the tag that
  catches naive implementations), locates the ESS `signingCertificate` certHash by walking
  the subtree, and proves the signing certificate was issued by a supplied CA and was valid
  at its stamping time. A real Free TSA token for the head in `tests/fixtures/anchor/`
  verifies: `stamped 20261117081135Z, TSA O=Free TSA`.
- **This is the one witness the project cannot mint.** Every other check is witnessed by
  parties we choose: our tree, our head, our pin. A token is dated by somebody else's key,
  and now two implementations built from the spec — with no shared code — reach the same
  verdict on it, in both the accept and the refuse direction.
- **Red team, seven of seven:** the token as received is accepted; a flipped signature bit,
  a wrong anchored digest, a CA that did not issue it, no CA at all, one mutated digit inside
  a signed attribute, and a truncated token are each refused with a distinct reason.
- **S9 in JavaScript.** `--expect-head <head>` supplies the observation made outside the
  package and compares it with the checkpoint state. The pin is never read from the package;
  without it S9 does not appear, because an unchecked rollback must not look like a pass.
- `node tools/verify-js/rfc3161.mjs <token.tsr> <digest-hex> <ca.pem>` is a standalone entry
  point: anyone with Node can reproduce the token verdict without installing anything.
- **Coverage: seventeen of nineteen checks** in the second implementation; `--strict` and
  lenient modes now agree with the Python verifier's defaults.

### Added

- **CI now fails when the second implementation drifts.** `tools/assert_second_impl.py`
  asserts that every package the suite accepts is accepted, every package it
  refuses fails for a reason one of its expected checks names, and no package
  expects a check the JavaScript side does not carry. Verified by breaking it
  on purpose: with S15 forced to pass it names the four anchor packages and
  exits 1; with S15 removed from the covered set it does the same. The new
  `second-implementation` job runs it on every push and pull request. Set
  equality is not required, because the two implementations legitimately
  differ on five packages and forcing equality would make one of them lie.
- **The gate was tested against itself, in the pipeline.** Pull request #134
  removed `S15` from `COVERED` while four packages still expected it: the
  `second-implementation` job failed, `mergeable_state` stayed `blocked` for
  thirty consecutive samples, and the pull request was closed unmerged. The
  required checks on `main` are now `test (3.13)` and `second-implementation`,
  with `strict` and `enforce_admins` on. Recorded in `docs/NEGATIVE-CONTROL.md`.

### Added

- **The JavaScript verifier covers ten of nineteen checks, up from eight.**
  S14 strict base64: pad bits set, missing padding and stray characters all
  decode permissively, so two decoders can disagree about what was signed.
  Only fields the package itself marks as base64 are examined, so a schema
  that does not use base64 cannot be false-flagged. S10 the closure
  declaration: six components must be present and shaped like digests --
  declaration only, because whether those digests match what actually ran is
  not decidable from a package.
- Both checks are silent on a package that declares neither, exactly as the
  Python verifier is: the correct package's report still shows eight checks,
  not ten.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 36/36   refused 30/36`
- Identical FAIL set to Python: 31 of 36; named an expected check: 30 (+6 positives)
- Out of scope: 0 packages -- the JavaScript verifier now agrees on all 36

### Added (S17, S18)

- **The second implementation now agrees with the first on all 36 packages.**
  S17 recomputes `previousReceiptHash` over the JCS of the predecessor's signed
  envelope and insists the first receipt of a chain carries 64 zeros. S18
  resolves every `policy_digest` to the artefact shipped next to it, and rejects
  one a receipt declares that resolves nowhere. A tree answers "was this byte
  changed"; only the linear link answers "is this record the successor of that
  record".
- Fifteen of nineteen checks now have two independent implementations. The
  four without one are S0 and S3 (not modelled as separate checks on this side),
  and S9/S16, which need an observation or a key this checker does not hold.
- Measured honestly: the FAIL *sets* still differ on 5 of 30 vectors -- the
  JavaScript side reports a superset (an edited byte also moves the root,
  S4 and S5). Same verdict, finer diagnosis. `named an expected check` is 30
  of 30.

### Added (S15)

- **The JavaScript verifier resolves anchors.** Four vectors, one code path:
  a corrupt inclusion proof, a leaf hash that is not a digest, 30 February,
  and a root this package cannot recompute. The lesson from the Python side
  carries over: the claimed leaf must be the leaf that actually sits at that
  index, or the proof is being checked against a subject the set does not
  contain at that position. Resolving against our own root proves the anchor
  was built from this package; it does not prove a third party saw it, and an
  anchor naming an external log stays unresolved rather than counted.
- Thirteen of nineteen checks now have two independent implementations. The
  four packages still out of scope are S9 (out-of-band pin) and S16/S17/S18.

### Added (S8)

- **The JavaScript verifier recomputes the package checkpoint.** One value
  committing to the whole state: lifecycle head, evidence root, index metadata
  digest, evidence count. A lifecycle-only head was not enough -- adding
  evidence changes the root but leaves the log untouched, so two different
  states shared one head. Truncation, rollback and post-seal replacement inside
  one package are what this detects. A whole-store rollback still needs an
  observation made elsewhere, which is S9 and stays out of scope.
- Both S8 vectors now fail on S8: a rewritten index with content untouched
  (also S7), and a truncated lifecycle log. Packages without a checkpoint_head
  are not examined, exactly as the Python verifier behaves. Twelve of nineteen.

### Added (S13)

- **The JavaScript verifier recomputes Merkle inclusion proofs (RFC 6962).**
  Leaf = SHA-256(0x00 || data), node = SHA-256(0x01 || l || r), an unbalanced
  tail is promoted rather than duplicated -- duplicating it would let two
  different trees share a root. It checks the declared algorithm, the declared
  size against the leaves it computed, the root, each proof's index against the
  order it recomputed, hex shape, and the path itself. All four S13 vectors
  (replaced root, inflated size, corrupted proof, swapped index) now fail on
  S13 rather than on something incidental. A package with no tree is still not
  penalised: eleven of nineteen covered.

---

## [0.4.1] - 2026-11-18 (the second implementation grows)

### Added

- **The second implementation verifies Ed25519 seals, not just structure.**
  `tools/verify-js/verify.mjs` now checks S6 for asymmetric seals: it re-derives
  the canonical payload (identity + manifest, plus lifecycle when the seal says
  so), builds an Ed25519 public key from the one recorded in the package, and
  verifies the signature with Node's own crypto. Coverage goes from seven checks
  to eight of nineteen. An HMAC seal is reported as INCONCLUSIVE, because it
  cannot be checked without the owner's key -- the verifier says so rather than
  guessing.
- **The suite now contains an asymmetric seal.** Two cases: "a package sealed with
  Ed25519" (must be accepted) and "flip one bit in an Ed25519 signature" (must
  fail S6). Until now every case carried an HMAC seal, so the property the
  project keeps claiming -- *a stranger verifies provenance with no secret* --
  had no vector. The seed is fixed, so the case is reproducible byte for byte.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 19/36   refused 30/36`
- Identical FAIL set to Python: 13 of 36; named an expected check: 13 (+6 positives)
- `tests/test_conformance.py` no longer hard-codes "5 positives": the counts are
  read from the manifest, so the next case does not break the tests that guard
  the suite.

## [0.4.0] - 2026-11-18

This is the release that makes the eighteen checks reachable. Everything below
that concerns S7-S18 exists in the tree and in no earlier artifact: the
published `0.3.3` verifier reports six checks on the same package that the tree
reports seventeen on (docs/RELEASE-PARITY.md records the measurement).

### Added

- **Twelve checks beyond `0.3.3`:** S7 index metadata, S8 whole-state
  checkpoint, S9 out-of-band pin, S10 attestation closure, S13 merkle proofs,
  S14 strict base64, S15 anchor resolution, S16 RFC 3161, S17 receipt chain,
  S18 policy artefacts, plus the S0 crash fallback and the S11/S12 strictness
  checks in their current form. `python3 tools/check_release_parity.py` prints
  the three-channel comparison.
- **`tools/outsider_audit.py`** -- five red-team stages over one command, with an
  auditor self-test (path gate + behaviour gate) and `--json` output.
- **`tools/build_evidence_index.py`** -- every check mapped to its tests, its
  red-team cover and its docs, measured by running the audit rather than grepping
  the source (`docs/EVIDENCE-INDEX.md`).
- **`tools/build_checks_reference.py`** -- the eighteen checks with the question
  each answers and an explicit three-way classification of their external basis
  (`docs/CHECKS-REFERENCE.md`).
- **`tools/build_outside_kit.py`** -- a whitelisted 43-file audit kit, runnable
  by someone who will not clone the repository.
- **`tools/serve_verify.py`** -- a verify endpoint that accepts bytes and
  refuses hostile archives.
- **`tools/emit_aac_capsule.py`** -- export to the Agent Action Capsule format,
  recomputing the capsule id under JCS and asking their verifier.
- **`tools/check_citation_scope.py`, `tools/preflight_release.py`** -- the two
  gates that stop a claim from outrunning the artifact.

### Changed

- **`pyproject.toml`:** version 0.4.0; the description no longer carries a
  version number, which had drifted from the field beside it.

### Notes on compatibility

Per this project's own rule, any change to what produces which verdict is a
breaking change. Twelve new checks necessarily change verdicts for packages
carrying the fields they inspect, so 0.4.0 is a major-looking bump under a
0.3.x series rather than a patch.

## [Unreleased]

### Added

- **An independent JavaScript verifier** (`tools/verify-js/verify.mjs`): Node standard library only, no import of `uibc-core`, no npm package. It decides seven of the nineteen checks -- S1, S2, S4, S5, S7 (shape *and* the metadata digest), S11, S12 -- and refuses to pretend about the rest, so it never returns PASS. Measured against the same 34 packages: `strict 16/34 refused 29/34`, with an **identical FAIL set to Python on 10 packages** and the same expected check named on 11. Two implementations built from the spec, sharing no code, agreeing on what is broken and why.
- **`tools/cross_impl_check.py`** prints that comparison case by case, so the boundary is a number rather than a claim.
- **Two defects found by the exercise itself.** (a) The "one more declared evidence file" conformance package wrote its declaration under `files` instead of `entries`, so the file was undeclared while the name claimed otherwise; the case now grows the package through the shipped CLI. (b) The JS metadata-digest comparison caught an exception on an absent member and let a tampered note pass -- an `undefined` that Python writes as `null`. Both were caught only because a second implementation ran the same corpus.
- `tests/test_verify_js.py` (4 tests, skipped when Node is absent): a sound package must be INCONCLUSIVE, a flipped byte must fail S4, an edited root must fail S5, and every extra finding must come from a check the implementation claims to run.

### Added

- **The docs/ pages that describe the present now have to stay true.** `tools/check_doc_facts.py` scanned six top-level files; `docs/CONFORMANCE.md` said 305 tests, `docs/COMPOSITION-VERIFIER.md` said 180, `docs/ECOSYSTEM-MAP.md` and `docs/INTEROP-MATRIX.md` said 0.3.0 with 305 tests, all of them about the current project and all of them wrong. A page joins the check by saying so on its first lines, `<!-- facts: current -->`; the five present-tense pages that do are now scanned along with the six. Pages recording a past run (`REVIEW-LOG.md`, `RUN-RECORD-second-machine-20261118.md`) carry no marker and are left alone, because rewriting a run record's numbers would falsify history rather than correct it.
- **One checker bug fixed on the way.** `"15 red-team cases"` was matched by the `cases` rule against the *conformance package* count, so a correct sentence looked stale. Red-team cases now have their own key, and the generic `cases` rule is gone rather than guessed at.
- `tests/test_doc_facts.py` gained two assertions: a marked page that carries a wrong number must be caught, and an unmarked one must not be scanned.

### Added

- **Five positive vectors in the conformance suite**, so it measures correctness instead of pessimism. Twenty-nine packages had to be refused and nothing had to be accepted, which meant a verifier that refused everything scored 29/29 -- full marks for being useless. Now **29 refused + 5 accepted**: the shipped package untouched, the tree-and-chain / extended-evidence / checkpoint shapes appended correctly, and one case where an extra evidence file is added *and declared in the index* so S1 must not fail. Expected verdicts come from this repo's measured run.
- **The positive cases found a real gap at once.** Archived v0.2.1 refuses all 34, the five correct ones included: it cannot read the newer shapes, so its blanket refusal was hiding a forward-compatibility hole. A property of that older release, made visible by the suite.
- `tests/test_conformance.py` asserts that a verifier refusing everything fails every positive case. Measured: always-PASS 5/34, always-FAIL naming S1 1/34, current 34/34 (refused 29/34). Test count 513 -> 514; `docs/REPRODUCE.md` regenerated so its conformance row reads `strict 34/34 refused 29/34`.

### Added

- **`docs/REPRODUCE.md` and `tools/build_reproduce.py`** -- ten rows: the figure in the paper, the command a reader types, and the output recorded when the generator ran it. Every row has its own reader (JSON field, tail line, or regex) because six of the tools print progress before their figure, and taking the first line reported `{` for three of them. Latency here reads 1.367 ms against the paper's 1.225 ms, and the sheet says so rather than smoothing it: a figure from another host is another measurement.
- **`tests/test_reproduce.py`** -- 5 tests, including one that runs a real claim end to end and one that refuses placeholder output anywhere in the sheet.
- The published test count moved 508 -> 513 across README, README.en, AGENTS and the paper, as `check_doc_facts` requires.

### Fixed

- **The paper's own numbers were wrong in three places.** `paper/paper.md` claimed 122 tests (507 run), "three modules" within 24 files (25), and "zero-dependency (stdlib only)" when `[verify]` pulls in `cryptography` and `asn1crypto`. Rewritten to state the stdlib-only core, the optional extra, the INCONCLUSIVE-on-absence behaviour, 507 tests, and 25 modules. The skipped count is described rather than pinned, because it moves between 16 and 17.
- **`tools/check_doc_facts.py` now covers the paper and module counts.** `paper/paper.md` is a target, and `modules` is a measured fact, so a stale count there fails CI too.

### Fixed

- **The README's test count was 328; the suite runs 507.** Corrected in `README.md`, `README.en.md`, `AGENTS.md`, together with the skipped count (6 -> 16) and the recorded runtime.

### Added

- **`tools/check_doc_facts.py`** -- measures tests, checks, audit attacks, red-team cases and conformance vectors, then reads the documents a reader treats as current and reports every number that disagrees. Dated records under `docs/` are excluded on purpose: they are findings from a moment, and rewriting them would falsify a record rather than correct a claim. `--json` and `--files` supported.
- **`tests/test_doc_facts.py`** -- 4 tests: every fact is measurable, no published number is stale, a planted wrong number must be caught, and the two attack counts (36 audit / 15 red-team) must stay distinguishable. Adding a test without updating the README now turns CI red.

### Added

- **Rate limiting on the verify endpoint.** A token bucket per caller, `--rate`/`--burst`, `429` with `Retry-After`, and the limit advertised on `/health`. `X-Forwarded-For` is ignored unless `--trust-forwarded` is passed, because a bucket keyed on a caller-controlled header is not a bucket. Measured at burst 10: 11 of 320 calls under 16 concurrent clients succeeded, 309 refused.
- **`tools/stress_verify.py`** -- concurrency measurement, unlimited and limited in one run.
- **`deploy/`** -- a Dockerfile and instructions so a stranger can run their own endpoint; the image is untested here (no Docker on this machine) and the README says so.
- **`tests/test_rate_limit.py`** -- 8 tests, including the spoofed-header test.

### Added

- **Conformance suite.** 29 packages, each correct and then broken in exactly one way, with the checks a verifier must report. `tools/run_conformance.py --verify "<cmd>"` runs them against any implementation. Expectations come from the audit's measured run, so the suite cannot drift from the report. Measured: current implementation 29/29; archived v0.2.1 (6 checks) 0/29 while still refusing all 29; a verifier that refuses nothing scores 0. See `conformance/README.md`.
- **`tests/test_conformance.py`** -- 6 tests, including the archive-vs-manifest digest check and the rubber-stamp check.

### Added

- **`--strict` mode for S1.** `verify(pkg, strict=True)` and `uibc verify <pkg> --strict` fail any file under `evidence/` that the index never declared, while exempting the five structural members the format places there (`merkle.json`, `chain.json`, `anchors.json`, `policies.json`, `policies/*`). The default stays lenient, because a tightening that invalidates every existing package is a version change, not a fix. See `docs/STRICT-MODE.md`.
- **`tests/test_strict_mode.py`** -- 5 tests covering lenient, strict, exempt, clean, and the real CLI exit code.

- **`tools/build_thesis_tables.py` -> `docs/THESIS-CH5-TABLES.md`.** The six tables a chapter-5 could cite (checks and their basis, basis distribution, attack incidence summary, the two-implementation comparison, the three-channel coverage, the hot-path latency), each generated from the tools' JSON with a "how to regenerate" line beneath it, and an explicit section listing what the chapter must not claim.
- **`tests/test_thesis_tables.py`** -- 6 tests tying each table to the tool it reads.
### Added

- **`tools/check_matrix.py` -> `docs/CHECK-MATRIX.md` and `docs/CHECK-MATRIX.svg`.** Reads the audit's own JSON and prints which attacks move which checks. Two numbers fall out: 32 of 36 attacks isolate exactly one check, and no check is unreachable. The two attacks that move two checks (an impossible date also trips the lifecycle state machine; rewritten index metadata also moves the checkpoint head) are recorded rather than smoothed over.
- **`tests/test_check_matrix.py`** -- 6 tests holding those two claims.

### Fixed

- **The package reported its own version as 0.3.3 while shipping as 0.4.0.**
  `uibc_core/__init__.py` held a literal that had not moved with
  `pyproject.toml`, so every verification report stamped the wrong version. `tools/version_gate.py` now also reads that literal, making it a fourth
  place the gate compares rather than a fourth place to drift.
- **S15 lost its import during this work** and raised
  `NameError: _mk2 is not defined` on any package carrying an anchor; caught by
  the audit builder's own "a correct package must pass" assertion before it
  reached a commit.
- **S13 raised `IndexError` when an evidence file was deleted.** The declared
  order still listed the missing evidence, so `leaves[i]` ran past the end of
  the list the filesystem actually produced, and the exception was caught by
  the S0 fallback. The verdict was right (FAIL) but the reason was
  `IndexError: list index out of range`, which names neither the check nor the
  file. S13 now reports `proof names evidence 'files/action-log.txt' whose file
  is absent`.

### Added

- **Every check now carries its basis.** `uibc_core/basis.py` holds, for each
  check, whether a draft or RFC states the requirement (`direct`), the
  mechanism is borrowed from one (`related`), or this project defines it with
  nothing to point at (`none`) - and a citation for the first two, an empty
  string for the third. Rendered into every report as
  `checks[].basis = {class, citation, note}`.
- **`uibc explain <pkg>`** -- the same verifier, printed for a person: one line
  per check, then its class and citation, then the failure text. `verify` keeps
  emitting JSON unchanged, because scripts parse that and a citation four
  levels down in a JSON blob is not readable.
- **`tests/test_basis.py`** -- 8 tests: only documented classes carry a
  citation, `none` never does, an unknown id borrows nothing, and the shipped
  report matches the module.

- **`tools/compare_diagnostics.py` → `docs/DIAGNOSTICS.md`.** The same six
  kinds of damage applied to our package and to `agent-action-capsule` 0.17.0,
  printing what each verifier says *after* it says FAIL. On the four attacks
  both formats can express, we reported 13 specific reasons against their 5;
  the other two have no counterpart in their format, and are marked n/a rather
  than scored.
- **`tests/test_diagnostics_compare.py`** -- 5 tests, including one that fails
  on purpose if the documented gap (an uncommitted file under `evidence/` is
  only a note, never a failure) ever changes, so the doc cannot drift from
  reality.

### Not changed, on purpose

An attempt to make S1 fail on any uncommitted file under `evidence/` was
reverted: this format itself keeps the anchor event, the policy artefacts and
the receipt chain there, and the tightening failed a dozen existing packages.
That is a format-version change, not a patch.


### Added

- **Handover worked example (`examples/link3-handover-evidence/`):**
  the Link-3 handbook pack — the receiving-side check of a fictional
  device evidence set, in five runs (approved open PASS / approved
  pinned PASS / report swapped after sealing FAIL / rebuilt and
  re-sealed under a substitute key PASS unpinned / same pack FAIL
  pinned). Rebuilt with the released 0.3.3 so the `pip install`
  path reproduces every verdict; the folder README states the
  coverage=legacy scope of these seals in the verifier's own terms.
  Includes the plain-language verify guide (EN + Chinese) and the
  recorded run transcript.

- **Change-evidence worked example (`examples/link1-change-evidence/`):**
  the Link-1 handbook pack — a fictional device AI model update
  (v1.1 -> v1.2) handed downstream as a sealed four-file evidence set,
  in three states (sealed / evaluation report swapped after sealing /
  submitted unsealed) with verdicts PASS / FAIL (S4 names the swapped
  file) / INCONCLUSIVE and gate decisions ALLOW / DENY / HOLD. Built
  with the released 0.3.3 so the `pip install uibc-core` path
  reproduces every verdict; includes a plain-language verify guide
  (EN + Chinese) and the recorded run transcript.

- **AEE rail (`uibc_core/aee.py`): an external verifier for the
  Adversarial Execution Evidence in-toto predicate v0.7**, so the
  `agent-evidence-vectors` conformance corpus (288 vectors) can run
  against uibc-core: `python3 -m uibc_core.aee <statement.json>` under
  the corpus contract (exit 0 = valid; last stdout line one JSON report
  with verdict / codes / result / tiers; consumer key policy via
  `AEE_SUBSTRATE_KEYS`). GATE 0 well-formedness (strict I-JSON,
  vocabulary and corpus digests, coverage partition), GATE 1
  byte-checkable coverage validity (run-binding derivation v2, kind
  constraints, method cap), the 0.7 statement-level commitments, the
  total result recompute, and GATE 2 evidence tiers against pinned
  substrate keys (strict Ed25519). Stdlib only; the RFC 6962 batch root
  reuses `uibc_core.merkle`. Corpus result at build time: 288/288
  (63 accept / 223 reject / 2 indeterminate), reason parity on all
  rejects. Spot-checks live in `tests/test_aee_rail.py` (skipped when
  the corpus package is not installed).

### Fixed

- **Browser verifier (`verify.html`) brought back to parity with the CLI.**
  The page still implemented the v0.3.0 semantics: its seal payload covered
  identity+manifest only, so every package sealed since v1.1 (seal payload
  identity+manifest+lifecycle) failed S6 in the browser while passing
  `uibc verify`. The page now ports the 0.3.3 verifier check-for-check
  (S1–S18 in the reference report order, including S11 strict serialization,
  S12 semantic strictness, and the conditional S7/S10/S13–S18 surfaces),
  canonicalizes with RFC 8785 JCS like the CLI, accepts the legacy payload
  as `coverage=legacy`, supports a pinned checkpoint head (S9), and embeds
  a sample package built with the current release. A 27-run parity corpus
  ships in `tests/verify_html_parity/`; the page and the CLI agree on every
  check. Declared limit: S16 (RFC 3161 tokens) is INCONCLUSIVE on the page
  by design — the port does not parse DER tokens.

v0.3.0 below is the release cut on 2026-11-12: tag `v0.3.0`, GitHub Release published,
and `uibc-core 0.3.0` uploaded to PyPI on 2026-11-12 (sdist + wheel, same bytes as the CI build —
sha256 listed in `docs/pypi-0.3.0-release.md`). The release-triggered `publish-pypi.yml` run
`43150166821` still fails at the upload step because the trusted-publisher registration is not in
place; that workflow is a convenience path, not the only one.


## [0.3.0] — 2026-11-12


### ⚠️ VERDICT-AFFECTING (breaking in effect)

Per this project's own rule above, this release changes what produces
which verdict, in two connected moves. The full semantics are specified
in `docs/verdict-and-seal-semantics.md`.

**1. Three-valued verdicts.** Through 0.2.x the top-level result was
PASS unless a check FAILed, so an INCONCLUSIVE S6 (seal present but not
checkable in open mode) rode under a PASS. An external review (2026-11)
demonstrated the consequence: a fully self-consistent forgery verified
PASS in open mode. From 0.3.0: any FAIL → FAIL; else any INCONCLUSIVE →
INCONCLUSIVE; else PASS. Exactly three fixture cells changed — clean /
malicious / malicious-keyswap in open mode, PASS → INCONCLUSIVE. No
individual check outcome moved; the forgery is still not *detected*
without a key, it is simply no longer *passed*.

**2. Ed25519 public seals.** The v0.2 notes promised an asymmetric seal
for v0.3, pending a `cryptography` dependency decision. The decision
landed differently: Ed25519 (RFC 8032) is implemented in pure Python on
the standard library, and the project stays zero-dependency. An
Ed25519 seal records its public key in the package, so anyone can
verify provenance without the owner's secret (`uibc keygen --ed25519`,
`uibc submit --key`, `uibc verify --pubkey <pin>`). Reports gain an
`assurance` field: `public-key` / `owner-key` / `unattested`.

Also in this release: an unsigned package in open mode is INCONCLUSIVE
at S6 (was SKIP under PASS); `uibc demo` now runs the v0.3 arc
(stranger-verifies → tamper → forge-and-reseal → pinning catch);
`examples/` ships a committed sample package verifiable by any
stranger; the independent verifier mirrors the new semantics so the
two implementations still cross-check; gate HOLD now also results
from an unattested (unsigned) package in open mode.

Note: `CITATION.cff` / `codemeta.json` still pin the archived 0.2.1
artifact and its version DOI; they will be updated when the 0.3.0
archive is deposited.


### ⚠️ VERDICT-AFFECTING (breaking in effect) — released as 0.2.2

Per this project's own rule above, *a change to what produces which verifier
verdict is a breaking change*. This release contains one, in the **memory
migration verifier**:

| Input | Before | After |
|---|---|---|
| migration `target` contains a duplicate `memory_id` | `PASS` when the real entry happened to be kept by dict collapse — reported as "no injections" | `FAIL` / `MALFORMED_INPUT`; duplicate ids rejected on **both** sides |
| `source` and `target` both empty | `PASS` on all four Preservations | `INCONCLUSIVE` / `VACUOUS_INPUT` |

The patch number is used deliberately. `0.3.0` is already committed in the
public narrative to Ed25519 + a public key registry (the standing answer to the
`malicious-keyswap` boundary), and silently renumbering that promise would be a
more confusing change than an honest patch with this notice. **The substance is
breaking; this notice exists so nobody discovers it from a failing suite.**

> **Release status — which version number lives where.**
> `0.2.1` is **already published** (Zenodo DOI `10.5281/zenodo.22821835`; see
> `dist/`) and therefore must never be redefined. So this fix ships as `0.2.2`,
> and the files that describe the *published artifact* — `CITATION.cff`,
> `.zenodo.json`, `codemeta.json`, `dist/` — deliberately still read `0.2.1`.
> `__init__.py` and `pyproject.toml` carry the *working-tree* version.
>
> Consequence worth stating plainly: **the published `0.2.1` contains the two
> memory-migration gaps fixed here.** A `0.2.2` release should be published
> (the existing concept DOI supports "new version"), so that the version a
> researcher cites is not the one with a silent injection path. Publishing is
> an outbound, irreversible action and is left to the maintainer.

### Added
- `fixtures/generate_memory_fixtures.py` — a 22-case memory-migration mutation
  corpus (M0-M5), with the same hand-derived expectation matrix and non-zero
  exit gate as the package fixtures. It is what found the two defects above.
- `fixtures/_matrix_gate.py` — the comparison/rendering/gate logic shared by
  both fixture generators, so the two cannot drift apart.
- `tests/test_fixture_expectations.py` (16 tests) and
  `tests/test_memory_fixtures.py` (19 tests) — gate tests in both directions
  (green when the prior holds, red when it breaks) plus regression locks.
- `MEM_VERIFIER_VERSION` in `uibc_core/memory.py`, carried in every migration
  report so a rubric score can cite which verify produced it (SS31 field).

### Changed
- `fixtures/EXPECTED.md` and `README.md` no longer claim "S4 + S6 signature
  invalid" for the evidence-content mutations. A seal over
  `identity+manifest` cannot be invalidated by rewriting an evidence file, so
  S6 stays `PASS` in those cases and the detection comes from S4/S5/S3. The old
  wording described a defence that never fired.
- Memory migration reports now always carry a `result_code`
  (`OK` / `MALFORMED_INPUT` / `VACUOUS_INPUT`).

### Fixed
- Memory injection was possible through a duplicate `memory_id` in the target:
  the entry was collapsed away before comparison and the report still said
  "no injections" — a silent pass through M2 Fact Preservation (rubric weight
  0.30, the heaviest dimension).
- A migration of nothing scored `PASS` on all four Preservations.
- An empty field value (`{"content": ""}`) was reported as a *missing* field.

### Added
- `LICENSE` (Apache-2.0). Previously `pyproject.toml` declared Apache-2.0 but no
  licence file existed, and `CITATION.cff` warned against redistribution. This
  was a blocking gap for any standards or academic use; it is now closed.
- `codemeta.json` (CodeMeta 2.0) — required for indexing in the Software
  Heritage archive and for cross-repository software metadata exchange.
- `.zenodo.json` — per-deposit metadata so future Zenodo releases inherit the
  correct title, creators, ORCID, licence and keywords.
- `SECURITY.md` — scope, out-of-scope, supported versions, private reporting
  channel, and an explicit statement of the adversarial-testing posture.
- `CONTRIBUTING.md` — ground rules, the full local gate, what we want and what
  we decline.
- `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).
- `NOTICE` — third-party attribution.

### Changed
- `CITATION.cff` licence field now points at the real `LICENSE` file.

### Fixed
- `CITATION.cff`: replaced an unverified Software Heritage identifier with the
  values confirmed against the archive API (origin SWHID + snapshot SWHID), and
  corrected the neighbour-benchmark reference — the previous entry paraphrased
  the arXiv title instead of quoting it.
- `sbom.spdx.json` / `tools/gen-sbom.py`: SPDX 2.3 conformance. Element
  identifiers no longer contain underscores, the invalid
  `hasExtractedLicensingInfos` block was dropped (Apache-2.0 is on the SPDX
  licence list, so extracting it as a `licenseId` was wrong), and
  `licenseListVersion` now tracks the current list (3.29.0).
- `NOTICE`: removed a third-party company name from the redistribution note.
- `adapters/tencentdb-agent-memory/SPEC.md`: neutral wording for the runtime
  environment.
- Zenodo record `10.5281/zenodo.22821835`: metadata corrected from MIT to
  Apache-2.0 so the DOI-fixed artifact matches this repository, and the
  description now carries the canonical UIBC expansion and abstract. The
  deposited file bytes are unchanged; only metadata was corrected.
- All of the above came out of an independent three-way expert review
  (standards/compliance, endorsement channels, privacy and credential red
  lines). The review record is `docs/expert-review-2026-09-18.md`.

### Packaging / distribution (no verdict change)

- The MCP server now ships inside the package as `uibc_core.mcp_server`
  with a `uibc-mcp` console script, so `pip install uibc-core` is enough
  to run it; `mcp_server/server.py` remains as a compatibility shim.
- `verify_package` and `gate_check` MCP tools accept `pubkey_hex` to pin
  the expected Ed25519 signer (a substituted key FAILS S6), matching the
  CLI `--pubkey` behaviour.
- README (中文 / English) updated from v0.2.1 to v0.3.0; PyPI metadata
  description and development-status classifier updated to match.

---

## [0.2.1] — 2026-09-17

First publicly archived release. Triple-anchored: GitHub tag + OpenTimestamps
proof + Zenodo DOI.

- **Zenodo DOI:** version `10.5281/zenodo.22821835`, concept
  `10.5281/zenodo.22821834` (resolves to latest version).
- **OpenTimestamps:** `timestamps/uibc-core-0.2.1.zip.ots`, submitted to two
  independent calendars; upgrades to a Bitcoin block attestation on its own
  schedule.
- **Release artifact:** `dist/uibc-core-0.2.1.zip`,
  SHA-256 `59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4`.

### Added
- Read-only HTTP registry server (POST refused with 405; corrupt JSONL surfaces
  honestly rather than being swallowed). 9 tests.
- Static registry query page (`registry/index.html`).
- A2A adapter HTTP server — JSON-RPC 2.0 `card` / `verify` / `gate` / `inspect`,
  path-traversal rejection. 15 tests.
- `examples/showcase.py` + `SHOWCASE.md` — a full-lifecycle recorded run.
- `uibc_core/runtime.py` — one-line integration hooks
  (`record_action` / `seal` / `event` / `snapshot`). 9 tests.
- `README.en.md` — full English documentation.
- Contest package: charter, seven curated problems (P-01…P-07) mapped to
  `uibc-core` capabilities with AIGC provenance labels, weighted rubric
  (M2–M5, evidence-required scoring), submission spec with a verify-first gate,
  and a pilot-run record that includes honest tool limitations.
- Resident-benchmark charter v0.2: three-stage evaluation (machine gate →
  hidden set → top-submission re-run), `experiments/` append-only archive,
  starter kits, and a 10-competitor landscape review.

### Changed
- Test counts re-synced across `README.md`, `/ai/faq`, `llms.txt` and the
  manifest (the earlier `71` figure had drifted; the suite is now **115** unit
  cases plus 7 stress scenarios).
- `__version__` and `SPEC_VERSION` aligned to `0.2.1` so that verifier output
  reports match the released package.
- `uibc demo` step 6 now tampers *actual evidence content* instead of appending
  new evidence — the previous version could pass for the wrong reason.
- FAQ clarified the difference between `S6 SKIP` and `S6 INCONCLUSIVE`.
- `llms.txt` no longer implies Merkle-tree construction; the evidence root is a
  canonical hash over the ordered evidence set.

### Fixed
- External-audit findings: FAQ quickstart rewritten and verified command-by-
  command against the CLI; `docs/benchmarks.md` expectations aligned to
  `EXPECTED.md`; README gains an explicit test section; `submit` now returns a
  readable error for an unregistered package instead of failing obscurely.

---

## [0.2.0] — 2026-09-17

The release that closed the v0.1 blind spot.

### Added
- **Seal signatures** (HMAC-SHA256, provisional; Ed25519 planned for v0.3) —
  `seal_sign` / `seal_verify`, CLI `keygen` / `submit --key` / `verify --key`.
- Verifier **S6** with two modes: `open` (unsigned tolerated, verdict stated)
  and `strict` (unsigned or wrongly-keyed ⇒ FAIL).
- `malicious-keyswap` fixture, documenting the out-of-band key-pinning boundary.

### Fixed
- **Full forgery is now detected.** In v0.1, a package whose evidence was
  entirely fabricated verified as clean. `failure_corpus/` keeps the original
  case public rather than quietly patching it away.

### Notes
- Stress scenario `g` added to cover the signing path: 10k `seal_sign` /
  `seal_verify` throughput, and strict `S6` verification on a 500-entry package.
  Re-run live after v0.2: 7/7 OK.

---

## [0.1.0] — 2026-09-17

Initial proposal.

### Added
- Canonical serialization (provisional).
- Lifecycle state machine L1–L7.
- Verifier with scoped report (S1–S5). PASS is explicitly defined as "no
  violation found within the observed evidence boundary" — not absolute trust.
- CLI: `init` / `register` / `event` / `evidence` / `submit` / `verify` /
  `inspect`.
- `uibc demo` — build → seal → verify PASS → tamper → FAIL.
- Golden fixtures across 7 categories (clean / tampered / deleted / duplicated /
  reordered / migrated / malicious), with `EXPECTED.md` recording
  expected-vs-observed. The malicious full-forgery case was **UNDETECTED**; this
  is the documented motivation for v0.2 signatures.
- Determinism check: 7 independent builds produced an identical evidence root.
- Test hardening: 31 unit cases (including a stale-seal S5 regression) and a
  pre-push gate that was itself deliberately violated to confirm it blocks.

### Known issues at this version
- No signatures ⇒ malicious forgery undetected.
- No certificate, gate-decision, memory-migration or registry layer.


## 未发布 — 2026-11-25（修 did:web 策略随传输路径漂移，s02b 三例根因）

- **发现**：`assert_public_host`、禁降级 302、文档体积上限三处限制原先只写在 `_fetch_json` 里。
  任何**自带 fetcher** 的调用方（测试替身、bench 的本地服务用例、适配器）从 `resolve()` 进来时，
  `did:web:127.0.0.1` 会被正常解析——限制"生效与否"取决于哪条代码路径搬字节。这正是 issue #434
  里三个用例 Linux PASS / Windows FAIL 的根因，不是平台差异。
- **修法**：把主机策略与体积上限搬进 `resolve()` 的解析契约（loopback/私网/`.local` 一律拒；返回的文档按
  UTF-8 序列化后超过 2 MiB 一律拒），传输层 `_fetch_json` 保留原检查作为纵深防御。
- 降级 302 仍只能在传输层拒绝（注入 fetcher 时看不到重定向）；这一点在测试与文档里明说，不假装覆盖。
- 新增 `tests/test_did_web_policy.py`（6 条）：注入 fetcher 的 loopback / 私网 / localhost 一律拒，
  公网照常；2.2 MB 文档拒绝、1.5 MB 接受。
