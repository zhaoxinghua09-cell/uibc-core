# Measuring adoption for per-action record formats

**Status: draft, unsent.** Nothing here has been sent to anyone. The message in
§6 is a draft; sending it needs the account holder's explicit go-ahead.

A conformance section usually answers *"how much of the spec do you cover?"*
This note proposes a second question that is cheaper to answer and harder to
answer dishonestly: *"has anyone outside your account taken it up?"*

The method is four buckets and one exit code. It is small enough to copy into
any project in an afternoon, and it is deliberately built to be **falsified**:
when any bucket goes non-zero the check fails, and a human has to look at why.

## 1. The four buckets

| Bucket | Question | How it is searched |
|---|---|---|
| another repository | does any repository outside our account exist under the format's own name? | GitHub repository search for the format's distinctive name, minus the owner account |
| another codebase | does any code outside our account emit or consume the format identifier? | GitHub code search for the wire identifier string |
| a standards body | has a standards organisation taken up the name? | IETF Datatracker document search on the name |
| a neighbouring spec | does the closest adjacent spec mention us? | the adjacent package's registry metadata, read as text |

Reference implementation: `tools/check_adoption.py` in this repository. `--json`
for machine use; `--out` writes the dated report. Exit codes: **0** every bucket was
asked and answered zero, **1** a signal, **3** at least one bucket could not be asked.

## 2. What went wrong the second time (2026-11-20)

Run live, the check printed `ZERO ADOPTION` while its own JSON showed
`"error": "HTTP 401"` on the code-search bucket. An unauthenticated code search is
**not** a search that found nothing; it is a search that did not happen. The verdict
was reading a refusal as a result — the same defect as the earlier one where a
missing interpreter made a corpus look like it failed every case.

Three things changed, and they are the point of this section rather than a footnote:

- buckets carry a **state**, not just a number: `measured` / `unmeasured` / `context`;
- any `unmeasured` bucket makes the verdict `INCOMPLETE` with **exit code 3** and a
  sentence naming which bucket refused and why, so a reader cannot quote the run as
  a zero;
- a fifth bucket records **package downloads** as `context` — it is a real number and
  it is never summed into adoption, because **downloads are not a party**: a mirror,
  a cache and a CI image all download without adopting.

While fixing this, a second defect surfaced from the test: two repository searches
(`uibc-core`, `uibc-anchor`) can both return the same repository, and the count was
the number of hits rather than the number of repositories. One adoption could read
as two. The bucket now de-duplicates by full name — the direction that flatters is
the one that has to be closed.

## 2b. What went wrong the first time

The first version searched for `uibc`. That returned 18 repositories — and none
of them were about this format: `UIBC` is also the name of a UPnP display
protocol from 2010. The bucket read as "18" for a project with zero adoption.

The fix is a rule, not a patch: **search only the format's own distinctive
string**, never an acronym that other fields already own. A name collision
bucket is not adoption; it is noise that flatters.

## 3. What this method cannot measure

Stated here rather than in an appendix, because a measurement that hides its
limits is marketing:

- **A zero is not proof of absence.** It is proof that four specific searches,
  run at a specific time, found nothing. A private deployment, an internal
  standard, or a fork under a different name is invisible to all four.
- **A non-zero is not proof of uptake.** A repository that names the format may
  be a survey, a critique, or a vendored copy.
- **Keyword search is not semantic.** A standards-body search on the name finds
  documents that use the string, not documents that adopt the semantics.
- **The clock matters.** Every result is an observation with a timestamp; none
  of it is a permanent property of the project.

## 4. Our own result

All four buckets are zero as of 2026-11-19. The command, its output and the
timestamp are reproduced in `docs/LANDSCAPE-2026-11.md` §五. This is published
as a **zero that can be overturned**, not as a claim of quality.

Dated snapshots of the re-run are committed under `docs/adoption/` so the sequence
can be diffed rather than trusted. `docs/adoption/2026-11-20.json` is the run that
found the 401 defect and the double-count; it is kept even though it is wrong in
those two ways, because deleting a wrong measurement is how a history of
measurements becomes a history of good news.

## 4b. What the run of 2026-11-20 actually returned

```
$ python tools/check_adoption.py --out docs/adoption/2026-11-20.json
bucket                 state       found  what
another repository     measured        0
another codebase       unmeasured     —
a standards body       measured        0  
a neighbouring spec    measured        0  
package downloads      context        598  last_month=598

VERDICT: INCOMPLETE — 1 of 5 buckets could not be measured: another codebase
         (HTTP 401 — code search needs an authenticated request; without one this
         bucket was not asked)
```

Two facts from that table that are easy to lose: the package was fetched **598 times
in the last month** and that number says nothing about adoption, and the only
non-zero in the table is that number. Everything that would count as adoption
remains zero — with one bucket not even asked.

The same command, borrowing the `gh` CLI's existing credential so the code search
could actually be asked, gives the other verdict:

```
$ python tools/check_adoption.py --out docs/adoption/2026-11-20-authenticated.json
VERDICT: ZERO ADOPTION — each bucket was asked and each answered zero
```

Two snapshots, both committed, different exit codes: **3** when one bucket could not
be asked, **0** when all four were asked and all four answered zero. The pair exists
so nobody has to take either one on trust — the difference between them is the
entire discipline. The credential is borrowed in memory for one request, never
written into the report; the report records only `"credential": "present"`.

## 5. Why publish a zero at all

Because the field's own literature says the same thing, and says it independently.
`arXiv:2606.04193` (J. Figuera, 2 June 2026, 22 pages), in its §8, writes:

> **Adoption-incentive problem.** Sello is only useful if services adopt it;
> **in 2026, that adoption is zero.**

That sentence is about a different protocol by a different author, and it is the
most useful sentence in the literature for anyone writing an implementation
report this year: it means an adoption count of zero is **a property of the
field in 2026, not a defect of one project**. It also means nobody can honestly
claim an adoption lead — including the authors of the largest draft in the space.

## 6. Draft message (unsent)

> Subject: `Adoption counting: four buckets, one exit code — a measurement you can overturn`
>
> I maintain `uibc-core` (Apache-2.0), a verifier for a per-action record format.
> It is **not** an implementation of your draft, and I am not asking it to be
> described as one.
>
> Your Implementation Status section reports how much of the specification your
> reference implementation covers. That is a different question from whether
> anyone outside your account has taken the format up. I have been answering the
> second question with four searches and an exit code — repositories, codebases,
> standards bodies, neighbouring specs — and publishing the result even when all
> four are zero (`tools/check_adoption.py` in my repository; result and timestamp
> in `docs/LANDSCAPE-2026-11.md`).
>
> Two things I would rather be corrected on than quoted for:
>
> 1. the choice of search string — I learned that an acronym already owned by
>    another field (UIBC/UPnP) inflates the count to 18 with zero real hits;
> 2. whether an adoption count belongs in a conformance section at all, or only
>    in a separate measurement document.
>
> If your document already answers the second question somewhere I did not read,
> please point me at the section and I will cite it instead of my own count.
> I am not asking for endorsement, and I am not claiming a lead: on this
> measurement nobody in the field currently leads.

## 7. What this note does not say

- It does not say our format is better, stronger, or more complete than any
  draft named above.
- It does not say "first" or "only". Both are the kind of sentence one
  fact-check retires permanently.
- It does not describe any regulator, working group, or standards body as having
  accepted anything.
