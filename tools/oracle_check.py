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

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "independent_verifier"))

from uibc_core.verify import verify                      # noqa: E402
from uibc_core import cli as ucli                        # noqa: E402
from uibc_core.signing import generate_key  # unused by _oracle_key; kept for build_bad               # noqa: E402
from iverify import independent_verify                   # noqa: E402
import outsider_audit as oa                              # noqa: E402  (mutations only)

V_TO_S = {"V1": "S1", "V2": "S2", "V3": "S3", "V4": "S4", "V5": "S5", "V6": "S6"}
# What the independent implementation emits as of v1.1. It is not V1-V6 only: three parity
# rules were added after the benchmark corpus showed it missing them, and they pair with
# parts of S1/S7/S8 rather than with whole checks. Counting nine rules as "nine checks
# covered" would be the same overclaim this repository keeps catching in others.
IND_RULES = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9"]

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
    # Tranche five: the shapes the reject side mutates, built correctly. A accept table
    # of plain packages says nothing about policy, anchor or lifecycle artefacts, which
    # is where the interesting rules live. These three are the legitimate versions of
    # the S14/S15/S18 and actor/sequence machinery.
    ("accept-typed-evidence",  "typed"),
    ("accept-lifecycle-events", "lifecycle"),
    ("accept-anchored-policy", "anchored"),
]


def measure_rule_correspondence(tmp):
    """Measure, do not assert, what the second implementation's extra rules correspond to.

    Each probe breaks exactly one thing and then re-seals, so the seal is valid and the
    seal complaint cannot answer first. Whatever each side reports is then the rule itself.
    """
    probes = [
        ("V7", "m_add_undeclared_file", None),
        ("V8", "m_ckpt_rewrite_index_note", "build_ckpt"),
        ("V9", "m_ckpt_truncate_the_log", "build_ckpt"),
    ]
    out = []
    for rule, fn, prebuild in probes:
        pkg, key = build(tmp, "corr-" + rule, "none")
        if prebuild:
            getattr(oa, prebuild)(pkg)
        getattr(oa, fn)(pkg)
        reseal(pkg, key)
        rep = verify(pkg, key=key)
        ref_failed = [c["id"] for c in rep["checks"] if c["result"] != "PASS"]
        ind = independent_verify(pkg, key=key)
        ind_failed = [k for k, v in ind["checks"].items() if v != "PASS"]
        out.append((rule, ref_failed, rep["result"], ind_failed, ind["result"]))
    return out


def measure_blind_verdict(tmp):
    """Does the second implementation fall silent, or say PASS, where it has no rule?

    This is the question a coverage percentage cannot answer. INCONCLUSIVE and PASS are
    different reports about the same package, and only one of them is honest when the
    rule is missing.
    """
    pkg, key = build(tmp, "blind-s10", "none")
    oa.build_ckpt(pkg)
    oa.m_ckpt_drop_closure_component(pkg)
    reseal(pkg, key)
    rep = verify(pkg, key=key)
    ind = independent_verify(pkg, key=key)
    return rep["result"], ind["result"]


def measure_false_pass(tmp):
    """How often the second implementation says PASS on a package the reference rejects.

    This is the number a coverage percentage hides. Before the scope guard it was 9 of 20;
    after it, every one of those became INCONCLUSIVE, which is a statement about the
    verifier rather than about the package.
    """
    hostile = []
    for name, mutation, _v, _f in ORACLE:
        if mutation == "none":
            continue
        pkg, key = build(tmp, "fp-" + name, mutation)
        ref = verify(pkg, key=key)
        ind = independent_verify(pkg, key=key)
        hostile.append((name, ref["result"], ind["result"]))
    for name, prebuild, fn, _v, _f in ORACLE_EXT:
        pkg, key = build(tmp, "fp-" + name, "none", nevid=2)
        if prebuild:
            getattr(oa, prebuild)(pkg)
        getattr(oa, fn)(pkg)
        reseal(pkg, key)
        ref = verify(pkg, key=key)
        ind = independent_verify(pkg, key=key)
        hostile.append((name, ref["result"], ind["result"]))
    false_pass = [n for n, r, i in hostile if i == "PASS" and r != "PASS"]
    declined = [n for n, r, i in hostile if i == "INCONCLUSIVE" and r != "PASS"]
    return len(hostile), false_pass, declined


