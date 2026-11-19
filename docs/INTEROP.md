# 跨界复算：两边互相跑对方的语料（2026-11-20）

**可复算**：`python3 tools/oracle_check.py --emit` 生成我方 28 例；EATF 侧为公开仓库 `github.com/tyche-institute/eatf-verifier`（Apache-2.0），本轮在本机克隆并装入独立 venv 实跑。

## 先说我方自己得的低分

| 方向 | 输入 | 结果 |
|---|---|---|
| 我方第二实现 → EATF 13 例 | 5 个他们的 valid / 8 个他们的 invalid | **修复前：13 个里 8 个"结果相同"、5 个 valid 全判 FAIL** |
| EATF 验证器 → 我方 28 例 | 目录打成的 `.aep` | **28 个全部 false，诊断同一句：`AEP entries must use flat, safe names`** |

两边都没有崩溃、没有静默通过——这一点双方都做到了。但数字本身很难看：如果只数"通过率"，我方在他们的 valid 上是 **0/5**，他们在我们的 28 例上是 **0/28**。

**原因不是判错，是容器不同。** 他们是单文件 `.aep`（zip，条目必须平铺：`canonical.bin`/`metadata.json`/`signature.sig`…），我们是目录树（`manifest.json`/`identity.json`/`lifecycle.json`/`evidence/index.json`/`signatures/seal.json`）。谁也读不了对方的包，所以任何"我们比他们强"的结论都不能从这个交叉跑里得出来。

## 本轮因此改了什么（我方唯一实质改进）

修复前：拿到一个根本不是 UIBC 包的目录，我方第二实现回 **FAIL**。那是在对一个自己没读过的格式下 affirmative 断言。

修复后：`independent_verify` 先看容器——`manifest.json`/`identity.json`/`lifecycle.json`/`evidence/index.json` 一个都没有时，直接回 **INCONCLUSIVE** + `unsupported: "not-a-uibc-package"`，`checked` 为空，并写明"未提供 UIBC 包，因此两个方向都不给判词"。

修复后重跑 EATF 13 例：**13 个全部 declined**，`unsupported` 同一句。这不是分数变好，是把"错判成 FAIL"换成"明说判不了"。

## 这条能说明什么、不能说明什么

**能说明**：
- 双方都对外发布了机器可跑的语料与预期判词（他们 `test-vectors/README.md` 写 `5 verified, 8 rejected, 0 contract mismatches`，我们 `conformance/oracle/expected.json` 写 28 例的 `expected_verdict`/`expected_first_fail`）；本轮在本机把他们的 5/8 亲手复现了一遍（`Conformance: 5 verified, 8 rejected, 0 contract mismatches`），不靠引用。
- 双方对"外来容器"都拒绝而不是误判——他们给的是可读诊断，我们修完之后给的是 `INCONCLUSIVE` + 具名原因。
- 我方语料比他们多：28 vs 13；且我方要求每条 reject 说明"依据的是哪条原文"，他们只要求布尔一致（这是设计目标差异，不是高下）。

**不能说明**：
- 不能在**同一批包**上比准确率——没有共享容器，交叉跑得不出准确率，只能得出"互不兼容"。
- 不能说我们的判词更强：他们的 README 也不声称可判别全部 AI Act 条款，我们的 20 项里语料只触达 15 项。
- 不能说"已独立验证"：这是我方自己跑去跑别人，不是第三方跑我们。

## 若要真的可比，还缺什么

一份双方都能读的容器。可选三条路，按成本排序：

1. **适配层**：我方写一个 `.aep` → UIBC 目录的转换器（或反向），把 EATF 的 13 例转成 UIBC 包，两边各自跑一遍同一批语义事件。这需要读他们的 `canonical.bin` 结构，成本约一人日。
2. **共用语料捐赠**：把对方的 13 例作为附带来源写进我方语料，标 `borrowed_vectors`，只跑"能不能识别容器外的篡改"这一层。
3. **等他们先动**：这条路最省，但也最慢，且不改变"互不兼容"的事实。

在那之前，对外只能说：**两边都有公开、可离线复跑的语料；两边的容器互不兼容；我方在自己容器内的预期判词是 28 例、逐条带依据，本轮已实测 `exact 22 / declined 6 / wrong 0`。**

## 第一条路已经走了：`tools/aep_to_uibc.py`（2026-11-20 同日）

转换器的语义只有一条：**载荷字节和它被记录的 SHA-256 一起搬过去**。搬完之后：

| 故障类别（他们的 8 个 invalid） | 能不能搬进 UIBC | 参考实现 | 第二实现 |
|---|---|---|---|
| `tampered-canonical-bin` | 能（载荷被改） | FAIL | FAIL |
| `missing-canonical-bin` | 能（载荷缺失） | FAIL | FAIL |
| `tampered-metadata` | 能（元数据被改） | FAIL | FAIL |
| `bad-signature-classical` | 不能（签名对象不同） | — | — |
| `bad-signature-pqc` | 不能（ML-DSA 无对应槽） | — | — |
| `untrusted-issuer` | 不能（转换后由我方签，无可不信之 issuer） | — | — |
| `bad-timestamp` | 不能（DER 令牌 vs JSON 信封槽） | — | — |
| `tampered-overt-receipt` | 不能（OVERT 对象 vs 我方 receipt schema） | — | — |

5 个 valid 全部转换成功，两个实现都回 **PASS**（`python tools/aep_to_uibc.py --measure <test-vectors> <work>` 实测：`5 PASS/PASS`、`3 FAIL/FAIL`、`5 declined`）。

**这条数字的意义要说准**：能搬的 3 类，是两个容器都表达"载荷/哈希不一致"的类别，判对是应有之义；**5 类搬不过去是因为我方没有对应的信封**，不是他们判得比我们细。所以这张表仍然不能用来宣称"更准"。它能说明的只有一句：**一旦把载荷搬进同一容器，两套实现在同一批证据上给出一致判词**——这是第一处真正的同批比较。

**仍缺**：把 RFC 3161 令牌和 OVERT 收据映射成我方信封（需要一份字段对照，本轮未做）。做完之后，8 类故障才能全部同批比较。

## 补做之后的结论：不是缺解析器，是签的不是同一个对象

字段对照做不下去，原因在字节级，`docs/BINDING.md` 记了实测：解析他们 13 个包的 `timestamp.tsr`，可解析 12 个，其中 **12/12 的 imprint 等于 `hash.sha256` 文件里的值，10/13 等于 `sha256(canonical.bin)`**——他们的第三方时间戳签的是**载荷摘要**；我方 S16 要求令牌覆盖**包链头**（生命周期+证据根+索引派生）。

所以一个完好无损的 EATF 包搬进 UIBC 后，字节全对、S16 仍然会判"未覆盖本包链头"。两种设计各有代价，谁也不是"更严"：他们用签名+收据补绑定，代价是多对象；我们用一个 head 换掉，代价是包定稿后才能锚。

要让 8 类全部同批比较，唯一诚实的路是**让同一个 TSA 给两边的 head 各签一次**，或提出"绑定中立"的令牌格式（subject 是一组 `(格式, 摘要)` 对）。这是对外议题，不是本轮能自证的。

