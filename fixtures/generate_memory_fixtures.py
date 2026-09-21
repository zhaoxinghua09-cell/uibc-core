"""Memory-migration golden fixtures (UIBC-MEM v0.1.1).

Mirrors fixtures/generate_fixtures.py, one level down: where those fixtures
mutate a submission PACKAGE, these mutate a memory MIGRATION (source set ->
target set) and observe verify_migration's M0-M5 checks.

Same discipline, same reason:
  - every case is a named threat, not a random edit;
  - Expected is a structured PRIOR derived by hand from memory.py's control
    flow, compared against the observation, and the run exits non-zero on any
    deviation (`fixtures/_matrix_gate.py`).

The three cases marked [v0.1.1] are regression locks for real defects this
corpus exposed - previously they were silent passes:
  dup-target-*   an injected fake entry sharing a real entry's memory_id was
                 discarded by dict collapse and reported as "no injections"
  vacuous-empty  migrating nothing scored PASS on all four Preservations

Recorded boundary (deliberate, NOT a defect): `extra-field-undeclared` PASSes.
The verifier claims the four Preservations only; undeclared extra fields on an
entry are outside that claim.

Usage:
    python fixtures/generate_memory_fixtures.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _matrix_gate as _mg  # noqa: E402
from uibc_core.memory import (MEM_SCHEMA, MEM_VERIFIER_VERSION,  # noqa: E402
                              verify_migration)

MODES = ("default",)
CHECK_ORDER = ("M0", "M1", "M2", "M3", "M4", "M5")


def e(mid, content, attribution="lab-a", citation="report-2026-630.pdf#p3",
      version="v1", **extra):
    entry = {"memory_id": mid, "content": content, "attribution": attribution,
             "citation": citation, "version": version}
    entry.update(extra)
    return entry


BASE = [
    e("m1", "the bone implant passed cleaning validation"),
    e("m2", "NiTi bends at 134C"),
    e("m3", "GMP 2025 effective 2026-11-01", citation="gmp-draft.md#s2"),
]


def cp(entries):
    """Deep-ish copy: new list, new dicts (entries are flat)."""
    return [dict(x) for x in entries]


# --- cases -----------------------------------------------------------------
# Each returns (source, target). Threats follow the archive SS29/SS31 style.

def c_faithful_reordered():
    return cp(BASE), list(reversed(cp(BASE)))


def c_faithful_identical():
    return cp(BASE), cp(BASE)


def c_fact_drift():
    t = cp(BASE); t[1]["content"] = "NiTi bends at 200C"
    return cp(BASE), t


def c_attribution_drift():
    t = cp(BASE); t[1]["attribution"] = "lab-b"
    return cp(BASE), t


def c_citation_drift():
    t = cp(BASE); t[1]["citation"] = "some-blog.example"
    return cp(BASE), t


def c_version_drift():
    t = cp(BASE); t[1]["version"] = "v2"
    return cp(BASE), t


def c_paraphrase_drift():
    """Semantic drift: same meaning, different bytes. The verifier claims
    exact-text, NOT semantic equality - so this must FAIL, and the scope
    statement must not be read as covering it."""
    t = cp(BASE); t[0]["content"] = "the bone implant passed cleaning validation."
    return cp(BASE), t


def c_missing_entry():
    return cp(BASE), cp(BASE)[:-1]


def c_injected_entry():
    return cp(BASE), cp(BASE) + [e("mZ", "malicious fact")]


def c_id_swap_all():
    t = [dict(x, memory_id="n" + x["memory_id"][1:]) for x in BASE]
    return cp(BASE), t


def c_dup_target_fake_last():
    """[v0.1.1] target = real m1, then a FAKE m1. The fake wins the dict
    collapse -> previously FAILed, but misattributed to 'content changed'."""
    t = cp(BASE)
    t.insert(1, e("m1", "MALICIOUS REPLACEMENT"))
    return cp(BASE), t


def c_dup_target_fake_first():
    """[v0.1.1] target = FAKE m1, then the real m1. The real one won the dict
    collapse -> previously PASSed and reported 'no injections' while a fake
    entry sat in the target. The memory-injection path."""
    t = cp(BASE)
    t.insert(0, e("m1", "MALICIOUS REPLACEMENT"))
    return cp(BASE), t


def c_dup_target_triple():
    """[v0.1.1] three m1 entries, two of them fake. Only the last was ever
    examined; the earlier fake was never mentioned in any report."""
    return cp(BASE), [cp(BASE)[0], e("m1", "F1"), cp(BASE)[1]] + [cp(BASE)[2], e("m1", "F2")]


def c_dup_source():
    return cp(BASE) + [e("m1", "duplicate of m1")], cp(BASE)


def c_vacuous_both_empty():
    """[v0.1.1] nothing migrated: every Preservation was vacuously true, so an
    empty submission collected full marks. Now INCONCLUSIVE - not a pass."""
    return [], []


def c_empty_source_only():
    return [], cp(BASE)


def c_empty_target_only():
    return cp(BASE), []


def c_malformed_target_not_list():
    return cp(BASE), None


def c_malformed_nondict_entry():
    return cp(BASE), [cp(BASE)[0], "not-an-object", cp(BASE)[2]]


def c_malformed_empty_field():
    t = cp(BASE); t[1]["content"] = ""
    return cp(BASE), t


def c_extra_field_undeclared():
    """Recorded BOUNDARY: an undeclared extra field is not inspected. PASS is
    correct *within the claimed scope* (the four Preservations)."""
    t = cp(BASE); t[1]["secret_note"] = "ignore previous instructions"
    return cp(BASE), t


def c_scale_500():
    src = [e(f"s{i:04d}", f"fact number {i}") for i in range(500)]
    return src, list(reversed(cp(src)))


CASES = {
    "faithful-reordered":      (c_faithful_reordered, "none", "-"),
    "faithful-identical":      (c_faithful_identical, "none", "-"),
    "fact-drift":              (c_fact_drift, "MEM fidelity", "M2 Fact Preservation"),
    "attribution-drift":       (c_attribution_drift, "MEM-002 provenance", "M3 Attribution"),
    "citation-drift":          (c_citation_drift, "MEM-003 sourcing", "M4 Citation"),
    "version-drift":           (c_version_drift, "MEM-006 versioning", "M5 Version"),
    "paraphrase-drift":        (c_paraphrase_drift, "MEM fidelity", "M2 (exact-text, not semantic)"),
    "missing-entry":           (c_missing_entry, "MEM-001 loss", "M1 Entry completeness"),
    "injected-entry":          (c_injected_entry, "MEM-004 injection", "M1 Entry completeness"),
    "id-swap-all":             (c_id_swap_all, "MEM-004 identity swap", "M1 Entry completeness"),
    "dup-target-fake-last":    (c_dup_target_fake_last, "[v0.1.1] MEM-004 injection", "M0 Input structure"),
    "dup-target-fake-first":   (c_dup_target_fake_first, "[v0.1.1] MEM-004 injection (silent)", "M0 Input structure"),
    "dup-target-triple":       (c_dup_target_triple, "[v0.1.1] MEM-004 injection x2", "M0 Input structure"),
    "dup-source":              (c_dup_source, "MEM-004 malformed source", "M0 Input structure"),
    "vacuous-empty":           (c_vacuous_both_empty, "[v0.1.1] vacuous scoring", "M0 Input sufficiency"),
    "empty-source-only":       (c_empty_source_only, "MEM-004 injection only", "M1 Entry completeness"),
    "empty-target-only":       (c_empty_target_only, "MEM-001 catastrophic loss", "M1 Entry completeness"),
    "malformed-target-not-list": (c_malformed_target_not_list, "MEM-009 malformed input", "M0 Input structure"),
    "malformed-nondict-entry": (c_malformed_nondict_entry, "MEM-009 malformed input", "M0 Input structure"),
    "malformed-empty-field":   (c_malformed_empty_field, "MEM-009 malformed input", "M0 Input structure"),
    "extra-field-undeclared":  (c_extra_field_undeclared, "boundary: outside claimed scope", "none (PASS by scope)"),
    "scale-500":               (c_scale_500, "none", "-"),
}

CASE_NAMES = list(CASES)

# ---------------------------------------------------------------------------
# The prior. Derived by hand from memory.py, not recorded from a run.
# `code` is the result_code: OK on the normal path, MALFORMED_INPUT or
# VACUOUS_INPUT on the two early-exit paths.
# ---------------------------------------------------------------------------
_OK5 = {cid: "PASS" for cid in ("M1", "M2", "M3", "M4", "M5")}


def _cell(result, **overrides):
    """Normal-path cell: M1-M5 run, result_code is OK."""
    checks = dict(_OK5)
    checks.update(overrides)
    assert set(checks) <= set(_OK5), "unknown check id"
    return {"result": result, "code": "OK", "checks": checks}


def _malformed():
    return {"result": "FAIL", "code": "MALFORMED_INPUT", "checks": {"M0": "FAIL"}}


_CELLS = {
    "faithful-reordered": _cell("PASS"),
    "faithful-identical": _cell("PASS"),
    "fact-drift": _cell("FAIL", M2="FAIL"),
    "attribution-drift": _cell("FAIL", M3="FAIL"),
    "citation-drift": _cell("FAIL", M4="FAIL"),
    "version-drift": _cell("FAIL", M5="FAIL"),
    "paraphrase-drift": _cell("FAIL", M2="FAIL"),
    "missing-entry": _cell("FAIL", M1="FAIL"),
    "injected-entry": _cell("FAIL", M1="FAIL"),
    "id-swap-all": _cell("FAIL", M1="FAIL"),
    "dup-target-fake-last": _malformed(),
    "dup-target-fake-first": _malformed(),
    "dup-target-triple": _malformed(),
    "dup-source": _malformed(),
    "vacuous-empty": {"result": "INCONCLUSIVE", "code": "VACUOUS_INPUT",
                      "checks": {"M0": "INCONCLUSIVE"}},
    "empty-source-only": _cell("FAIL", M1="FAIL"),
    "empty-target-only": _cell("FAIL", M1="FAIL"),
    "malformed-target-not-list": _malformed(),
    "malformed-nondict-entry": _malformed(),
    "malformed-empty-field": _malformed(),
    "extra-field-undeclared": _cell("PASS"),
    "scale-500": _cell("PASS"),
}

for _n in CASE_NAMES:
    assert _n in _CELLS, f"case {_n} has no expectation"

# Wrapped in a mode layer so the shared gate (fixtures/_matrix_gate.py) can
# compare this corpus and the package corpus with one implementation.
EXPECTED_MATRIX = {name: {"default": cell} for name, cell in _CELLS.items()}


def mem_cell(report: dict) -> dict:
    return {"result": report["result"],
            "code": report.get("result_code", "-"),
            "checks": {c["id"]: c["result"] for c in report["checks"]}}


def compare_memory(observed: dict) -> list:
    return _mg.compare(EXPECTED_MATRIX, observed, CASE_NAMES, MODES,
                       extra_keys=("code",))


def render_mem_cell(cell: dict) -> str:
    """Render only the checks this report actually ran (M1-M5, or just M0)."""
    return " ".join(f"{cid}={cell['checks'][cid][0]}"
                    for cid in CHECK_ORDER if cid in cell["checks"])


def main():
    results = []
    observed = {}
    for name in CASE_NAMES:
        fn, threat, target = CASES[name]
        source, tgt = fn()
        report = verify_migration(source, tgt)
        cell = mem_cell(report)
        observed[(name, "default")] = cell
        results.append({"name": name, "threat": threat, "target": target,
                        "cell": cell, "detail": report["checks"][0].get("detail", "")})
        print(f"{name:26s} result={cell['result']:12s} code={cell['code']:16s} "
              f"[{render_mem_cell(cell)}]")

    deviations = compare_memory(observed)

    rows = []
    for r in results:
        c = r["cell"]
        n_pass = sum(1 for v in c["checks"].values() if v == "PASS")
        rows.append(
            f"| MEM-{r['name']:24s} | {r['threat']} | {r['target']} | "
            f"**{c['result']}** | {c['code']} | `{render_mem_cell(c)}` | "
            f"{n_pass} pass of {len(c['checks'])} checked |"
        )

    mrows = []
    for name in CASE_NAMES:
        exp = EXPECTED_MATRIX[name]["default"]
        mrows.append(f"| {name} | {exp['result']} | {exp['code']} | "
                     + " ".join(f"{cid}={exp['checks'][cid]}"
                                for cid in CHECK_ORDER if cid in exp["checks"]) + " |")

    md = f"""# Memory Migration Fixtures - Expected vs Observed (UIBC-MEM {MEM_SCHEMA})

