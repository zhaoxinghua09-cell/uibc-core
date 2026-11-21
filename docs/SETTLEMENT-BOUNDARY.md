# 结算边界：这份格式在支付争议里能证明什么，不能证明什么

支付适配是我们与同业差距最明显的一维：他们把授权回执接进了"agent 发起的支付"的争议证据包里，
我们连"谁承担损失"这句话都没写过。本轮补的不是支付能力——我们没有清算、没有收单、没有牌照，
也不打算在文档里假装有——而是把边界写成**机器可读、可被检查器否决**的六问六答。

## 他们做到了什么（一手读到的）

`probityai/agent-evidence-vectors` 的 `corpora/vectors-agent-payment-mandate/`：`agent-payment-mandate/v1`，
**15 个案例、11 条规则、11 个变异体逐一被抓**。它把四样东西绑在一起——用户签的 mandate（AP2 cart /
Mastercard Verifiable Intent / Stripe Shared Payment Token，按概念命名）、agent 出示的凭证、实际跑的扣款、
把它们串起来的回执；读者**自己重算命名的摘要，而不是相信声称摘要的字段**。其 README 结尾两句很重要：

> "It proves a charge stayed inside what a user authorised; it does not prove the user meant it."
> "It does not say who bears the loss in a dispute."

也就是说：连做得最深的这一家，也把"金额是否在授权内"与"损失谁承担"分得很清。

## 我们的六问六答（`docs/SETTLEMENT-BOUNDARY.json`，`tools/settlement_boundary.py` 逐条校验）

| # | 争议里会问的 | 我们的答案 | 依据 |
|---|---|---|---|
| Q1 | 有人在**这些确切字节**上跑过验证器吗？ | **supported** | `docs/RECEIPT-FORMAT.md`：版本、语料摘要、逐案表、命令、具名运行者，缺一即作废 |
| Q2 | 这些字节自某日起**没被改过**吗？ | **partial** | `docs/LAB-PROTOCOL.md`：签名 + TSA 令牌离线可验；**但未在任何已发布 release 上跑过**，OTS 客户端缺席时只记 `unavailable` |
| Q3 | 跑的人**被授权代表**他写的那个方吗？ | **partial** | `docs/DELEGATION.md`：单签、一跳、有窗口、绑语料摘要；**不是阈值授权、无撤销登记处**，公钥不在带外给出时只给"identity unbound" |
| Q4 | 扣款在 mandate 的**金额／商户／币种**限额内吗？ | **not_ours** | 本格式无 mandate、无金额、无商户、无币种。判这件事的语料在 probityai 那边，15 案例 11 规则——那是他们的，不是我们的 |
| Q5 | 未授权扣款的**损失谁承担**？ | **not_ours** | 本仓库没有任何字段、任何句子分配责任；写别的就是把法律主张伪装成技术主张 |
| Q6 | 这份东西能**递给收单方或仲裁者**当证据吗？ | **not_ours** | 可采性由法庭／仲裁庭按其规则决定，不由我们决定 |

三条 `not_ours` 都带理由，不是空白——空白容易被读成"以后会补"，理由写清楚才是边界。

## 检查器拒什么

- `we_process_payments` / `we_authorize_charges` **必须字面为 false**；改成 true 直接否决（改一个字段就把"能绑字节"变成"能收款"，这是最容易发生的事故）。
- `supported` / `partial` 必须指向**仓库里真实存在的文件**，并写清"证明什么"；`partial` 必须写**限制**，因为没有限制的 partial 读起来就是 supported。
- 六条问题的 id 固定为 Q1–Q6，**不许重编号**（重编号会丢掉历史对应关系）。
- 扫描 `README.md` 与四份关键文档，命中 `guarantees payment` / `authorizes the charge` / `chargeback protection` / `pci compliant` / `we settle` 等短语即判 **OVERCLAIM**，退出码 1。

## 实测，2026-11-20

```
$ python tools/settlement_boundary.py
Q1  supported   Did someone run this verifier against these exact bytes?
Q2  partial     Were these bytes unchanged since a date anyone can check?
Q3  partial     Was the party who ran it authorised to act for the party they named?
Q4  not_ours    Was the charge inside the mandate's amount, merchant and currency limits?
Q5  not_ours    Who bears the loss if the charge was not authorised?
Q6  not_ours    Can this be filed with an acquirer or arbitrator as evidence?

ACCEPTABLE — six questions answered, no payment claim in the scanned documents     exit 0
```

在 `README.md` 里塞一句 "we settle the payment instantly" 后重跑：`OVERCLAIM — README.md contains 'we settle the payment'`，退出码 1
（见 `tests/test_settlement_boundary.py::test_the_cli_exits_one_on_an_overclaim`）。

## 仍然没有的

- **没有 mandate 语料。** 判"金额是否超限"需要整套 mandate 语义与 15 个案例，我们没有；
  本轮也没打算复制别人的语料来充数。
- **没有清算／收单链路。** 一个字段都没接。
- **没有法律意见。** Q5／Q6 的答案永远是 `not_ours`，除非有人以书面法律意见改变它——那不是我能在仓库里单方面完成的事。
