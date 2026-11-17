# SUCCESSION — how someone else takes this over

This file exists so that maintenance does not depend on one person. It is deliberately honest about what is still missing.

## Current state (2026-11-17)

| Role | Named? |
|---|---|
| Maintainer | Yes — see `.github/CODEOWNERS` |
| Successor | **No.** This is the known gap, stated rather than papered over. |
| Decision authority for releases | The maintainer, unassisted |

**Bus factor: 1.** Every repository in this project has a CODEOWNERS entry, and none has a second named person. If the maintainer becomes unavailable, the code continues to exist and to verify — but no one is authorised to cut a release, and no one has been told what to check first. That is the single largest structural risk here, larger than any technical debt in this repository.

## What a successor needs, in order

1. **Read `QUICKSTART.md` and run `python -m uibc_core.cli demo`.** Ten minutes. The eight steps are the whole product in miniature.
2. **Read `docs/verdict-and-seal-semantics.md`.** This is normative. If the code and the text disagree, one of them is a defect; do not assume the code is right.
3. **Run `fixtures/EXPECTED.md` against the code.** Every expected outcome is pinned. A diff here is a release blocker, not a style question.
4. **Read `docs/adr/` before changing behaviour.** Decisions are recorded with the alternative rejected; re-litigating them without reading them is how regressions get reintroduced.
5. **Check the second implementation under `independent_verifier/`.** It is written against the text, not against this code. Disagreement between them is the most valuable signal this project produces.

## Release checklist (copy this, do not improvise)

- [ ] Demo runs end to end; steps 5–8 produce the expected four different outcomes
- [ ] Fixture matrix matches `fixtures/EXPECTED.md` exactly
- [ ] Second implementation agrees on the same fixtures
- [ ] Package / policy / engine versions bumped together; evidence records them
- [ ] `CHANGELOG.md` states what changed in verdict semantics, if anything
- [ ] Claims in README still match what the code does — no "first", "certified", "independently verified"

## Recovery runbook

Nothing here is destructive; all of it is reproducible from the repository alone.

1. No key, no package? Run `demo` — it builds a fresh package in a temporary directory and prints the path.
2. Verification disagrees with the fixture matrix? Check `git log` on `uibc_core/`; a semantic change without an ADR is the usual cause.
3. Lost the owner key for a real package? The package remains verifiable in open mode (integrity only) and becomes UNKNOWN on provenance — it is not recoverable by re-signing, because re-signing changes the seal, and the seal is the claim.
4. Disagreement with a third party about a verdict? Give them the package plus the pinned `.pub`. The verdict is reproducible by anyone; that is the design.

## What the successor may not do without an explicit decision

- Change what PASS means, or reintroduce a two-valued verdict
- Accept a package where an applicable check was unresolved
- Describe this project as certified, accredited, independently verified, or in production use
- Publish a competitive format rather than a verifier of existing formats

---

# 接替说明 — 别人怎么接手

本文件存在的目的是让维护不依赖单个人。它对"仍然缺什么"是诚实写明的。

## 现状（2026-11-17）

| 角色 | 是否已指定 |
|---|---|
维护人 | 是——见 `.github/CODEOWNERS` |
接替人 | **否。这是已知缺口，写出来而不是糊过去。** |
发布决定权 | 仅维护人一人 |

**Bus factor = 1。** 本项目每个仓库都有 CODEOWNERS，但没有一个有第二个人名。若维护人不可用：代码仍在、仍可验证，但**没有人被授权发版，也没有人被告知先查什么**。这是本项目最大的结构性风险，比本仓任何技术债都大。

## 接替者按此顺序做

1. 读 `QUICKSTART.md` 并跑 `python -m uibc_core.cli demo`（十分钟，八步就是整个产品的缩影）；
2. 读 `docs/verdict-and-seal-semantics.md`——它是规范性的；代码与文本冲突时，必有一方是缺陷，不要默认代码正确；
3. 用 `fixtures/EXPECTED.md` 对代码跑一遍；这里出现差异是发版阻断项，不是风格问题；
4. 改行为之前读 `docs/adr/`；不读就重新争论已决事项，正是回归的来源；
5. 看 `independent_verifier/`：它是照文本写的、不是照这份代码写的，两者不一致是这项目最有价值的信号。

## 发版清单（照抄，不要临场发挥）

- [ ] demo 端到端跑通，5–8 步给出四个不同结果
- [ ] 夹具矩阵与 `fixtures/EXPECTED.md` 完全一致
- [ ] 第二实现与同一批夹具一致
- [ ] 包/策略/引擎版本同步提升，且写入证据
- [ ] `CHANGELOG.md` 写明判定语义有无变化
- [ ] README 的主张与代码实际相符——不得出现"首个""已认证""已独立验证"

## 恢复手册

以下都不破坏数据，且全部可从仓库本身复现。

1. **没钥匙、没包**：跑 `demo`，它会在临时目录建一个新包并打印路径。
2. **验证结果与夹具矩阵不符**：查 `uibc_core/` 的 `git log`；无 ADR 的语义改动是常见原因。
3. **真实包的 owner 钥匙丢了**：包仍可在开放模式验完整性，来源变 UNKNOWN；**不能靠重签恢复**——重签会改变封签，而封签本身就是那项主张。
4. **与他人对判定有分歧**：给出包 + 钉住的 `.pub`。判定任何人都可复现，这就是设计。

## 接替人未经明确决定不得做的事

- 改变 PASS 的含义，或恢复二值判定
- 接受"存在未解决检查"的包
- 把本项目描述为已认证、已获资质、已独立验证或已在生产使用
- 发布一套竞争性新格式，而不是验证既有格式的验证器
