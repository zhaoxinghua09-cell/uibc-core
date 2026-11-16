# ADR-001: Three-valued top-level verdict (PASS / INCONCLUSIVE / FAIL)

- Status: Accepted
- Date: 2026-11-17
- Supersedes: the implicit two-valued semantics of v0.2
- Normative text: `docs/verdict-and-seal-semantics.md`

## Context

Through v0.2 the top-level verdict was two-valued: a package passed unless some check failed. S6 (seal signature) is INCONCLUSIVE in open mode — no key given and none pinned — so that fact appeared only in the report's detail lines.

An external review in 2026-11 demonstrated the consequence: a fully self-consistent forgery — evidence rewritten, index hashes and `evidence_root` recomputed — verified **PASS** in open mode. Nothing in the package could contradict it, and the one check that spoke to provenance could not be resolved.

The detail line was accurate. The verdict was not. Any consumer reading only `verdict` drew a false conclusion, and consumers read only `verdict` — that is what a top-level field is for.

## Decision

Make INCONCLUSIVE a first-class top-level value:

| Condition | Verdict |
|---|---|
| any check FAIL | FAIL |
| else any check INCONCLUSIVE | INCONCLUSIVE |
| else | PASS |

PASS is reserved for packages where every applicable check actually resolved. SKIP remains available only where a check does not apply at all, and SKIP does not block PASS.

## Consequences

**Good.** An unresolved provenance check can no longer ride under PASS. A consumer who reads a single field now gets a truthful answer. The three certificate-mode fixtures that changed are all in open mode and all at the top level only — no individual check outcome moved, so the change is behaviourally narrow and verifiable from the fixture matrix.

**Costs.** Exit codes and downstream automation that treated "not FAIL" as success must be updated. Some previously green runs now report INCONCLUSIVE, which is the point, but it is still churn.

**Risk accepted.** INCONCLUSIVE may be read as "suspicious" rather than "unknown". Mitigation: reports state which check was unresolved and what would resolve it (pin a key, supply a registry record).

## Alternatives considered and rejected

1. **Keep two values, strengthen the detail lines.** Rejected: the demonstrated defect was not in the detail but in the summary field, and consumers legitimately read the summary.
2. **Treat open-mode verification as always FAIL.** Rejected: verification without a key legitimately establishes integrity, and calling that a failure would be its own false statement.
3. **Add a fourth value, UNTRUSTED.** Rejected: "no key available" is unknown, not adverse. Conflating the two is how audit trails lose credibility.

## Related

- `docs/verdict-and-seal-semantics.md` — normative statement, including the v0.2→v0.3 fixture delta
- `fixtures/EXPECTED.md` — the pinned outcome matrix
- `independent_verifier/` — second implementation written against the text, not against this code

---

# ADR-001：顶层判定改为三值

- 状态：已采纳
- 日期：2026-11-17
- 取代：v0.2 的隐含二值语义
- 规范文本：`docs/verdict-and-seal-semantics.md`

## 背景

v0.2 的顶层判定是二值：除非某项检查失败，否则通过。S6（封签签名）在开放模式（无钥匙、未钉住）下是 INCONCLUSIVE，而这个事实只出现在报告的详情行里。

2026-11 的外部评审给出了后果：一个完全自洽的伪造件——证据被改写、索引哈希与 `evidence_root` 全部重算——在开放模式下被判定为 **PASS**。包里没有任何东西能反驳它，而唯一与来源有关的检查无法解决。

详情行是准确的，判定不是。只读 `verdict` 的消费者会得出错误结论——而消费者只会读 `verdict`，那正是顶层字段的用途。

## 决定

把 INCONCLUSIVE 提升为顶层取值：任一 FAIL → FAIL；否则任一 INCONCLUSIVE → INCONCLUSIVE；否则 PASS。PASS 只留给每一项适用检查都真正解决的包。SKIP 仍只用于"该项根本不适用"，且不阻断 PASS。

## 后果

**收益**：未解决的来源检查不能再藏在 PASS 下面；只读一个字段的消费者得到真实答案。变化只涉及开放模式下的三个夹具单元，且只在顶层体现——单项检查结果一个都没变，因此改动窄、可核。

**代价**：把"非 FAIL 即成功"当成功的退出码与下游自动化必须改；一些原本绿灯的运行会变成 INCONCLUSIVE，这正是目的，但仍是变更成本。

**接受的风险**：INCONCLUSIVE 可能被读成"可疑"而不是"未知"。缓解：报告必须写明"哪一项未解决、怎样才能解决"（钉住钥匙、提供登记记录）。

## 已考虑并否决的方案

1. **保持二值、加强详情行**——否决：被实证的缺陷不在详情，而在汇总字段。
2. **开放模式一律判 FAIL**——否决：无钥匙验证确实能证明完整性，把完整性叫失败本身又是一句假话。
3. **加第四个值 UNTRUSTED**——否决："拿不到钥匙"是未知，不是不利；把两者混起来，审计链就会失去可信度。