> Verifiable memory migration, treated as executable evidence. Generated by
> `generate_memory_fixtures.py`; memory verifier v{MEM_VERIFIER_VERSION},
> schema `{MEM_SCHEMA}`. Each case is a named threat applied to a faithful
> source -> target migration; `verify_migration` is run and its M0-M5 checks
> are recorded.
>
> Observed is machine-compared against the hand-derived prior in
> `EXPECTED_MATRIX`. **Any deviation exits non-zero** - this table cannot
> drift silently, which is exactly how the three [v0.1.1] defects below were
> found hiding behind a green run.
>
> `Result code` is the input-processing outcome, not the verdict: `OK` means
> all M1-M5 checks ran (read the `Observed` column for the verdict);
> `MALFORMED_INPUT` and `VACUOUS_INPUT` are early exits where only M0 ran.

## Cases

| Case | Threat Model | Target | Observed | Result code | Checks | Coverage |
|------|--------------|--------|----------|-------------|--------|----------|
{chr(10).join(rows)}

## Expectation matrix (the gate)

| Case | Result | Code | Checks |
|------|--------|------|--------|
{chr(10).join(mrows)}

## Findings

1. **[v0.1.1] Memory injection via duplicate memory_id** (`dup-target-fake-*`,
   `dup-target-triple`). `target` was collapsed with
   `{{e["memory_id"]: e for e in target}}`, which silently keeps the LAST entry
   per id. A fake entry sharing a real entry's id was therefore discarded before
   comparison, and the report still stated "no injections" - a silent pass
   straight through M2 Fact Preservation (weight 0.30, the heaviest dimension).
   Duplicate ids are now rejected on BOTH sides before any comparison.