def measure_decidability(tmp):
    """For each check the corpus actually exercises: can the second implementation decide it?

    "6 of 19 exactly paired" is a statement about identifiers. This is a statement about
    behaviour: on packages where the reference fails check S, did the second implementation
    ever reach FAIL, or did it decline, or - the bad case - pass?
    """
    rows = {}

    def note(ref_ids, ind_verdict):
        for cid in ref_ids:
            r = rows.setdefault(cid, {"failed": 0, "detected": 0, "declined": 0, "green": 0})
            r["failed"] += 1
            if ind_verdict == "FAIL":
                r["detected"] += 1
            elif ind_verdict == "INCONCLUSIVE":
                r["declined"] += 1
            else:
                r["green"] += 1

    for name, mutation, _v, _f in ORACLE:
        if mutation == "none":
            continue
        pkg, key = build(tmp, "dec-" + name, mutation)
        rep = verify(pkg, key=key)
        ind = independent_verify(pkg, key=key)
        note([c["id"] for c in rep["checks"] if c["result"] != "PASS"], ind["result"])
    for name, prebuild, fn, _v, _f in ORACLE_EXT:
        pkg, key = build(tmp, "dec-" + name, "none", nevid=2)
        if prebuild:
            getattr(oa, prebuild)(pkg)
        getattr(oa, fn)(pkg)
        reseal(pkg, key)
        rep = verify(pkg, key=key)
        ind = independent_verify(pkg, key=key)
        note([c["id"] for c in rep["checks"] if c["result"] != "PASS"], ind["result"])
    reachable = sorted(rows, key=lambda c: int(c[1:]))
    decided = [c for c in reachable if rows[c]["detected"]]
    never = [c for c in reachable if not rows[c]["detected"]]
    return reachable, decided, never


def measure_declared_scope(tmp):
    """How much each implementation says it did not check, on the same packages.

    A verdict is read as broader than its evidence unless it says otherwise. The reference
    ships a fixed `not_checked` list, identical on every package; the second implementation
    declares both its standing non-goals and whatever this run found it had no rule for.
    """
    theme = {"merkle": "merkle", "anchor": "anchor", "timestamp": "timestamp",
             "receipt": "receipt", "polic": "policy", "base64": "base64",
             "closure": "closure", "duplicate json": "duplicate json",
             "duplicate evidence": "duplicate evidence",
             "behavioural": "behavioural", "behavioral": "behavioural",
             "memory": "memory", "lifecycle event signature": "lifecycle event signature"}

    def keys(items):
        out = set()
        for it in items:
            low = it.lower()
            for needle, k in theme.items():
                if needle in low:
                    out.add(k)
        return out

    pkg, key = build(tmp, "decl-plain", "none")
    pkg2, key2 = build(tmp, "decl-ext", "none", nevid=2)
    oa.build_ckpt(pkg2)
    reseal(pkg2, key2)
    ref_items = set()
    ind_items = set()
    for target, k in ((pkg, key), (pkg2, key2)):
        ref_items |= keys(verify(target, key=k).get("not_checked") or [])
        ind_items |= keys(independent_verify(target, key=k)["not_checked"])
    only_ind = ind_items - ref_items
    only_ref = ref_items - ind_items
    return len(ref_items), len(ind_items), sorted(only_ind), sorted(only_ref)


