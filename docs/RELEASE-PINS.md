# 三样东西必须一致，两样一致不算数

版本号不是对字节的承诺。`uibc-core 0.4.0` 可以被重传、被 yank、被镜像换成另一份。所以把「PyPI 现在供的是什么字节」写下来，写到索引改不动的地方。

## 实测

```
$ python3 tools/check_pins.py
channel 1 (release asset) : .../releases/download/release-pins-0.4.0/uibc-core-0.4.0.sha256
channel 2 (PyPI index)    : 2 artefact(s)
  uibc_core-0.4.0-py3-none-any.whl   pinned=index=3aecb408c7af5081  download=3aecb408c7af5081 (115131 bytes) ok
  uibc_core-0.4.0.tar.gz             pinned=index=7c0fc50c4c42e276  download=7c0fc50c4c42e276 (821066 bytes) ok

VERDICT: OK - the pin, the index and the download agree
```

**2.229 秒**，三个来源：Release 资产（我们发的）、PyPI 索引（它声明的）、真实下载（装机会拿到的）。

三样一致才算数。任意两样一致都不算：

| 不一致的组合 | 意味着 |
|---|---|
| 资产 ≠ 索引 | 钉子过期，或钉子被伪造 |
| 索引 ≠ 下载 | 镜像或代理在供别的东西 |
| 资产 = 索引 ≠ 下载 | 前两个都被人维护，第三个不受控 —— 这正是「只信索引」的盲区 |

第三种是这次真正排除掉的：**别人可以声称，但只有下载能证明**。

## 钉文件长什么样

`anchors/pins/uibc-core-0.4.0.sha256` 是纯 `sha256sum` 格式：

```
3aecb408...  uibc_core-0.4.0-py3-none-any.whl
7c0fc50c...  uibc_core-0.4.0.tar.gz
```

不用我们的任何代码也能用：`sha256sum -c uibc-core-0.4.0.sha256`。

## 通道

仓库里的 `anchors/pins/` 是顺手副本；**Release 资产 `release-pins-0.4.0` 才是那个必须被单独伪造的**。两处不同通道，改一处不改另一处就会被 `check_pins.py` 抓出来。

## 边界

- 它证明「PyPI 现在供的字节 = 我们钉的字节」，不证明这些字节是好的（那是 conformance 与 19 项检查的事）。
- 它证明「索引与下载一致」，不证明 PyPI 没在更早的时候供过别的字节 —— 那需要透明日志（我们已有 Rekor 一条，针对 0.2.1）。
- 0.4.0 的发布不是本轮做的，是并行开发线在 2026-11-18T17:19 发的。本轮做的是**把它钉住并跨通道核验**。