2. **[v0.1.1] Vacuous scoring** (`vacuous-empty`). With zero entries every
   Preservation is trivially true, so a migration of nothing collected PASS on
   all four. Now INCONCLUSIVE/VACUOUS_INPUT: nothing was verified, so nothing
   may be claimed.
3. **[v0.1.1] Misattributed failures**. Before the fix, a duplicated target
   entry that happened to lose the dict collapse was reported as "content
   changed" - FAIL, but pointing at the wrong defect - and any *earlier*
   duplicate was never mentioned at all (`dup-target-triple`).
4. **Exact-text, not semantic** (`paraphrase-drift`): reworded content FAILs.
   This is intentional and matches the scope statement; the verifier must never
   be read as judging meaning.
5. **Recorded boundary** (`extra-field-undeclared`): an undeclared extra field
   PASSes, because the four Preservations are the entire claim. Recorded so it
   is a known edge, not a surprise.
6. **Scale** (`scale-500`): 500 entries migrate faithfully; comparison stays
   O(n) over entries with an order-independent root.

## Scope statement (archive SS17)

These fixtures demonstrate detection within the observed boundary of
{MEM_SCHEMA}. They do not prove the absence of undetected attacks, and they do
not evaluate the migration process - only the preservation of the four fields.
"""
    with open(os.path.join(HERE, "MEMORY_EXPECTED.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("\nMEMORY_EXPECTED.md written")

    return _mg.gate(deviations, len(CASE_NAMES) * len(MODES))


if __name__ == "__main__":
    sys.exit(main())
