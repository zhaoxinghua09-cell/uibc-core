# GOVERNANCE.md — 生态治理章程

Version 1.0 · 2026-11-19 · Owner: Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237

## 1. Current governance form

This project is **single-maintainer with published rules**. That is the accurate description today and it is what this charter governs.

It is not a foundation, not a consortium, not an independent committee, and not a standards body. Those forms are not established and must not be described as established in any material. <!-- phrase-ok: 政策条款在列举禁令本身 -->

Development stage: **stage 1** (founder-led, rules published, records transparent). The staged path to other forms is in §7.

## 2. Authority

| Decision | Who decides | Record |
|---|---|---|
| Changes to the normative core (as defined in `VERSIONING.md` §1) | Maintainer, after the seven-step procedure in §3 | Decision Record, public |
| Extension additions | Maintainer | Release record |
| Merging code contributions | Maintainer | Commit history |
| Evaluation conclusions | Evaluator of record | Evaluation record with relation class |
| Authorization to use the system in an organisation | That organisation, not this project | Outside this project's records |
| Publication of any external submission | The owner, named in person | Submission log |

Three separations are structural and may not be collapsed for convenience:

1. **Registration is not assessment.** A record existing in a registry means it was listed, nothing more.
2. **Assessment is not authorization.** A favourable verdict is a statement about evidence against a standard. It is not permission to operate.
3. **Authorization is not a safety guarantee.** Permission to run is granted by a party that accepts the risk, not by this project.

## 3. Change procedure for the normative core

Seven steps, in order. Step 3 must complete before step 4 begins.

| Step | Output | Question it must answer |
|---|---|---|
| 1 | Change Proposal | What changes, and why now |
| 2 | Technical Rationale | What breaks if we do not change it |
| 3 | Compatibility Analysis | What will an existing verifier do — the full field set from `VERSIONING.md` §3 |
| 4 | Security Review | Does this introduce a path that returns `PASS` on unknown input |
| 5 | Public Discussion | Objections received and how each was resolved |
| 6 | Decision Record | Who decided, on what grounds, with objections retained |
| 7 | Version Release | Release record with migration steps |

Skipping step 3 does not accelerate the process; it moves the cost to whoever implements against an unclear specification.

## 4. Contribution and maintainership

Contributions are accepted under `CONTRIBUTING.md`. A contributor becomes eligible for maintainership when all three hold:

- a record of merged contributions;
- a demonstrated passing run of the conformance corpus;
- a signed declaration of interests under `COI.md`.

Eligibility is not appointment. Appointment requires a Decision Record naming the maintainer and the scope of their authority.

## 5. External review

External review is invited, not claimed. A review counts as external only when the reviewer's relation class is `S3` or `S4` under `INDEPENDENCE.md`. Reviews are published with the reviewer's name, their relation class, and any objection they raised.

## 6. Disputes and appeals

Any party may dispute an identity record, an evidence record, an evaluation conclusion, or an authorization record.

| Stage | Commitment (internal target, not a published SLA) | Record |
|---|---|---|
| Acknowledgement | 3 working days | Case number |
| Evidence submission | 14 days for the complainant | Submitted package digest |
| Initial review | 14 days | Reasoning for accepting or rejecting new facts |
| Review by an uninvolved party (material disputes only) | 30 days | Reviewer identity and relation class |
| Outcome | One of: upheld / corrected / withdrawn / re-assessed | Published |

Rules that do not bend:

- an unfavourable conclusion may not be deleted without a record; deletion is treated as withdrawal and must be logged;
- a correction preserves the original conclusion and appends the change with its reason;
- conclusions are published; third-party personal data may be redacted, the outcome may not.

## 7. Staged path

| Stage | Form | Entry condition (checkable) |
|---|---|---|
| 1 | Founder-led, rules published | current |
| 2 | Multiple maintainers and external technical reviewers | ≥1 external maintainer and ≥1 reviewer at `S3`/`S4` |
| 3 | Formal independent review mechanism | evaluator and developer are different owners, with an appeal having run end to end |
| 4 | Foundation or other independent legal form | legal and operational study completed |

No stage may be announced before its entry condition is met. Announcing a stage is a factual claim, and factual claims are governed by the same evidence rules as technical ones.

## 8. Amendment

Amendments to §2 or §3 require the seven-step procedure and a major version of this document.