def emit_corpus(dest, only=None):
    """Materialise the corpus as data a third party can run without our tooling.

    Everything above checks our two implementations against each other inside one
    process. That is useful and it is not consumable: an outside verifier cannot run
    this code. Emission writes the packages, the throwaway keys, and the expected
    verdicts to disk, then re-verifies the *written copies* and refuses to report
    success unless the copied bytes still produce the declared answers. If the corpus
    and its answers could drift apart, publishing them would be worse than not
    publishing at all.
    """
    os.makedirs(dest, exist_ok=True)
    # Ids and keys are derived, not drawn, so that a second run of this command
    # produces the same bytes; the remaining variable is the clock, and that is
    # the caller's SOURCE_DATE_EPOCH. Unpinned, the corpus still emits, it just
    # cannot be rebuilt by a stranger - which is the thing this exists to avoid.
    os.environ.setdefault("UIBC_REPRO_SEED", "uibc-oracle/1")
    cases_dir = os.path.join(dest, "cases")
    os.makedirs(cases_dir, exist_ok=True)
    expected = []
    keys = {}
    want_names = set(only) if only else None

    def keep(name):
        return want_names is None or name in want_names

    work = tempfile.mkdtemp()
    for name, mutation, want_verdict, want_first in ORACLE:
        if not keep(name):
            continue
        pkg, key = build(work, name, mutation)
        target = os.path.join(cases_dir, name)
        shutil.copytree(pkg, target, dirs_exist_ok=True)
        keys[name] = key.hex()
        expected.append({"case": name, "kind": "reject-or-accept", "mode": "strict",
                         "expected_verdict": want_verdict,
                         "expected_first_fail": want_first})
    for name, prebuild, fn_name, want_verdict, want_first in ORACLE_EXT:
        if not keep(name):
            continue
        pkg, key = build(work, name, "none", nevid=2)
        if prebuild:
            getattr(oa, prebuild)(pkg)
        getattr(oa, fn_name)(pkg)
        target = os.path.join(cases_dir, name)
        shutil.copytree(pkg, target, dirs_exist_ok=True)
        keys[name] = key.hex()
        expected.append({"case": name, "kind": "reject", "mode": "open",
                         "expected_verdict": want_verdict,
                         "expected_first_fail": want_first})
    for name, variant in ORACLE_ACCEPT:
        if not keep(name):
            continue
        pkg, key = build_good(work, name, variant)
        target = os.path.join(cases_dir, name)
        shutil.copytree(pkg, target, dirs_exist_ok=True)
        keys[name] = key.hex()
        expected.append({"case": name, "kind": "accept", "mode": "strict",
                         "expected_verdict": "PASS", "expected_first_fail": None})

    with open(os.path.join(dest, "expected.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"spec": "uibc", "cases": expected}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(dest, "keys.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"note": "throwaway test keys; these packages are synthetic",
                   "keys": keys}, f, indent=2)

    # Round trip on the written copies, not on the in-memory packages.
    mismatches = []
    for row in expected:
        case_dir = os.path.join(cases_dir, row["case"])
        key = bytes.fromhex(keys[row["case"]]) if row.get("mode") == "strict" else None
        verdict, first = ref_view(case_dir, key)
        if verdict != row["expected_verdict"] or first != row["expected_first_fail"]:
            mismatches.append((row["case"], verdict, str(first),
                               row["expected_verdict"], str(row["expected_first_fail"])))
    with open(os.path.join(dest, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(EMIT_README % (len(expected), len(mismatches)))
    return len(expected), mismatches


EMIT_README = """# UIBC conformance corpus

%d cases, each a complete submission package plus the verdict it must produce.
Written by `python tools/oracle_check.py --emit <dir>`; the answers were checked
against the bytes on disk after writing, so what you read here is what the files
do (mismatches at emit time: %d).

## Rebuilding these bytes

The corpus is reproducible, not merely consistent. Emit it with the same clock
and you get the same files:

    SOURCE_DATE_EPOCH=1794700800 python tools/oracle_check.py --emit <empty dir>

Every `created_at` comes from that epoch instead of the wall clock, and every
`event_id`, `evidence_id` and file name prefix is derived from a fixed seed
(`UIBC_REPRO_SEED`, set by `--emit`) instead of `uuid4`, so a second run asking
in the same order gets the same identifiers. `tests/test_oracle_reproducible.py`
rebuilds the corpus and compares bytes; it fails if that stops being true.
Without `SOURCE_DATE_EPOCH` the corpus still emits and still round-trips - it
just cannot be rebuilt, which is the thing worth not doing.

## How to use it with any verifier

1. Take `cases/<name>/` as the package.
2. Read `keys.json` for that case. If `mode` is `strict`, verify in strict
   (owner-key) mode exactly as `uibc verify <path> --key <hex> --json` does. If
   `mode` is `open`, verify with no key: those packages were built sealed and then
   mutated, so the seal is expected to fail and open mode is what lets the case
   reach the check it was written for.
3. Compare the overall verdict, and the first failing check id for reject cases,
   with `expected.json`.

`kind` is `accept` (must not be rejected) or `reject` (must be rejected at the
named check). A verifier that rejects everything passes every reject case and
fails every accept case, which is why both halves are here.

## What this corpus does not prove

These packages were produced by this project. They are anchored to
`docs/CHECK-MATRIX.md` and to the spec text, not to an outside authority, and
passing them shows conformance to this reading of the spec, not to any
regulator's requirement. Anything a verifier does that is not in here is
unmeasured, not impossible.
"""


def _oracle_key(name):
    """The seal key for a case, derived from its name instead of drawn at random.

    A corpus a stranger cannot rebuild is a corpus a stranger has to trust. Two
    things stopped that: keys drawn per run, and a wall-clock `created_at`. The
    key is now the hash of the case name, and the clock is pinned by
    SOURCE_DATE_EPOCH when `--emit` runs, so the same commands produce the same
    bytes anywhere. These keys are published in `keys.json` and seal nothing but
    synthetic packages.
    """
    return hashlib.sha256(b"uibc-oracle-key/" + name.encode("utf-8")).digest()


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
    elif variant == "typed":
        files = [("call.json", '{"tool":"search","q":"a"}', "ACTION"),
                 ("in.txt", "three results\n", "INPUT"),
                 ("out.txt", "pick the first\n", "OUTPUT")]
    elif variant == "lifecycle":
        files = [("log.txt", "one action\n")]
    elif variant == "anchored":
        # Two items, not one: an anchor carries a Merkle proof, and a single-leaf tree
        # has an empty proof, which the anchor resolver treats as unresolvable. Found
        # while building this case, recorded in docs/ORACLE.md rather than worked around.
        files = [("log.txt", "one action\n"), ("extra.txt", "second action\n")]
    elif variant == "resubmit":
        files = [("log.txt", "one action\n")]
    else:
        raise ValueError(variant)

    for fname, content, *_rest in [(f[0], f[1], *(f[2:] if len(f) > 2 else [])) for f in files]:
        etype = _rest[0] if _rest else "ACTION"
        src = os.path.join(tmp, f"{name}-{fname}")
        mode = "wb" if isinstance(content, bytes) else "w"
        # newline="\n" even here: these bytes become evidence, and evidence
        # hashed on Windows must hash the same as evidence hashed on Linux.
        opts = {} if mode == "wb" else {"encoding": "utf-8", "newline": "\n"}
        with open(src, mode, **opts) as f:
            f.write(content)
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": etype, "file": src,
            "media_type": "text/plain", "note": fname})())

    if variant == "lifecycle":
        # Ordinary lifecycle: three events by the recorded principal, using words the
        # verifier knows. This exercises the actor/principal rules and sequence
        # continuity in the accepting direction.
        for etype in ("UPDATE", "DELEGATE", "UPDATE"):
            ucli.cmd_event(type("A", (), {"path": pkg, "type": etype, "actor": None})())

    key = _oracle_key(name)
    kf = os.path.join(tmp, f"{name}.key")
    with open(kf, "w", encoding="ascii", newline="\n") as f:
        f.write(key.hex())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    if variant == "resubmit":
        # a second submission is ordinary: the agent sealed, then sealed again
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    if variant == "anchored":
        # A legitimate package that also carries a resolvable anchor and a resolvable
        # policy artefact - the accepting version of the S14/S15/S18 machinery.
        import outsider_audit as oa
        oa.build_ext(pkg)
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
        with open(src, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"oracle {name} {i}\n")
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "ACTION", "file": src,
            "media_type": "text/plain", "note": f"n{i}"})())
    key = _oracle_key(name)
    kf = os.path.join(tmp, f"{name}.key")
    with open(kf, "w", encoding="ascii", newline="\n") as f:
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
        with open(first, "a", encoding="utf-8", newline="\n") as f:
            f.write("TAMPERED\n")
        return
    if mutation == "delete":
        os.remove(first)
        return
    if mutation == "duplicate":
        idx = json.load(open(idx_path, encoding="utf-8"))
        idx["entries"].append(dict(idx["entries"][0]))
        with open(idx_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
        return
    if mutation == "dup_root":
        # duplicate the first entry; the re-seal that follows rewrites manifest and
        # signature from the index, so only the identifier rule (S12) can fail.
        idx["entries"].append(dict(idx["entries"][0]))
        with open(idx_path, "w", encoding="utf-8", newline="\n") as f:
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
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
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
    # Which checks the reference actually evaluated across all these packages. Not which
    # checks it declares: which ones produced a line of output on at least one package.
    # The difference is the whole point of this count - a check that is declared and never
    # reached is indistinguishable from a check that does not exist.
    seen = set()
    with tempfile.TemporaryDirectory() as tmp:
        for name, mutation, want_verdict, want_first in ORACLE:
            pkg, key = build(tmp, name, mutation)
            r_verdict, r_first = ref_view(pkg, key)
            seen |= {c["id"] for c in verify(pkg, key=key)["checks"]}
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
            seen |= {c["id"] for c in rep["checks"]}
            r_verdict, r_first = ref_view(pkg, None, rep=rep)
            r_ok = (r_verdict == want_verdict and r_first == want_first)
            bad += 0 if r_ok else 1
            # Score the second implementation where it can actually see the rule. S1-S3
            # are V1-V3, so an extension row expecting a failure at S1 is within its sight
            # and must not be waved through as "n/a" - that was a hole in this tool until
            # a test pointed at it.
            #
            # Its first failure is only comparable when it lands on an id CHECK_MAP
            # translates. It also emits V7/V8/V9, rules that pair with parts of S1/S7/S8
            # rather than whole checks; a case where one of those fires first has the right
            # verdict and a first-failure code that means something different, so the code
            # is recorded as un-mapped instead of being called a disagreement.
            if int(want_first[1:]) <= 6:
                i_verdict, i_first = ind_view(pkg, None)
                code_comparable = i_first is None or str(i_first).startswith("S")
                i_ok = (i_verdict == want_verdict and
                        (not code_comparable or i_first == want_first))
                bad += 0 if i_ok else 1
                rows.append((name, want_verdict, str(want_first), r_verdict, str(r_first),
                             i_verdict,
                             str(i_first) if code_comparable else "%s (unmapped)" % i_first,
                             r_ok, i_ok))
            else:
                rows.append((name, want_verdict, str(want_first), r_verdict, str(r_first),
                             "n/a", "n/a", r_ok, None))

        # --- S9: a self-consistent package judged against someone else's head ---
        pkg_a, key_a = build(tmp, "oracle-s09-old", "none", nevid=1)
        pkg_b, _kb = build(tmp, "oracle-s09-new", "none", nevid=2)
        want_head = checkpoint_of(pkg_b)          # the head observed elsewhere
        rep = verify(pkg_a, expect_head=want_head)
        seen |= {c["id"] for c in rep["checks"]}
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
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(man, f, indent=2, sort_keys=True)
        reseal(pkg_c, key_c)
        verify(pkg_c, state_file=state_file)      # first observation: records the mark
        man = json.load(open(man_path, encoding="utf-8"))
        man["freshness_head"]["sequence"] = 3     # ...validly signed, but from earlier
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(man, f, indent=2, sort_keys=True)
        reseal(pkg_c, key_c)
        rep = verify(pkg_c, state_file=state_file)
        seen |= {c["id"] for c in rep["checks"]}
        r_verdict, r_first = ref_view(pkg_c, None, rep=rep)
        r_ok = (r_verdict == "FAIL" and r_first == "S19")
        bad += 0 if r_ok else 1
        rows.append(("oracle-s19-regressed", "FAIL", "S19", r_verdict, str(r_first),
                     "n/a", "n/a", r_ok, None))

        # --- measured correspondence for the rules CHECK_MAP does not translate ---
        corr = measure_rule_correspondence(tmp)
        blind_ref, blind_ind = measure_blind_verdict(tmp)
        n_hostile, false_pass, declined = measure_false_pass(tmp)
        reachable, decided, never = measure_decidability(tmp)
        r_n, i_n, only_ind, only_ref = measure_declared_scope(tmp)

        # --- tranche four: legitimate packages must be accepted, not merely "not attacked" ---
        accept_total = 0
        accept_ref_alarms = 0
        accept_ind_alarms = 0
        for name, variant in ORACLE_ACCEPT:
            pkg, key = build_good(tmp, name, variant)
            rep = verify(pkg, key=key)
            seen |= {c["id"] for c in rep["checks"]}
            r_verdict, r_first = ref_view(pkg, None, rep=rep)
            i_verdict, i_first = ind_view(pkg, key)
            r_ok = (r_verdict == "PASS")
            # On the accept side the second implementation is allowed to decline to judge
            # (INCONCLUSIVE) but not to reject: a rejection here is a false alarm. After
            # the scope guard it says INCONCLUSIVE on packages carrying artefacts it has
            # no rule for, which is the honest answer rather than a green one.
            i_ok = (i_verdict != "FAIL")
            accept_total += 1
            accept_ref_alarms += 0 if r_ok else 1
            accept_ind_alarms += 0 if i_ok else 1
            bad += 0 if r_ok else 1
            bad += 0 if i_ok else 1
            rows.append((name, "PASS", "—", r_verdict, str(r_first),
                         i_verdict, str(i_first), r_ok, i_ok))

    # Computed, not written: how many checks actually produced output across these
    # packages, and how many of those the second implementation can also speak to.
    observed = sorted(seen, key=lambda i: int(i[1:]) if i[1:].isdigit() else 0)
    mapped = sorted(V_TO_S, key=lambda v: int(v[1:]) if v[1:].isdigit() else 0)
    ind_rules = sorted(IND_RULES, key=lambda v: int(v[1:]) if v[1:].isdigit() else 0)

    verdict = ("PASS" if bad == 0 else "FAIL")

    if "--json" in sys.argv or "--json-out" in sys.argv:
        report = {
            "schema": "uibc-differential/1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cases": len(rows),
            "cells_disagreeing_with_the_oracle": bad,
            "checks_evaluated": observed,
            "checks_total": len(observed),
            "exact_pairs": [{"second_implementation_rule": k, "check": V_TO_S[k]} for k in mapped],
            "exact_pairs_count": len(mapped),
            "second_implementation_rules": ind_rules,
            "unmapped_second_implementation_rules": [r for r in ind_rules if r not in V_TO_S],
            "rule_correspondence": [
                {"rule": rule, "reference_verdict": ref_v,
                 "reference_first_failures": ref_f, "independent_verdict": ind_v,
                 "independent_first_failures": ind_f}
                for rule, ref_f, ref_v, ind_f, ind_v in corr],
            "blind_verdict": {"reference": blind_ref, "independent": blind_ind,
                              "note": "the reference has a rule the second does not; "
                                      "the second must not answer PASS here"},
            "hostile": {"total": n_hostile, "false_pass": len(false_pass),
                        "declined_to_judge": len(declined)},
            "accept": {"cases": accept_total,
                       "reference_false_alarms": accept_ref_alarms,
                       "independent_false_alarms": accept_ind_alarms},
            "per_case": [
                {"case": name, "oracle_verdict": ov, "oracle_first": of,
                 "reference_verdict": rv, "reference_first": rf,
                 "independent_verdict": iv, "independent_first": iff,
                 "reference_matches_oracle": rok,
                 "independent_matches_oracle": (None if iok is None else iok)}
                for name, ov, of, rv, rf, iv, iff, rok, iok in rows],
            "verdict": verdict,
        }
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        # The build steps inside this tool print progress to stdout, so a report
        # piped to a JSON consumer would arrive polluted. `--json-out` writes the
        # report to a file and leaves stdout for nothing but progress text.
        if "--json-out" in sys.argv:
            i = sys.argv.index("--json-out")
            dest = sys.argv[i + 1] if len(sys.argv) > i + 1 else "differential-report.json"
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload + "\n")
            sys.stderr.write("wrote %s\n" % dest)
        else:
            print(payload)
        return 0 if bad == 0 else 1

    print(f"{'case':<26}{'oracle':<8}{'o-first':<9}{'ref':<8}{'r-first':<9}"
          f"{'ind':<8}{'i-first':<9}{'ref?':<6}{'ind?'}")
    for name, ov, of, rv, rf, iv, iff, rok, iok in rows:
        mark = "OK" if rok else "DIFF"
        imark = "n/a" if iok is None else ("OK" if iok else "DIFF")
        print(f"{name:<26}{ov:<8}{of:<9}{rv:<8}{rf:<9}{iv:<8}{iff:<9}{mark:<6}{imark}")

    print(f"\ncases: {len(rows)}, cells disagreeing with the oracle: {bad}")
    print("checks evaluated by the reference across these cases: %d (%s)"
          % (len(observed), ", ".join(observed)))
    print("rules the independent implementation emits: %d (%s)"
          % (len(ind_rules), ", ".join(ind_rules)))
    print("exact id-mapped pairs (CHECK_MAP): %d of %d (%s)"
          % (len(mapped), len(observed),
             ", ".join("%s->%s" % (V_TO_S[k], k) for k in mapped)))
    print("unmapped independent rules: %s - these pair with parts of S1/S7/S8, "
          "not with whole checks, so they are not counted as coverage"
          % (", ".join(r for r in ind_rules if r not in V_TO_S) or "none"))
    for rule, ref_failed, ref_verdict, ind_failed, ind_verdict in corr:
        print("measured: %s fires alone -> reference %s %s; independent %s %s"
              % (rule, ref_verdict, ",".join(ref_failed) or "-",
                 ind_verdict, ",".join(ind_failed) or "-"))
    print("measured: where the reference has a rule and the second does not "
          "(closure dropped, S10), reference says %s and the second says %s"
          % (blind_ref, blind_ind))
    print("measured: of %d hostile packages the reference rejects, the second "
          "implementation says PASS on %d and declines to judge %d"
          % (n_hostile, len(false_pass), len(declined)))
    print("measured: of %d checks the hostile corpus exercises, the second implementation "
          "reaches %d by rule (%s) and can never reach %d (%s)"
          % (len(reachable), len(decided), ",".join(decided),
             len(never), ",".join(never) or "-"))
    print("measured: things each implementation declares it did NOT check - reference %d, "
          "second %d; %d of the second's are absent from the reference's list (%s), and "
          "the reference names %d the second does not (%s)"
          % (r_n, i_n, len(only_ind), ",".join(only_ind) or "-",
             len(only_ref), ",".join(only_ref) or "-"))
    print("ORACLE: " + ("PASS - both implementations match the written expectations"
                        if bad == 0 else "FAIL - an implementation disagrees with the oracle"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    if "--emit" in sys.argv:
        target = sys.argv[sys.argv.index("--emit") + 1]
        n, bad_rt = emit_corpus(target)
        print("emitted %d cases to %s; round-trip mismatches: %d"
              % (n, target, len(bad_rt)))
        for row in bad_rt:
            print("  DRIFT: %s wrote %s/%s but expects %s/%s"
                  % (row[0], row[1], row[2], row[3], row[4]))
        sys.exit(0 if not bad_rt else 1)
    sys.exit(main())
