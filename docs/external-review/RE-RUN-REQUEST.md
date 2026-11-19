# Re-run request to external node 001 — draft, unsent

Status: **draft, unsent** (as of 2026-11-19). Nothing here has been sent. Sending
requires explicit approval from the maintainer.

Addressed to: Wang Guigui (Correctover — AI Reliability), who ran the suite on
`8a95747` on 2026-11-19 and reported two disagreements.

---

## Subject

`Second run, same host: the two rows you found are now a standing check — would you re-run on today's main?`

## Body

Hello Wang,

Thank you for the run. Two things in your reply were worth more than a clean one would have been: you found the `fixture:duplicated` divergence on S4 and S5, and you then went to `refs/pull/169/head` on your own and confirmed it was fixed there. Nobody asked you to do the second half.

What changed since:

- The fix is in `main` (`#186`).
- Your two rows are now a **standing check**: `tools/external_node_regression.py` re-runs that comparison and fails if the two implementations ever disagree on `fixture:duplicated` again. It is item 9 of 9 in `tools/run_all_evidence.py`, so a regression there turns the project's published evidence number red.
- The record page is `docs/external-review/EXTERNAL-NODE-001.md`. It quotes your numbers, keeps the bug you found, and keeps the limits: you are a correspondent in the same W3C working group, so this is third-party execution and not third-party interest; one node is a node, not a sample; and it arrived because we asked.

## The request (small, and refusable)

If you have ten minutes, run today's `main` on the same host:

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core
cd uibc-core
python -m unittest discover tests
python independent_verifier/cross_check.py
```

and reply with three things:

1. the `Ran N tests ... OK (skipped=M)` line;
2. the `checks compared: ..., mismatches: ...` line and the `AGREEMENT:` line;
3. `git rev-parse HEAD` at the time you ran it.

If any of it fails, send the failure and not an apology — a second run that finds something is worth more to us than one that passes.

## What we will and will not write

- We will record it as a second run by the same operator on the same host, across two versions: your first run found the defect, the second confirms the repair. That is a verification line, not a second node; we will say so.
- We will not describe you as endorsing, supporting, or approving this repository, and we will not call the count higher than it is: outer nodes become 1, and stay 1.
- If you would rather not run it, that changes nothing in the record; the first run stands on its own.

Thank you,
Xinghua Zhao

---

## 中文附注（内部，不外发）

- 用途：把"一次回执"补成"同一外部人、同一台机器、跨两个版本"的验证线；这是目前**唯一不需要新人、不需要新授权**的推进。
- 请求刻意极小：三条命令、三个数字、一个 commit id；并明确写了"可以拒绝"。
- 若他跑了并报出问题，按 `standards-participation-gate` 铁律 6 处理：状态类数字要自取、带时点、回读比对，不能拿他的一句话当已核验事实。
- 发送前需要：(1) 用户明确许可；(2) 复核三条命令在当天 `main` 上确实可跑（本轮已跑：`9 ok, 0 failed, 0 skipped, 22.759 s`）。
