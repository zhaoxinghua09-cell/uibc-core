"""Oracle check: expectations are written down before anything is run.

The difference from `independent_verifier/cross_check.py` is the direction of trust.
Cross-check asks "do two implementations agree?" - which cannot rule out both being wrong
the same way. This asks "does each implementation match a verdict that was written down
from the specification?" - so a shared misreading now fails here even when the two agree.

The table below is derived from `fixtures/EXPECTED.md` (the hand-derived prior) and from
`benchmarks.md` line on `duplicated` (S5 root mismatch). It was written before the runs;
changing it after seeing an output is the exact failure this tool exists to prevent.

Run:  python tools/oracle_check.py
Exit: 0 = both implementations match the oracle, 1 = at least one cell differs.
"""

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "independent_verifier"))

from uibc_core.verify import verify                      # noqa: E402
from uibc_core import cli as ucli                        # noqa: E402
from uibc_core.signing import generate_key               # noqa: E402
from iverify import independent_verify                   # noqa: E402
import outsider_audit as oa                              # noqa: E402  (mutations only)

V_TO_S = {"V1": "S1", "V2": "S2", "V3": "S3", "V4": "S4", "V5": "S5", "V6": "S6"}

# case name, mutation, expected top-level verdict, expected FIRST failing check in strict mode
ORACLE = [
    ("oracle-clean",      "none",      "PASS", None),
    ("oracle-tampered",   "tamper",    "FAIL", "S4"),
    ("oracle-deleted",    "delete",    "FAIL", "S4"),
    ("oracle-duplicated", "duplicate", "FAIL", "S5"),
    ("oracle-unsealed",   "unseal",    "FAIL", "S6"),
    # S12 on its own: duplicate the entry *and* repair the root and the count, so that
    # S5 has nothing to complain about and the identifier rule is the only thing left
    # to fail. An S12 case that also breaks S5 never proves S12 is doing work.
    ("oracle-s12-id-only", "dup_root", "FAIL", "S12"),
]

# Tranche two: the checks a CLI-built package cannot reach. Each row takes its
# expectation from `docs/CHECK-MATRIX.md`, which is committed evidence about which
# attack makes which check FAIL - written down before this tool ran.
#
# Honest limit: the matrix and the mutation functions below share one provenance
# (tools/outsider_audit.py). This tranche therefore locks in verdicts and first-failure
# codes against regressions; it is not an independent judgement, and it has no
# second implementation to compare with, because the independent verifier stops at V6.
ORACLE_EXT = [
    # name, prebuild (None = base package as is), mutation, verdict, first failure
    ("oracle-s01-undeclared-file",  None,         "m_add_undeclared_file",   "FAIL", "S1"),
    ("oracle-s02-identity",         None,         "m_identity_mismatch",     "FAIL", "S2"),
    ("oracle-s03-calendar",         None,         "m_bad_calendar_date",     "FAIL", "S3"),
    ("oracle-s08-log-truncated",    "build_ckpt", "m_ckpt_truncate_the_log", "FAIL", "S8"),
    ("oracle-s10-closure",          "build_ckpt", "m_ckpt_drop_closure_component", "FAIL", "S10"),
    ("oracle-s11-duplicate-member", None,            "m_duplicate_member",      "FAIL", "S11"),
    ("oracle-s13-merkle-root",      "build_v11",     "m13_merkle_root",         "FAIL", "S13"),
    ("oracle-s14-base64-padding",   "build_ext",     "m14_base64_padding",      "FAIL", "S14"),
    ("oracle-s15-anchor-time",      "build_ext",     "m15_bad_time",            "FAIL", "S15"),
    ("oracle-s16-token-byte",       "build_s16",     "m16_flip_token_byte",     "FAIL", "S16"),
    ("oracle-s17-receipt-body",     "build_v11",     "m17_receipt_body",        "FAIL", "S17"),
    ("oracle-s18-policy-artefact",  "build_ext",     "m18_edited_artefact",     "FAIL", "S18"),
    ("oracle-s07-index-metadata",   "build_ckpt",    "m_ckpt_rewrite_index_note", "FAIL", "S7"),
]

