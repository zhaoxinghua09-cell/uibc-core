# Two documents describe one code, and they disagree

There are two published texts that both define "the agent identity code", and they do not describe the same string.

| | GB/Z 185.2-2026 (national guidance) | ACPs-spec-AIC-v02.02 (community specification) |
|---|---|---|
| Arcs | **8** | **10** |
| Shape | `1.2.156.3088.版本.服务方.请求方.序列号` | `1.2.156.3088.版本.ARSP.供应商.本体序列号.实例序列号.校验码` |
| Checksum | none | CRC-16/CCITT-FALSE over arcs 1-9 ++ per-ARSP salt, Base36, 4 chars |
| Prefix | fixed `1.2.156.3088` | default `1.2.156.3088`, worked example `1.2.156.1234` |
| Serial | one arc, split only by recommendation | two arcs, ontology and instance |
| Salt | n/a | per-ARSP, >=2 bytes, not published; the text publishes one worked example (0x1234) |

Measured consequence (`docs/THIRD-PARTY-DIVERGENCE.md`, executed 2026-11-24): the reference implementation of the second document (`aipmc-basic` 0.0.2) **rejects** the first document's shape, and our reader of the first document **rejects** the second's. Neither is defective. They answer different papers.

## What this repository does about it

Two readers, two labels, no crosswalk:

- `uibc_core/agent_identity_code.py` — eight arcs, GB/Z 185.2 5.1-5.6, checksum absent.
- `uibc_core/acps_identity_code.py` — ten arcs, ACPs v02.02; checksum **judged only when the caller supplies the salt** (`verify_acps_code(code, salt)`), never guessed.

`detect_profile()` says which reading a string is written in (`gbz185.2` / `aip-acps`). Each reader refuses the other's shape with an explicit reason instead of coercing it. Shape alone tops out at `INCONCLUSIVE` — shape is not allocation. The ten-arc case goes one step further **when, and only when, the caller holds the ARSP's salt**: `verify_acps_code()` recomputes arc 10 and returns `VERIFIED` or `INVALID`, with `scope` stating that issuance is still a registry question.

Where the asymmetry used to sit is now written down as a test rather than a paragraph: without a salt we return `INCONCLUSIVE` and say the checksum was not checked; with a salt we return a definite answer. The text's own worked example (`SALT = 0x1234` → `0x646C` → `0JU4`) is reproduced in `tests/test_acps_spec_conformance.py`, so "we can compute this" is a claim with a run behind it, not a promise.

## Why this matters beyond our repository

If two documents in the same ecosystem produce mutually unreadable codes, then "supports the national agent identity code" is ambiguous until the document is named. That is an interoperability question for the authors of both texts, and the honest way to raise it is as a question with a reproduction, not as an assertion that one of them is wrong.

Reproduction for anyone:

```
python -c "from uibc_core.acps_identity_code import read_acps_code as r; print(r('1.2.156.3088.1.0001.00001.ABC123.000001.176F')['state'])"
python -c "from uibc_core.agent_identity_code import parse_agent_code as p; print(p('1.2.156.3088.1.360.360.000000001')['state'])"
```

Both readers, both answers, on the same machine, same day.
