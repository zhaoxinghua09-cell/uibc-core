# Anchor dependency of the mutation suite

Source: `submissions/uibc-core@0.4.0.json` (commit `21f3abd`), read at generation time. `A` = accepted (attack succeeded), `R` = rejected.

| # | mutation | open (no anchor) | pinned (trust anchor) | head-pinned (trust + freshness) |
|---|---|---|---|---|
| 1 | M01 manifest.agent_id | R | R | R |
| 2 | M02 manifest.evidence_root | R | R | R |
| 3 | M03 manifest.agent_version | R | R | R |
| 4 | M04 manifest.status | R | R | R |
| 5 | M05 manifest 增字段 | R | R | R |
| 6 | M06 identity.owner | R | R | R |
| 7 | M07 identity.agent_type | R | R | R |
| 8 | M08 lifecycle 时间戳 | R | R | R |
| 9 | M09 lifecycle actor | R | R | R |
| 10 | M10 lifecycle 删首事件 | R | R | R |
| 11 | M11 lifecycle 插入事件 | R | R | R |
| 12 | M12 证据内容改 1 字节 | R | R | R |
| 13 | M13 证据扩表 | R | R | R |
| 14 | M14 证据删条 | R | R | R |
| 15 | M15 证据删文件 | R | R | R |
| 16 | M16 封签改 1 字节 | R | R | R |
| 17 | M17 换钥重签（keyswap） | **A** | R | R |
| 18 | M18 包内外挂文件 | R | R | R |
| 19 | M19 索引元数据 | R | R | R |
| 20 | M20 整包回滚（装在旧包） | **A** | **A** | R |
| 21 | M21 未封签包截断尾部 | R | R | R |

## What each anchor actually buys

- No anchor needed: **19 of 21** cases are rejected with nothing trusted — they are self-contained integrity failures.
- Trust anchor buys: **1** case(s) — M17 换钥重签（keyswap）. Pinning the signer's key detects a re-signed package only because the key no longer matches.
- Freshness anchor buys: **1** case(s) — M20 整包回滚（装在旧包）. A pinned key still accepts a valid package from an earlier point in time; only an expected-head comparison catches that.

The point is the shape, not the scores: an anchor buys exactly the attack class it names, one case each, and buys nothing else. Key pinning does not buy freshness, and freshness does not buy authenticity.
