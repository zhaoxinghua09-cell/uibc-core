# 并发：200 次并发记录，原来只留下 28 条

`2026-11-18`｜发现 → 修复 → 回归测试，同一个 PR

---

## 怎么发现的

矩阵里一直写着"未测并发"。这次不再写说明了，直接测：8 个线程、每线程 25 次 `record()`，都写进同一个包。

**第一次结果：**

| 指标 | 值 |
|---|---|
| 期望条目 | 200 |
| index 实际 | **28** |
| 磁盘文件 | 129 |
| 异常 | **69**（`JSONDecodeError`、`Extra data`） |
| 最终 `verify()` | **FAIL**（S2 FAIL、S4 FAIL、S5 INCONCLUSIVE） |

**86% 的证据被静默丢弃，且包验不过。** 这不是性能问题，是证据完整性问题——一个会因为并发而丢证据的日志系统，不能承担"证明发生过什么"的职责。

## 第二个 bug：`register` 说成功，但 manifest 没写

修第一个 bug 之后，新包仍然 S2 FAIL。追下去发现：

`cmd_register` 打印 `registered agent 'agent'`，写了 `identity.json` 和 `lifecycle.json`，**唯独没写 `manifest.json`**——manifest 还停在 `cmd_init` 的骨架（只有 `_note` 和 `schema`）。

而 S2 比的是 `manifest.agent_id` 与 `identity.agent_id`，S5 比的是 `manifest.evidence_root` 与重算值。两者都是 `None` → FAIL。

**这个 bug 一直存在，之前所有测试都在用成品 fixture，没人看见。** 也就是说：任何人按 README 走 `init` + `register`，拿到的包开箱就是验不过的。

## 修法

**① 包级文件锁**（`uibc_core/locking.py`，零依赖）

`evidence/.lock`，POSIX 用 `fcntl.flock(LOCK_EX|LOCK_NB)` + 短轮询，Windows 用 `msvcrt.locking`。读、复制、追加、写回**作为一个临界区**。

没有可用锁原语时**直接抛 `LockTimeout`**，而不是假装上锁——一个以为自己持有锁的调用者，比一个知道自己没锁的更危险。

**② 原子写**

`lock → 写同目录临时文件 → os.replace`。读者只会看到旧文件或新文件，不会看到半个 JSON。

**③ 回填 manifest**

`register` 在锁内写完整 manifest（`agent_id`、`agent_version`、`created_at`、`evidence_count`、`evidence_root`、`status`），其中 root 由**空索引的真实哈希**算出，不是填空。

**④ 文件名冲突检测改为循环**

`while os.path.exists(dst)` —— 在锁内它已经安全，但保留循环是为了锁不可用时的降级不崩。

## 修复后实测

| 指标 | 修复前 | 修复后 |
|---|---|---|
| index 条目（期望 200） | 28 | **200** |
| 磁盘文件 | 129 | **200** |
| 异常 | 69 | **0** |
| 临时文件残留 | — | **0** |
| `seal()` 后 verify | FAIL | **INCONCLUSIVE**（S1–S5、S7、S8、S11、S12 全 PASS；S6 因未签名而 INCONCLUSIVE） |

`seal()` 仍是必需的一步：记录会移动 root，封签才发布新 root。这是设计，不是补丁。

## 剩余限制（写在代码里的也要写在这里）

- **锁是 advisory（建议锁）**：它约束愿意遵守它的写者。NFS/SMB 之类不完全遵守 flock 的挂载点上，跨进程保护不成立。
- ~~**Windows 分支未经实跑**~~ → **已在真实 Windows 上跑过**（Python 3.13.18/win32，`msvcrt: True`，并发 200/200 与审计 6 项全过），见 `docs/CROSS-PLATFORM.md`。
- **多进程未测**：测的是多线程。多进程理论上由同一个锁文件保护，但没有实测数据。
- **性能代价未单独量化**：锁内做复制与哈希，串行化后吞吐必然低于无锁。没有并发的场景不受影响（单写者不竞争）。

## 复跑

```bash
python3 -m unittest tests.test_concurrency_and_build -v   # 2 项
```

测试断言四件事：`register` 后 manifest 有真 root；200 条一条不少；路径不重复；封签后 S1–S5 全 PASS 且 S6 仍是 INCONCLUSIVE。
