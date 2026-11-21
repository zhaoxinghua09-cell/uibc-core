# Name collisions, checked

S9 of the participation checklist asks for a prior-art and same-name check before any
outward claim. The result here is not flattering, so it is written down rather than
summarised away.

## What collides

| collision | what it is | how it affects us | source |
|---|---|---|---|
| **UIBC** (clinical chemistry) | unsaturated iron binding capacity — a serum assay reported next to TIBC | a clinician who sees "UIBC" assumes a lab test; our first line must deny it | product literature for assay calibrators, e.g. <https://www.zoetis.com/> (search "UIBC calibrator") |
| **UIBCDF** | Unidad de Investigación en Bioinformática, Cómputo y Diseño de Fármacos — a Mexican research unit publishing dozens of packages on Anaconda | search engines rank them above us for the string "uibc"; we are unrelated | <https://anaconda.org/uibcdf> |

Handling so far: a **Name note** is the first block of `README.md`. An external reviewer
still called the note "buried under jargon" when it sat lower; moving it up was the fix.

## What does not collide

**SkillHub** (<https://skillhub.cn/skills>), the largest Chinese-language skill market, was
searched for `uibc`, `uibc-core` and `lgd`: no skill package of those names surfaced; the
result page returned generic programming skills instead. This is "not found", **not**
"confirmed absent" — the site does not expose an exact-match count, and its index changes.

## What we did not check

* PyPI and npm exact-name registration: `uibc` and `uibc-core` on PyPI are **not reserved
  by us**; we publish no PyPI package under either name, so the question of collision is
  moot today and becomes real the day we publish.
* GitHub repository names: `zhaoxinghua09-cell/uibc-core` is taken by us; no other
  repository with that owner prefix was checked.
* Trademark search, any jurisdiction: not done.

## Consequence for outward text

Do not write "the first", "no one else", "unique name", or anything that a one-click
search falsifies because of the two collisions above. This file exists so that sentence
cannot creep back in.