# Tranche four: the other half of the oracle. A table of cases that must FAIL says
# nothing about false alarms, and a verifier that fails everything would pass all
# twenty-one of them. These rows are legitimate packages that must be ACCEPTED: the
# ordinary shapes a real agent produces, not attacks. Every row is expected PASS in
# strict mode (owner key supplied), so a rejection here is a false alarm and is
# scored as a disagreement with the oracle.
ORACLE_ACCEPT = [
    ("accept-one-file",       "one"),
    ("accept-many-files",     "many"),
    ("accept-unicode-names",  "unicode"),
    ("accept-binary",         "binary"),
    ("accept-large-text",     "large"),
    ("accept-resubmitted",    "resubmit"),
]


def build_good(tmp, name, variant):
    """A legitimate package. Nothing here is an attack: these are shapes real use produces."""
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "accept", "owner": "accept",
        "agent_type": "software-agent", "version": "1"})())

    files = []
    if variant == "one":
        files = [("log.txt", "one action\n")]
    elif variant == "many":
        files = [(f"step-{i}.txt", f"step {i}\n") for i in range(5)]
    elif variant == "unicode":
        files = [("运行日志.txt", "代理执行了一次检索\n第二行中文\n"),
                 ("résumé.md", "accented filename\n")]
    elif variant == "binary":
        files = [("blob.bin", b"\x89PNG\r\n\x1a\n" + bytes(range(64)))]
    elif variant == "large":
        files = [("big.txt", "x" * 200000 + "\n")]
    elif variant == "resubmit":
        files = [("log.txt", "one action\n")]
    else:
        raise ValueError(variant)

    for fname, content in files:
        src = os.path.join(tmp, f"{name}-{fname}")
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(src, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
            f.write(content)
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "ACTION", "file": src,
            "media_type": "text/plain", "note": fname})())

    key = generate_key()
    kf = os.path.join(tmp, f"{name}.key")
    with open(kf, "w", encoding="ascii") as f:
        f.write(key.hex())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    if variant == "resubmit":
        # a second submission is ordinary: the agent sealed, then sealed again
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    return pkg, key


def build(tmp, name, mutation, nevid=1):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "oracle", "owner": "oracle",
        "agent_type": "software-agent", "version": "1"})())
    for i in range(nevid):
        src = os.path.join(tmp, f"{name}-{i}.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write(f"oracle {name} {i}\n")
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "ACTION", "file": src,
            "media_type": "text/plain", "note": f"n{i}"})())
    key = generate_key()
    kf = os.path.join(tmp, f"{name}.key")
    with open(kf, "w", encoding="ascii") as f:
        f.write(key.hex())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    mutate(pkg, name, mutation)
    if mutation == "dup_root":
        # re-seal after the edit: otherwise the seal (S6) fails and the case never
        # reaches the identifier rule it was built to test.
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    return pkg, key


def mutate(pkg, name, mutation):
    idx_path = os.path.join(pkg, "evidence", "index.json")
    if mutation == "none":
        return
    idx = json.load(open(idx_path, encoding="utf-8"))
    first = os.path.join(pkg, "evidence", idx["entries"][0]["path"].replace("\\", "/"))
    if mutation == "tamper":
        with open(first, "a", encoding="utf-8") as f:
            f.write("TAMPERED\n")
        return
    if mutation == "delete":
        os.remove(first)
        return
    if mutation == "duplicate":
        idx = json.load(open(idx_path, encoding="utf-8"))
        idx["entries"].append(dict(idx["entries"][0]))
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
        return
    if mutation == "dup_root":
        # duplicate the first entry; the re-seal that follows rewrites manifest and
        # signature from the index, so only the identifier rule (S12) can fail.
        idx["entries"].append(dict(idx["entries"][0]))
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
        return
    if mutation == "unseal":
        # EXPECTED.md: strict mode, unsigned package FAILs at S6.
        seal = os.path.join(pkg, "signatures", "seal.json")
        if os.path.exists(seal):
            os.remove(seal)
        return
    raise ValueError(mutation)


