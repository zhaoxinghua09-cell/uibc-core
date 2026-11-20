# 上游提交核对：`ietf-wg-scitt/examples`

状态：**未提交。材料已在本地生成并自验。** 下面三条是"提交前必须核对"的三件事，2026-11-19 逐条做掉了。

核对时点：2026-11-19；上游 HEAD `727ee03d86fa2c2ca8c534584b870235a1b252df`（commit date `2026-06-26T07:26:13+01:00`）。

---

## 一、上游格式要求：已核对，按 `test-vectors/scitt-cose` 的形状做

上游 `README.md` 与 `test-vectors/scitt-cose/README.md` 给出了现成形状，因为该仓 **2026-06-26 已经合并过一整套同类向量**（由 `action-state-group/scitt-cose` 供献）。照抄的部分：

| 上游做法 | 本包对应 |
|---|---|
| `test-vectors/<set>/v1/<vector-id>/` 每例一目录 | `docs/upstream-package/scitt-rfc9162/v1/<vector-id>/` |
| 每例一份 `expected.json` | 同 |
| `manifest.json` 内联每例的 expected 块 | 同 |
| `SHA256SUMS` 覆盖向量文件 + manifest | 同（6 条） |
| `.gitattributes` 把向量文件标为非规范化（`-text`），保证跨平台 `sha256sum -c` 可复现 | 同 |
| README 写 provenance、验证命令、字段说明 | 同 |

**他们对"外部提交"的表态（原文照抄，这句是门开着的证据）：**

> "A mismatch against your implementation is exactly the report the authors want — agreement on *rejection* is as load-bearing as agreement on *acceptance*."

我们没有撞型：`scitt-cose` 那一套是 **COSE 签名层**（statement/receipt 字节 + 签名负例）；本包是 **哈希树层**（路径折叠、树宽、索引三类负例），README 里明写"deliberately narrower, not a replacement"。

### 形状核对结论

- **可以直接按此形状提交**，不需要 JSON Schema，不需要扁平列表。
- 需要新增一层目录：上游现只有 `test-vectors/scitt-cose/`，本包应落在 `test-vectors/scitt-rfc9162/`。
- 上游根 `README.md` 用列表列出各套件，需要加一行指向新目录（提交时一并改）。

## 二、IETF Note Well / IPR：**不能由我代办**

向上游仓库贡献等同于同意 IETF 的 Note Well 与 IPR 条款，**必须以贡献者本人身份同意**。这一步只能由你本人完成，我不代签、不代勾。

提交时 GitHub 若出现 CLA/Note Well 提示，需要你点同意。这类点击视为你本人作出的法律性同意。

## 三、许可证相容性：**已核对**

- 本仓库：`LICENSE` 全文为 **Apache License 2.0**。
- 上游向量目录的 README **首行即带 `<!-- SPDX-License-Identifier: Apache-2.0 -->`**（`test-vectors/scitt-cose/README.md` 第一行），说明该目录以 Apache-2.0 收纳。
- 本包 README 首行同样带 `SPDX-License-Identifier: Apache-2.0`；每个 `expected.json` 不含代码，只是数据。

**结论：许可相容，且按目录级 SPDX 声明即可，不必改仓库根 LICENSE。**

---

## 本地自验（已跑通，命令可直接复跑）

```
$ python3 tools/build_scitt_vector_package.py
built 5 vectors into docs/upstream-package/scitt-rfc9162
  vectors: 5
VERDICT: CONSISTENT

$ cd docs/upstream-package/scitt-rfc9162 && sha256sum -c SHA256SUMS
31/31 OK
```

五个向量：`valid-tree8-index2`、`valid-tree4-index0`（正例，折叠出的根 == `root_true`）；
`fail-tampered-path`、`fail-wrong-tree-size`、`fail-wrong-leaf-index`（负例，折叠出的根 ≠ `root_true`，且 `reconstructed_root` 是**算出来**的，不是手写的）。

## 仍然缺的（写在这里，不在附录里藏）

- 无 COSE 签名层（本机无 COSE 库，不生成自己验不了的字节）。
- 无透明日志 receipt、无 witness 联签、无 TSA 时间戳。
- 无"签名失败"负例——因为没有签名。这一层在 `scitt-cose` 已覆盖，本包不重复。

## 停在哪

材料、形状、许可、自验都就绪。**动作没做**：开 PR 属于对外发布，需要你明确允许；一旦开，署名是你的 GitHub 账号，公开可查。

你说一句"发"，我就按上面形状建分支、加根 README 一行、写 PR 描述（含 `sha256sum -c` 输出与这五个向量的说明）交上去。
