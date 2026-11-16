# Quickstart — five minutes, verified

Every command below was executed on 2026-11-17 against this repository at v0.3.3 and the output shown is what it actually printed. If yours differs, that is a defect, not a misunderstanding.

Prerequisites: Python ≥ 3.10. No account, no network, no Docker.

## 0. Get the code

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
```

You can skip installation entirely — the package runs from the checkout:

```bash
export PYTHONPATH="$PWD"        # Windows PowerShell: $env:PYTHONPATH = (Get-Location)
python -m uibc_core.cli --help
```

## 1. One command, eight steps

```bash
python -m uibc_core.cli demo
```

It builds a package, registers an agent, adds evidence, seals it with Ed25519, verifies as a stranger, tampers with the evidence, forges a fresh seal with the attacker's own key, and then verifies again with the owner's public key pinned.

## 2. Read what came out — four outcomes, not one score

| Step | What happened | What it teaches |
|---|---|---|
5 | `PASS` (assurance: public-key) | A stranger verifies without any key or permission |
6 | `FAIL` after tampering | Content changes are caught by hashes |
7 | **`PASS`** with the attacker's key | A substituted key verifies against *itself* — a seal proves **origin**, not **ownership** |
8 | `FAIL` when pinned to the owner's `.pub` | Pinning is the only thing that catches substitution |

**Step 7 is the point of the whole tool.** An unpinned seal is self-consistent and therefore verifies; only a pinned key tells you *whose* seal it is. Publish your `.pub` somewhere verifiers can pin it.

## 3. Verify something yourself

The demo prints the package path. Then:

```bash
python -m uibc_core.cli verify <demo-package-dir>                  # no key needed
python -m uibc_core.cli verify <demo-package-dir>/forged --pubkey <demo-dir>/owner.key.pub
```

Exit code 0 = PASS. Non-zero = FAIL or INCONCLUSIVE — read the report, do not read the exit code alone.

## 4. Confirm the verdict has three values, not two

```bash
python -m uibc_core.cli inspect <demo-package-dir>
```

A package whose seal cannot be checked (no key, no pin) reports **INCONCLUSIVE**, not PASS. This is deliberate: in v0.2 an entirely self-consistent forgery passed in open mode, because the only provenance check was unresolved while the top-level verdict said PASS. See `docs/verdict-and-seal-semantics.md` and `docs/adr/ADR-001-three-valued-verdict.md`.

---

### What this quickstart does **not** prove

- It does not prove the system under evaluation is safe. It proves what **this** run, on **this** machine, at **this** version, concluded.
- It does not prove coverage. The demo is one package with one evidence file; the fixture matrix is in `fixtures/EXPECTED.md`.
- It is **not** independently reviewed. Every result here is `SELF-ASSESSED`.
- It is **not** a certification, an accreditation or a regulatory conclusion, and carries no probative effect.

---

# 快速开始 — 五分钟，逐条实测

以下命令均于 2026-11-17 在本仓 v0.3.3 上实跑，输出为真实打印内容。

前置：Python ≥ 3.10。无需账号、无需联网、无需 Docker。

## 0. 获取代码

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
```

可以不安装直接跑（实测可用）：

```powershell
$env:PYTHONPATH = (Get-Location)
python -m uibc_core.cli --help
```

## 1. 一条命令，八步

```bash
python -m uibc_core.cli demo
```

它会建包→注册 Agent→加证据→Ed25519 封签→陌生人验证→篡改证据→用攻击者自己的钥匙重新封签→再用所有者公钥钉住验证。

## 2. 读结果：四个结论，不是一个分数

| 步骤 | 实际发生 | 说明什么 |
|---|---|---|
5 | `PASS` | 陌生人无钥匙、无权限即可验证 |
6 | 篡改后 `FAIL` | 内容改动被哈希抓到 |
7 | **`PASS`**（攻击者钥匙） | 换钥匙后封签"对自己有效"——**签名只证来源，不证归属** |
8 | 钉住公钥后 `FAIL` | **只有钉住公钥才能抓到替换** |

**第 7 步是整个工具的意义所在**：未钉住的封签自洽，因此会通过；只有钉住的公钥才能告诉你"这是谁的封签"。请把 `.pub` 发布到验证者能钉住的地方。

## 3. 自己验一次

Demo 会打印包路径：

```bash
python -m uibc_core.cli verify <demo 包目录>
python -m uibc_core.cli verify <demo 包目录>/forged --pubkey <demo 目录>/owner.key.pub
```

退出码 0 = PASS；非 0 = FAIL 或 INCONCLUSIVE——**要看报告，不要只看退出码**。

## 4. 确认判定是三值不是二值

```bash
python -m uibc_core.cli inspect <demo 包目录>
```

无法检查封签（无钥匙、无钉住）时报 **INCONCLUSIVE**，不报 PASS。这是刻意的：v0.2 时一个完全自洽的伪造件在开放模式下被判 PASS，因为唯一与来源有关的检查未解决，而顶层判定却是 PASS。

### 本快速开始**不**证明什么

- 不证明被评系统安全，只证明本次运行在本机、本版本上得出什么结论；
- 不证明覆盖完整（示例只有一个包一个证据文件，完整矩阵见 `fixtures/EXPECTED.md`）；
- **未**经独立复核，所有结果标签为 `SELF-ASSESSED`；
- **不是**认证、不是资质认定、不是监管结论，不具有证明作用。