def reseal(pkg, key):
    """Re-sign the manifest with the same key after a deliberate edit.

    S9 and S19 need a package that is internally consistent *except* for the one
    thing under test, so the seal has to be restored or S6 would answer first.
    """
    from uibc_core.signing import seal_sign
    ident = json.load(open(os.path.join(pkg, "identity.json"), encoding="utf-8"))
    man = json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))
    lc = json.load(open(os.path.join(pkg, "lifecycle.json"), encoding="utf-8"))
    sp = os.path.join(pkg, "signatures", "seal.json")
    seal = json.load(open(sp, encoding="utf-8"))
    seal["signature"] = seal_sign(key, ident, man, lc)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(seal, f, indent=2, sort_keys=True)


def checkpoint_of(pkg):
    """The head the package commits to, derived the same way the verifier derives it."""
    from uibc_core import canonical as ca
    man = json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))
    lc = json.load(open(os.path.join(pkg, "lifecycle.json"), encoding="utf-8"))
    idx = json.load(open(os.path.join(pkg, "evidence", "index.json"), encoding="utf-8"))
    return ca.checkpoint_head(ca.lifecycle_head(lc["events"]),
                              man["evidence_root"],
                              ca.index_metadata_digest(idx),
                              len(idx["entries"]))


def first_fail(checks):
    """First failing check in CHECK-NUMBER order, not in report order.

    The report is not printed in S order (measured: S11, S1, S2, S3, S4, S12, S7, S8,
    S5, S6 on a duplicated package), so "first failure" is undefined unless the ordering
    rule is fixed. This tool fixes it: lowest check number that fails.
    """
    def num(cid):
        digits = "".join(ch for ch in cid if ch.isdigit())
        return int(digits) if digits else 10 ** 6

    failing = [c["id"] for c in checks if c["result"] == "FAIL"]
    return min(failing, key=num) if failing else None


def ref_view(pkg, key, rep=None):
    rep = rep or verify(pkg, key=key)
    return rep["result"], first_fail(rep["checks"])


def ind_view(pkg, key):
    out = independent_verify(pkg, key=key)
    checks = [{"id": V_TO_S.get(k, k), "result": v} for k, v in out["checks"].items()]
    checks.sort(key=lambda c: c["id"])
    return out["result"], first_fail(checks)


