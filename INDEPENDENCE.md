# INDEPENDENCE.md — 独立评估与利益关系披露政策

Version 1.0 · 2026-11-19 · Owner: Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237

## 1. Purpose

This policy defines when a statement about verification may be called independent. Its purpose is to make one prohibition unambiguous: **a project may not describe its own assessment as a third-party verification.**

## 2. Relationship classes

Every evaluation record carries exactly one relation value. There is no default and no "unknown" value.

| Value | Meaning | May be called independent |
|---|---|---|
| `S1` | Assessed by the code author | No |
| `S2` | Assessed within the same project or by the same owner | **No** |
| `S3` | Assessed by an external developer with no commercial relationship | Yes, with disclosure |
| `S4` | Assessed by an unrelated reviewer with no relationship of any kind | Yes |
| `S3m` | Assessed by an external machine (model or service) with no commercial relationship to the assessed party | Yes, machine |
| `S4m` | Assessed by an external machine under a third-party service, with the key fingerprint and raw exchange retained | Yes, machine |

A machine review is not a human review. Both `S3m` and `S4m` MUST record `reviewer_type: machine`, the model or service identity, and a key fingerprint. Wording may say "reviewed by an external model", never "independently reviewed by a third party" — the latter implies a person taking responsibility.

## 3. Required disclosures

An evaluation record MUST contain:

- `relation` — one of the values in section 2;
- `self_assessment` — boolean, `true` whenever `relation` is `S1` or `S2`;
- `evaluator` — named party;
- `consideration` — any payment, equity, employment or in-kind benefit received by the evaluator from the assessed party.

`consideration` must be recorded even when it is "none". An empty field is treated as unreported, not as zero.

## 4. Wording rules

| Forbidden when `relation` is S1/S2 | Permitted alternative |
|---|---|
| `third-party verified` | `self-assessed` | <!-- phrase-ok: 政策条款在列举禁令本身 -->
| `independent assessment` | `internal conformance check` | <!-- phrase-ok: 政策条款在列举禁令本身 -->
| `certified` | `conformance-checked (internal)` |
| `independently reproduced` (referring to a second implementation inside this project) | `two implementations maintained in the same project, cross-checked in CI` |

These rules are machine-checked. `banned_phrases.txt` in the repository encodes them, and `check_phrases.py` runs them over any document before publication.

## 5. Consideration exclusion

If an evaluator has received consideration from the assessed party, that evaluation MAY NOT be cited as external evidence. It may be used internally only. Recording the consideration does not cure the conflict; disclosure is not consent.

## 6. Current status of this project

As of 2026-11-19, the main project and LGD-Eval share a single owner. The applicable relation is therefore **`S2`**. Consequently:

- no evaluation result produced by this project may be described as third-party verified; <!-- phrase-ok: 政策条款在列举禁令本身 -->
- the project publishes no certification mark and issues no certificates;
- claims of independence are limited to named external parties with recorded `relation` values of `S3` or `S4`.

## 7. Dissent

Where an external reviewer disagrees with a published conclusion, the reviewer's objection and the maintainer's response are retained on the same page. Conclusions are never published with objections removed.

## 8. Amendments

Changes to this policy follow the seven-step procedure in `GOVERNANCE.md`. A change to the definition of `S3` or `S4` is a breaking change and requires a version increment.
