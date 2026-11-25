# AER-1 crosswalk: the twelve rows Brennan checked

Source: `fg-tida-wg0/use-cases` issue #71 (formerly `FG-TIDA/use-cases`; the old
path redirects). The table was posted as a comment on 2026-11-24 and relabelled
on 2026-11-25 after Brennan's ruling; this file is the same table in the
repository, so it can be diffed and cited without depending on a comment
thread surviving.

**Status of the right-hand cells.** The uibc-core column cites fields that exist
on the branch of PR #429 (`fix/authority-age-r1-r3`), which is still open. A
reader who wants to check the arithmetic before that PR merges can run the
twelve vectors on that branch — they do not need the merged code:

```
git fetch origin fix/authority-age-r1-r3 && git checkout FETCH_HEAD
python tools/run_authority_age_vectors.py
```

Run on 2026-11-25 against `a065af6`: `12 case(s), 0 mismatch(es)`. The script
takes no arguments; each row prints the computed state, the wanted state and the
reason code.

**How to read the labels.** A row is *cited text* only when both sides cite
something a reader can open: an issue comment, an Internet-Draft section, or a
file and field. A row that rests on cross-draft judgment says so in the cell —
rows 5, 11 and 12 carry that label, and row 5 was moved into that group on
2026-11-25 because draft-26 names no revocation case at all, so citing the
thread was an extrapolation from the append model rather than a reading of the
text.

| # | Requirement field | AER-1 | uibc-core | Strength | Note |
|---|---|---|---|---|---|
| 1 | R1 — each link has a status answer | answer committed as a record (`#71` 7101822656) | per-link verdict, four states (`verify.py`) | strong | both treat the answer as a first-class object |
| 2 | R1 — age counted from when the source gave its answer | answer commits the time it was given (`#71` 7101822656) | `authority_age.answer_age()` and `check_link()` (PR #429) | strong (was gap) | computed and bounded, with the age reported per link; closed this round |
| 3 | R1 — decision record carries decision time | receipt commits `created_at` only; no decision-time member (`#71` 7134239041) | `validation_at` (T) and `decision_at` (A) on the decision record (PR #429) | partial → ours holds both | saved time ≠ decision time; AER-1 still has one member |
| 4 | R1 — each answer's age lands on the record | same as row 2 | `decision_record().answer_checks[].age_seconds` (PR #429) | strong (was gap) | age is per-link on the record, not only a verdict |
| 5 | R1 — a later revocation appends its effective time | **judgment**: draft-26 names no revocation case at all (Brennan's ruling, 2026-11-24); this row is extrapolated from the append model, and sits with rows 11 and 12 rather than with cited text | `lifecycle.json` events (`event_id` chain); `authority_age.status_at()` reads the history at an instant (PR #429) | partial | ours is an event stream, AER-1 is row-append; status at commit is now derived from the stream |
| 6 | R1 — observation time | observation appends, never overwrites (`#71` 7101822656) | `examination` record in `records.py` | strong | both forbid after-the-fact rewriting |
| 7 | R3 — no in-bound answer ⇒ outcome unresolved | `not checked` / `absent` are first-class (`#71` 7134239041) | `ABSENT` / `OPAQUE_CONTENT` never upgraded; `anchored-unresolvable-anchor` | strong | aligned verbatim during PR #43 |
| 8 | R3 — the record keeps it unresolved | "never upgraded by a later refresh" (`#71` 7101822656) | four states cannot be overwritten by a later pass | strong | same semantics |
| 9 | R3 — named conditions that were met | no such field (`#71` 7134239041 concedes the shape needs them) | `conditions_met[]`, always emitted, empty ≠ absent (PR #429) | gap on AER-1 side | the field exists; its values are the decision owner's to name |
| 10 | R3 — named recourse that was relied on | no such field (same) | `recourse_relied_on[]`, always emitted (PR #429) | gap on AER-1 side | same |
| 11 | R4 — scheme rule / legal provision, or an explicit none | none | none | both-gap | joint build, not a defect of either |
| 12 | (AER-1 only) `rejected: unresolvable record` | first-class outcome | `anchored-unresolvable-anchor`, anchored case only | partial | ours applies only when the anchor cannot be resolved; AER-1's is a general fifth outcome |

## What the carrier is, in Brennan's wording

Rows 2, 4 and 6 needed a more precise mechanism than "answer time / observation
time members", which draft-26 does not have. The draft's carrier is the
append-only entry chain: entries for one job form an append-only hash chain, each
entry commits its own `created_at`, a status answer recorded as an entry commits
that entry's time, and a later entry appends without rewriting the earlier ones.
The age arithmetic therefore has both endpoints whenever the answer was recorded
as its own entry.

## What this row set does not claim

- Eight rows are cited text on both sides (1, 3, 6, 7, 8, 9, 10, 12); rows 2 and
  4 were gaps that this round closed on our side; rows 9 and 10 are gaps on the
  AER-1 side because the receipt has no member for them.
- Rows 5, 11 and 12 are judgment, and say so. They are not evidence from a cited
  table, and a reader should not treat them as such.
- The AER-1 side of the table is its author's reading of draft-26 and the thread;
  agreement on it is recorded in issue #71, not asserted here.
