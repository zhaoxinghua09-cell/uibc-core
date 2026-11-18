# 判定之外，它还说了什么

同一批六种破坏，分别施加到本仓库的包与竞品的 capsule。比的是**同一个 FAIL 之后的信息量**：能不能说出哪一项、哪个对象、期望什么。

| 攻击 | 我们：判定 | 我们：检查项 | 我们：一句原因 | 他们：判定 | 他们：错误码 | 他们：一句原因 |
|---|---|---|---|---|---|---|
| flip one byte in evidence | FAIL | S4, S13, S15, S8 | 2 entries checked; hash mismatch on 'files/action-log.txt' | FAIL | capsule_id_mismatch | capsule_id_mismatch: recomputed bb33a44ce57cdb781ac500022f9d7f8c84677d73f8abfbecad2ea4ef01 |
| delete one evidence file | FAIL | S4, S13, S8 | 2 entries checked; missing file 'files/action-log.txt' | n/a | — | 该格式没有证据文件集，只有一个 capsule |
| add an undeclared file | INCONCLUSIVE | — | No violation was detected, but verification is incomplete: at least one check could not be | n/a | — | 该格式没有可另加的成员集合，未声明字段即被 capsule_id 掩盖 |
| impossible date (2026-02-30) | FAIL | S3, S12 | L8 event 0 has no parsible ISO-8601 timestamp ('2026-02-30T00:00:00Z') | FAIL | capsule_id_mismatch | capsule_id_mismatch: recomputed ce991259bc9dd8cc80cf17b174098ad163421ccf2efd2cf2dcb882b00c |
| edit index metadata | FAIL | S7, S8 | evidence/index.json metadata does not match the sealed evidence_index_digest (expected sha | FAIL | capsule_id_mismatch | capsule_id_mismatch: recomputed b6a2252bbb879212bff8774c9bb1db0624c79631d10c7f04adcd29a362 |
| drop the last index entry | FAIL | S13, S15, S7, S8, S5 | declared size 2 != 1 evidence leaves; declared root does not match recomputed root; inclus | FAIL | missing_required_field, capsule_id_mismatch | missing_required_field: operator is REQUIRED (§5.1) |

在双方语义都成立的 4 类攻击下，我们共报出 **13** 条具体原因，他们报出 **5** 条。

## 这一轮试过、又撤回的改动

把「`evidence/` 下出现未声明文件即判 FAIL」写进 S1，跑测试时**十几个既有包全部失败**——因为这个格式自己就把锚定事件、策略件、收据链放在 `evidence/` 下。这说明它不是一处补丁，而是一次格式版本变更，已原样撤回。所以上表第二类攻击在这里是 `INCONCLUSIVE`，**这是我们已知的缺口，不是对比的胜利**。

## 这份对比不能说明什么

- 两种格式不同，六个攻击只是语义对齐，不是逐字节等价。
- 竞品的条款引用（§5.1）是他们比我们强的地方：我们的 `detail` 说「哪一项、期望什么」，但没有说「依据哪条」。写论文时这点要照实写。
- 次数多不等于更好；一条能定位到字节的原因，胜过十条泛泛的拒绝。

