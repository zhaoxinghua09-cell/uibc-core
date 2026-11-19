# 通道分离：锚发在 Release 页，包留在仓库

`anchors/001/anchor.json` 躺在仓库里，就在它钉住的那个包旁边。这不是优点，是弱点：**能改包的人，在同一次提交里就能改锚**。

所以同一个锚又被发到了另一个通道 —— GitHub Release 页 `anchor-001`，作为一个下载资产。包改不了它。

## 一条命令，两个通道拼回去

```
$ python3 tools/check_channel.py
anchor from the release : https://github.com/zhaoxinghua09-cell/uibc-core/releases/download/anchor-001/anchor.json
repo copy               : anchors/001/anchor.json
sha256 equal            : yes
seq 1  key_id 75935681213e00a1  head sha256:2935c3f497b00949bff
reassembled bundle      : ANCHORED
verifier                : result: PASS

VERDICT: OK - the package cannot rewrite this anchor
```

**1.383 秒。** 锚从 Release 页取，包从仓库取，拼在一起交给验证器 —— 它说这两半还属于彼此。

这意味着攻击面变了：想伪造的人必须**同时**改仓库和改 Release 资产，而 Release 资产的每一次改动都留痕，且不是一次 `git commit` 能悄悄带过的。

## 这次选择与没选的

| 通道 | 分离强度 | 代价 | 选了没有 |
|---|---|---|---|
| **GitHub Release 资产** | 中（同平台不同路径，改动留痕） | 已发，1 分钟 | ✅ 用了 |
| DNS TXT | 强（域名控制权） | 需域名与 DNS 权限 | 未选，无域名在手 |
| 只放锚的第二仓库 | 中强 | 多一处要维护 | 未选，冗余 |
| 邮件列表存档 | 强（第三方存档） | 需对外发信 | 未选，涉对外发信 |

Release 是最省的一次真实分离。它不完美——同一个平台，同一个账号——但它把「改包即改锚」这条最廉价的路堵上了。

## 边界，仍旧明写

- 钉的包是 demo fixture，不是 `dist/uibc-core-0.2.1.zip`，也不是 v0.4.0 构建。
- 这条分离是**通道级**的，不是**托管级**的：同一个 GitHub 账号仍能同时改两处。要堵住这条，需要 DNS 或第三方存档。
- 撤回：删 Release 即不再"当前"，tag 与历史保留"它曾存在"这一事实 —— 这正是锚撤回应有的含义。
