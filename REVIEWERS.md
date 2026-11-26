# For a reviewer who has 10 minutes

This repository is a **local draft plus a verifier**, not a standard and not a
submission. Everything below can be checked from the bytes in this repository;
nothing below asks you to trust a summary.

## 1. Read these four files, in this order

| # | File | Why |
|---|---|---|
| 1 | `drafts/draft-zhao-uibc-evidence-chain-01.md` | The claim. §4.1 states what each object commits and what it does not. Read that table first; it is the part most drafts leave implicit. |
| 2 | `REPRODUCTION.md` | How to get the bytes without corrupting them, and the one extraction trap that makes a correct verifier look broken on Windows. |
| 3 | `conformance/oracle/README.md` | What the 32 cases are, and why a rejection-only corpus proves nothing (§5.1 of the draft). |
| 4 | `drafts/…-01.md` Appendix F | The conformance tiers are a **proposal**. If a sentence in the body leans on them, that is a defect; report it. |

## 2. Run this, in a fresh clone

```
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core && git checkout feat/standards-exceed-20261125
python tools/outsider_chain_audit.py     # expect VERDICT: OK, 4 ok lines
python tools/axis_report.py              # expect: 32 cases, 32 consistent, 0 divergent
python -m pytest -q                      # expect: 2087 passed, 0 failed, 32 skipped
```

If you have only a tarball: `python tools/extract_tar.py <file>.tar.gz --dest out`.
Do **not** use Windows `bsdtar` and then judge the corpus — it mangles non-ASCII
names and the case `accept-unicode-names` fails with a hash mismatch that is not
the verifier's fault (`REPRODUCTION.md` shows how to tell the two apart).

## 3. What is verified, and by whom

- Verified here: the checks run, the corpus reproduces, the public clone matches the pushed branch head (`git log -1`
  when you clone is the authority; this file does not pin a commit, because a
  document that names its own commit is wrong the moment it is committed).
- **Not** verified: no third party has reviewed this and signed off. S0 (expert
  seat) is recorded as NOT RUN in the gate file. Linux and macOS have not been
  run: anything outside Windows is *not verified*.
- Two external AI reviewers (DeepSeek-V3.2 and GLM-5.3, two vendors) read the full
  draft seven times between them. Their last verdicts were **Decline / Decline**.
  The reasons were scope and structure, not wording. The record is in
  `external_ai.json` alongside the gate, including what was rejected and why.

## 4. Six claims you should not believe without checking

1. **"Nineteen checks."** Six of them are conditional ("where the package carries
   them"). The number is nominal; count what your package actually triggers.
2. **"Two independent readers."** The Node reader covers the head chain only,
   roughly 10 of 19 checks. Calling it a second implementation is generous.
3. **"32 cases."** That is fewer than the 54 in `draft-gruszka-scitt-statement-identification-05`,
   which is the closest work. Scale is a real gap, not a footnote.
4. **"Anchored."** A root on a public log makes guesses checkable and hides
   nothing else; and `evidence/anchors.json` is **not** committed by the root
   (draft §3). The anchor claim is *tested*, not *detected*.
5. **"The seal binds the package."** It binds `identity.json` + `manifest.json` +
   `lifecycle.json`. Evidence bytes are bound only through their hashes.
6. **"Interoperable with AER-1."** We consume their receipts (64 vectors: 27
   accepted, 36 rejected, 1 declared profile difference). We do not define their
   format and they have not reviewed our reading of it.

## 5. How to report a finding

Open an issue with: the commit, the command you ran, the output, and which claim
above (or which sentence in the draft) it contradicts. A finding that cites a
section number which does not exist is itself a finding — `tools/check_section_refs.py`
exists so that class cannot survive a commit.