def main():
    rows, bad = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, mutation, want_verdict, want_first in ORACLE:
            pkg, key = build(tmp, name, mutation)
            r_verdict, r_first = ref_view(pkg, key)
            i_verdict, i_first = ind_view(pkg, key)
            r_ok = (r_verdict == want_verdict and r_first == want_first)
            # The independent verifier implements V1-V6 only. A case whose expected
            # first failure is above S6 is outside what it can see, so it is recorded
            # rather than scored: scoring it would report a "pass" that means "blind".
            beyond = want_first is not None and int(want_first[1:]) > 6
            i_ok = None if beyond else (i_verdict == want_verdict and i_first == want_first)
            bad += 0 if r_ok else 1
            bad += 0 if (i_ok in (True, None)) else 1
            rows.append((name, want_verdict, str(want_first), r_verdict, str(r_first),
                         i_verdict, str(i_first), r_ok, i_ok))

        for name, prebuild, fn_name, want_verdict, want_first in ORACLE_EXT:
            pkg, _key = build(tmp, name, "none", nevid=2)
            if prebuild:
                getattr(oa, prebuild)(pkg)
            getattr(oa, fn_name)(pkg)
            rep = verify(pkg)
            r_verdict, r_first = ref_view(pkg, None, rep=rep)
            r_ok = (r_verdict == want_verdict and r_first == want_first)
            bad += 0 if r_ok else 1
            # no second implementation above V6: recorded, not scored
            rows.append((name, want_verdict, str(want_first), r_verdict, str(r_first),
                         "n/a", "n/a", r_ok, None))

        # --- S9: a self-consistent package judged against someone else's head ---
        pkg_a, key_a = build(tmp, "oracle-s09-old", "none", nevid=1)
        pkg_b, _kb = build(tmp, "oracle-s09-new", "none", nevid=2)
        want_head = checkpoint_of(pkg_b)          # the head observed elsewhere
        rep = verify(pkg_a, expect_head=want_head)
        r_verdict, r_first = ref_view(pkg_a, None, rep=rep)
        r_ok = (r_verdict == "FAIL" and r_first == "S9")
        bad += 0 if r_ok else 1
        rows.append(("oracle-s09-rollback-pin", "FAIL", "S9", r_verdict, str(r_first),
                     "n/a", "n/a", r_ok, None))

        # --- S19: a package whose sequence went backwards, remembered state ---
        state_file = os.path.join(tmp, "freshness.json")
        pkg_c, key_c = build(tmp, "oracle-s19", "none", nevid=2)
        man_path = os.path.join(pkg_c, "manifest.json")
        man = json.load(open(man_path, encoding="utf-8"))
        man["freshness_head"] = {"subject": "oracle", "sequence": 5}
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(man, f, indent=2, sort_keys=True)
        reseal(pkg_c, key_c)
        verify(pkg_c, state_file=state_file)      # first observation: records the mark
        man = json.load(open(man_path, encoding="utf-8"))
        man["freshness_head"]["sequence"] = 3     # ...validly signed, but from earlier
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(man, f, indent=2, sort_keys=True)
        reseal(pkg_c, key_c)
        rep = verify(pkg_c, state_file=state_file)
        r_verdict, r_first = ref_view(pkg_c, None, rep=rep)
        r_ok = (r_verdict == "FAIL" and r_first == "S19")
        bad += 0 if r_ok else 1
        rows.append(("oracle-s19-regressed", "FAIL", "S19", r_verdict, str(r_first),
                     "n/a", "n/a", r_ok, None))

        # --- tranche four: legitimate packages must be accepted, not merely "not attacked" ---
        for name, variant in ORACLE_ACCEPT:
            pkg, key = build_good(tmp, name, variant)
            rep = verify(pkg, key=key)
            r_verdict, r_first = ref_view(pkg, None, rep=rep)
            i_verdict, i_first = ind_view(pkg, key)
            r_ok = (r_verdict == "PASS")
            i_ok = (i_verdict == "PASS")
            bad += 0 if r_ok else 1
            bad += 0 if i_ok else 1
            rows.append((name, "PASS", "—", r_verdict, str(r_first),
                         i_verdict, str(i_first), r_ok, i_ok))

    print(f"{'case':<26}{'oracle':<8}{'o-first':<9}{'ref':<8}{'r-first':<9}"
          f"{'ind':<8}{'i-first':<9}{'ref?':<6}{'ind?'}")
    for name, ov, of, rv, rf, iv, iff, rok, iok in rows:
        mark = "OK" if rok else "DIFF"
        imark = "n/a" if iok is None else ("OK" if iok else "DIFF")
        print(f"{name:<26}{ov:<8}{of:<9}{rv:<8}{rf:<9}{iv:<8}{iff:<9}{mark:<6}{imark}")

    print(f"\ncases: {len(rows)}, cells disagreeing with the oracle: {bad}")
    print("ORACLE: " + ("PASS - both implementations match the written expectations"
                        if bad == 0 else "FAIL - an implementation disagrees with the oracle"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
