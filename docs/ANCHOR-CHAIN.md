# 回滚：一份完全正确但过时的锚

一个锚回答"这是发布方签的那个包、那个状态吗？"它回答不了"这是**最新**的状态吗"。

昨天那个包与它那个锚，彼此完全自洽，永远如此 —— 因为它们是同一次发布的两半。攻击者把这两半一起交出去，每一项检查都会点头。

修法很小，也很老：**让每个锚说出它前面是谁。**

```json
"seq": 3,
"prev_anchor_digest": "6ea89f63ad52830b4a33bf268e72481fb844d4a9dd519f662dbe81e8a5992374"
```

| 字段 | 含义 | 规则 |
|---|---|---|
| `seq` | 在线上的位置，从 1 开始 | 正整数、不重用、不跳号 |
| `prev_anchor_digest` | 前一个锚的 `anchor_digest` | seq 1 必须为 null；seq>1 必须等于前一锚的摘要 |

顺序，是摘要从来没有过的那样东西。

## 一条命令看一条链

```
$ python3 tools/anchor_chain.py anchors/
VERDICT: CHAIN OK
anchors: 3 (seq 1..3)
   1  001.json  head sha256:2935c3f497b00
   2  002.json  head sha256:1d4c...
   3  003.json  head sha256:8f71...
```

## 六条拒绝，全部有测试

| 情形 | 判定 | 为什么 |
|---|---|---|
| 缺中间一个 | CHAIN BROKEN | 有缺口就不是链 |
| 同一 seq 出现两次 | CHAIN BROKEN | 有人把旧锚换了个文件名 |
| `prev_anchor_digest` 被改写 | CHAIN BROKEN | 链被重写，或锚被就地替换 |
| seq 1 却声明前驱 | CHAIN BROKEN | 第一个锚前面没有东西 |
| 目录只到 seq 3，而调用方已知 seq 5 存在 | **STALE**（退出码 5） | 不是"链短"，是**新锚被藏起来了** |
| 拿旧锚去比对新锚（`--prev`） | FAILED | 回滚被当场抓住 |

最后一行对应真正的攻击：陌生人同时收到 seq 1 的包和锚，而调用方手里已有 seq 2 —— `anchor_check.py --prev` 一比对就失败，因为**第一个锚说自己是第一个，可调用方手上已经有第二个了。**

`STALE` 这个词是刻意的：链短不一定是没发布，可能是**被扣下了**。这两种情况对检查者一样危险，所以给同一个词。

## 它做不到的，说清楚

**扣留拦不住。** 谁能控制通道，谁就能决定你看到哪几个锚 —— 这里再多算一步也解决不了，解决办法是**分发**：把锚放到对方不能悄悄剪掉的地方，而不是在这份代码里加数学。

**第一版锚无法被判定陈旧。** 如果你手上的全部证据就是 `seq 1`，它和"唯一的发布"没有区别。需要一次外部记录（比如第一次打戳的时间）才能给线一个起点。

**我们没有一条真实的链。** 仓库里没有 `anchors/` 目录，没有一次发布，因此 `seq` 到目前为止只存在于测试里 —— `docs/IMPLEMENTATION-STATUS.md` 仍是零。

## 命令

```
python3 tools/make_release_bundle.py --out dist/r2 --seed-hex $SEED \
        --prev-anchor dist/r1/anchor.json      # 自动 seq+1 与前驱摘要
python3 tools/anchor_chain.py anchors/ [--expect-latest N]
python3 tools/anchor_check.py bundle --prev anchors/003.json
```
