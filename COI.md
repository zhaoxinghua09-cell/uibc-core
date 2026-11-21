# COI.md — 利益冲突政策

Version 1.0 · 2026-11-19 · Owner: Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237

## 1. Scope

This policy applies to anyone who produces an evaluation record, signs a verdict, reviews a submission, or writes public statements about this project's technology.

## 2. Roles that must be declared

A person acting in any of these capacities declares it, even when the role is unpaid:

- project developer
- project maintainer
- internal evaluator
- external evaluator
- independent reviewer
- commercial service provider

## 3. Rules

**R1 — Multiple roles must be disclosed.** When one party holds more than one role, the evaluation record states it in the first field (`self_assessment: true` for developer-evaluators, `relation: S2`).

**R2 — Consideration excludes external use.** An evaluation produced by a party that received payment, equity, employment or in-kind benefit from the assessed party may not be cited as external evidence. Disclosure does not remove the exclusion.

**R3 — Disclosure travels with the record.** Disclosure is a field inside the evaluation record, not a paragraph in a separate document. Citing a conclusion requires citing its disclosure field with it.

**R4 — Paid ranking is prohibited.** No party may buy a higher technical grade. There is no paid tier that changes an assessment outcome, and no sponsorship that changes a published verdict.

**R5 — Objections are retained.** An external reviewer's objection and the maintainer's response are kept on the same page as the conclusion.

## 4. What is not a conflict

The following do not, by themselves, constitute a conflict requiring exclusion:

- the reviewer works at the same organisation as a different project's author;
- the reviewer has publicly criticised the project (criticism is not a relationship);
- the reviewer has used the software in their own work;
- the reviewer is paid by their own employer for review work, provided the assessed party pays nothing.

Each of these is still recorded, because recording costs nothing and omission costs credibility.

## 5. Registry of declared interests

The project maintains a public list of declared interests: party, roles held, relationship class, and date declared. It is a list of facts, not of judgements. No entry in it constitutes an endorsement or its opposite.

## 6. Reporting a conflict

A conflict may be reported by anyone, including anonymously. Reports are handled under `GOVERNANCE.md` §6 and the outcome is published with the reasoning, redacting only third-party personal data.

## 7. Current declared state (2026-11-19)

| Party | Roles | Relation class |
|---|---|---|
| Xinghua Zhao | developer, maintainer, internal evaluator, commercial service provider | `S2` |
| Any external evaluator | none declared to date | — |

This table is the whole registry today. Its brevity is the finding, not a formatting choice.
