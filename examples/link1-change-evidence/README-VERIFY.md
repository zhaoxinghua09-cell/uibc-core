# Verify it yourself — no AI knowledge needed
# 你自己就能验——不需要懂 AI

This pack is fictional data with real cryptography. A model was updated;
four evidence files say what changed, what was measured, and who approved
it. You do not need to understand seals, keys or AI to check whether the
evidence still matches what was sealed. Copy one line, press Enter, read
one word.

本演示包是虚构数据、真封签。一个模型更新了；四份证据文件写明改了什
么、测出什么、谁批的。你不需要懂封签、密钥或者 AI，就能验这些证据是
不是还和封签时一模一样。复制一行字、按回车、看一个词。

---

## EN — five steps

**Step 1 — Open a terminal.**
Windows: press the Windows key, type `powershell`, press Enter.
Mac: press Command+Space, type `terminal`, press Enter.

**Step 2 — Get the tool (once).**
Copy this line into the window, press Enter:

```
pip install uibc-core
```

**Step 3 — Go to the demo pack.**
Copy this line, press Enter (use the folder you were given):

```
cd uibc-core/examples/link1-change-evidence/packages
```

**Step 4 — Run the check on the approved change.**
Copy this line, press Enter:

```
uibc verify change-approved
```

Read the last word of the result: **PASS**. The evidence matches the seal.

**Step 5 — See the two ways a change pack is stopped.**
Run these two lines, one at a time:

```
uibc verify change-swapped
uibc verify change-unsigned
```

The first says **FAIL** and names the file that was replaced after sealing
(`files/evaluation-report.md` — a better-looking report that was never
approved). The second says **INCONCLUSIVE**: the files are consistent, but
nobody sealed them, so there is no provenance to trust. Not "almost a
pass" — undecidable.

**The gate, in plain words.** A gate has three answers: let it through
(ALLOW), wait for evidence (HOLD), refuse (DENY). HOLD is not a refusal;
it means it is not this change's turn yet. Try:

```
uibc gate change-unsigned
```

It answers **HOLD** — the release decision waits until the evidence is
sealed.

---

## 中文 — 五步

**第 1 步 — 打开终端。**
Windows：按 Windows 键，输入 `powershell`，回车。
Mac：按 Command+空格，输入 `terminal`，回车。

**第 2 步 — 装工具（只需一次）。**
把这一行复制进窗口，回车：

```
pip install uibc-core
```

**第 3 步 — 进演示包所在的文件夹。**
复制这一行，回车（换成你拿到的文件夹）：

```
cd uibc-core/examples/link1-change-evidence/packages
```

**第 4 步 — 验已批准的那个变更包。**
复制这一行，回车：

```
uibc verify change-approved
```

看结果里最后一个词：**PASS**。证据与封签一致。

**第 5 步 — 看变更包被拦下的两种样子。**
逐行运行这两行：

```
uibc verify change-swapped
uibc verify change-unsigned
```

第一个说 **FAIL**，并指名被换掉的文件（`files/evaluation-report.md`
——一份数字更好看、但从未被批准的报告）。第二个说
**INCONCLUSIVE**（无法判定）：文件彼此一致，但没人封签，无从证明出
处。这不是「差一点通过」，是判不了。

**门的人话版。** 门只有三种回答：放行（ALLOW）、等证据（HOLD）、拒
绝（DENY）。等证据不是拒绝，是还没轮到它过。试试：

```
uibc gate change-unsigned
```

它回答 **HOLD**——上线决定等证据封好再走。

---

Fictional data: Meridian Medical and the CardioPatch CP-2 do not exist.
Demo key seed is published in build_demo.py on purpose, so anyone can
rebuild the exact packages; never use a published seed for anything real.
Full run record: RUN-TRANSCRIPT.txt (all spec expectations met,
2026-11-18).
