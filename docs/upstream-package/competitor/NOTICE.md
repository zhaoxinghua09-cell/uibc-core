# Third-party corpus, vendored verbatim

These 171 files are the corpus of **probityai/agent-evidence-vectors** at commit `39daf704`,
path `vectors-poc-evidence/package/poc_evidence_vectors/corpus`.

- Licence: Apache License 2.0 (the upstream repository ships `LICENSE`).
  A copy of the licence text is in `LICENSE-APACHE-2.0.txt`.
- Bytes: unmodified. `MANIFEST.json` lists each file's sha256, and its
  `manifest_digest` uses the same algorithm the snapshot receipt uses, so a
  stranger can tell a changed corpus from a changed claim.
- Why it is here: our sweep, ledger, mutation-control and second-implementation
  numbers are all computed on exactly these bytes. Shipping them removes the
  download step, so `python tools/stranger_competitor_check.py` with no `--dir`
  runs offline on this copy.

What we claim about it: the numbers in `docs/COMPETITOR-CORPUS-SWEEP.md` and the
receipts under `docs/upstream-package/competitor-defects/` apply to these bytes.
What we do not claim: that these vectors are correct, or that their authors
endorse anything we say about them.
