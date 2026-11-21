# 三个已经存在的第三方见证，今天重查了一遍

`docs/IMPLEMENTATION-STATUS.md` 一直说"外部见证为零"。那句话是错的 —— 错得有必要记下来，因为它是这个项目最容易犯的那类错：**把"没人采纳我们的格式"和"没人见过我们的产物"混成一句。**

它们是两件事。

## 今天（2026-11-19）实测

```
$ python3 tools/check_witnesses.py
VERDICT: OK
  Zenodo               ok
      record 22821835 exists, created 2026-09-18T01:13:59
      version DOI 10.5281/zenodo.22821835 / concept DOI 10.5281/zenodo.22821834
      file uibc-core-0.2.1.zip  md5:d8789c65a309e869977b0d74825a9b1e
      local dist zip md5 d8789c65a309e869977b0d74825a9b1e
      the archived file is byte-for-byte the zip in dist/
  Software Heritage    ok
      snapshot a901225b50ae resolves, HEAD -> refs/heads/main
      origin SWHID swh:1:ori:819530c8be2adf6da901256ce9fd28063f8f1296
  Sigstore Rekor       ok
      entry 108e9186e8c5677a… exists at logIndex 2883389783
      integratedTime 1789710612  (2026-09-18T05:50:12Z)
      artifact sha256 59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4
      local dist zip sha256 59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4
```

Not "we say it is archived". **Both digests came back equal to the file in `dist/`, from two services we do not operate.**

## 每一条各自证明什么

| 见证 | 它说的 | 它不说的 |
|---|---|---|
| **Zenodo** DOI `10.5281/zenodo.22821834`（concept）/ `…835`（version） | 这个 zip 存在，内容逐字节等于 `dist/` 里那份（md5 相同） | 不代表有人用过它 |
| **Software Heritage** `swh:1:ori:8195…` / `swh:1:snp:a901…` | 这台仓库在 2026-09-18 被归档，快照可浏览 | 不代表有人读过 |
| **Sigstore Rekor** `logIndex 2883389783` | 一个公开透明日志在 2026-09-18T05:50:12Z 记录了该产物的 SHA-256 | 不代表有人验过签名 |

三条都是**对产物的见证**：它们让"这个文件在那个时候存在、是这个字节序列"变成别人能独立复算的事实。这在学位论文与职业场景里是硬背书 —— 一个带 DOI 的归档件，比一百句形容词有用。

三条都**不是**"第三方采纳了我们的实现"。`IMPLEMENTATION-STATUS` 的四桶仍然是空：没有上游合并、没有第三方注册、没有在评审、没有独立实现。

## 为什么这个区分必须写进文档

上一版状态页只数了"采纳"，然后把"见证"一起算成了零。读者（包括未来的我）会因此以为连 DOI 都没有 —— 于是重新去找、重新去申请，或者干脆以为这条路走不通。

**一个诚实的计数器必须把两个数字分开写**，否则它算错的那一格会把已经拿到的东西一起抹掉。

## `.ots` 文件：不算

`timestamps/uibc-core-0.2.1.zip.ots` 在 2026-09-26 复核中被判定**不构成有效时间锚**（无 OTS magic、不内嵌工件摘要、日历回执不可复算、无第三方独立验证），已停止引用。这条撤回保留在 git 历史里，目录里的 README 也写着"不得作为存证引用"。

**撤回是对的，且撤回记录本身就是证据**：一个能公开说清"我们哪一条主张不成立"的项目，比一个只累积主张的项目可信。

## 怎么复算（不需要我们的任何东西）

```
python3 tools/check_witnesses.py          # 本仓库里的脚本，6 秒
# 或者完全不用我们的代码：
sha256sum dist/uibc-core-0.2.1.zip        # 应等于 Rekor 里的 59cc1c91…
md5sum    dist/uibc-core-0.2.1.zip        # 应等于 Zenodo 文件校验值
curl -s https://archive.softwareheritage.org/api/1/snapshot/a901225b50ae3fe84f9f878b8c0d6b0399867e64/
```

CI 不跑这个脚本：**第三方的故障不该把我们的 CI 变红**，那教不会任何人任何事。它按需运行，结果是给人看的。
