#!/usr/bin/env python3
"""Build parity-battery cases + CLI ground truth for the verify.html port."""
import base64, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
os.chdir(HERE)

from uibc_core import verify as V
from uibc_core import signing as S
from uibc_core import merkle as MK
from uibc_core.canonical import hash_obj

CASES = os.path.join(os.getcwd(), "cases")
shutil.rmtree(CASES, ignore_errors=True)
os.makedirs(CASES)

# Build a PRISTINE package by replaying the demo's steps 1-4 (the demo
# command itself leaves its package tampered on disk at step 6).
from uibc_core import cli as CLI
from uibc_core.canonical import hash_file

def _args(**kw):
    return type("A", (), kw)()

BUILD = os.path.join(os.getcwd(), "build")
shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD)
DEMO = os.path.join(BUILD, "demo")
KEYF = os.path.join(BUILD, "owner.key")
CLI.cmd_init(_args(path=DEMO))
CLI.cmd_register(_args(path=DEMO, agent_id="demo-agent", owner="alice",
                       agent_type="software-agent", version="0.1.0"))
_ev = os.path.join(BUILD, "report.txt")
open(_ev, "w", encoding="utf-8", newline="\n").write("demo evidence: agent action log\n")
CLI.cmd_evidence(_args(path=DEMO, type="ACTION", file=_ev,
                       media_type="text/plain", note=""))
CLI.cmd_keygen(_args(out=KEYF, ed25519=True))
CLI.cmd_submit(_args(path=DEMO, key=KEYF))
# Forged: copy pristine, alter evidence, recompute hashes, reseal w/ attacker key.
FORGED = os.path.join(BUILD, "forged")
shutil.copytree(DEMO, FORGED)
_fp = os.path.join(FORGED, "evidence", "files", "report.txt")
open(_fp, "a", encoding="utf-8", newline="\n").write("forged line added by attacker\n")
_idx = json.load(open(os.path.join(FORGED, "evidence", "index.json")))
for _e in _idx["entries"]:
    _e["content_hash"] = hash_file(os.path.join(FORGED, "evidence", _e["path"]))
json.dump(_idx, open(os.path.join(FORGED, "evidence", "index.json"), "w"), indent=2)
_man = json.load(open(os.path.join(FORGED, "manifest.json")))
from uibc_core.canonical import evidence_root as _er
_man["evidence_root"] = _er([_e["content_hash"] for _e in _idx["entries"]])
json.dump(_man, open(os.path.join(FORGED, "manifest.json"), "w"), indent=2)
_ATK = os.path.join(BUILD, "attacker.key")
CLI.cmd_keygen(_args(out=_ATK, ed25519=True))
CLI.cmd_submit(_args(path=FORGED, key=_ATK))
# Two-evidence variant (S15 anchors need a non-empty inclusion proof).
DEMO2 = os.path.join(BUILD, "demo2")
CLI.cmd_init(_args(path=DEMO2))
CLI.cmd_register(_args(path=DEMO2, agent_id="demo-agent", owner="alice",
                       agent_type="software-agent", version="0.1.0"))
_ev2 = os.path.join(BUILD, "report2.txt")
open(_ev2, "w", encoding="utf-8", newline="\n").write("demo evidence: second file\n")
CLI.cmd_evidence(_args(path=DEMO2, type="ACTION", file=_ev,
                       media_type="text/plain", note=""))
CLI.cmd_evidence(_args(path=DEMO2, type="ACTION", file=_ev2,
                       media_type="text/plain", note=""))
CLI.cmd_submit(_args(path=DEMO2, key=KEYF))

def cp(src, name):
    dst = os.path.join(CASES, name)
    shutil.copytree(src, dst)
    return dst

def load(d, rel):
    return json.load(open(os.path.join(d, rel)))

def save(d, rel, obj):
    with open(os.path.join(d, rel), "w") as f:
        json.dump(obj, f, indent=2)

truth = {}

def run(name, d, key=None, pubkey=None, expect_head=None):
    rep = V.verify(d, key=key, pubkey=pubkey, expect_head=expect_head)
    truth[name] = {
        "result": rep["result"],
        "checks": {c["id"]: c["result"] for c in rep["checks"]},
        "opts": {
            "keyHex": key.hex() if key else None,
            "pubkeyHex": pubkey.hex() if pubkey else None,
            "expectHead": expect_head,
        },
    }

# 01 demo pristine
d = cp(DEMO, "case01"); run("case01", d)
# 02 forged, unpinned
d = cp(FORGED, "case02"); run("case02", d)
# 02b forged, pinned with the DEMO (real owner) public key -> S6 must FAIL
demo_seal = load(DEMO, "signatures/seal.json")
real_pub = base64.b64decode(demo_seal["public_key"])
d = cp(FORGED, "case02b"); run("case02b", d, pubkey=real_pub)
# 03 truncated lifecycle
d = cp(DEMO, "case03")
lc = load(d, "lifecycle.json"); lc["events"] = lc["events"][:-1]; save(d, "lifecycle.json", lc)
run("case03", d)
# 04 actor rewrite
d = cp(DEMO, "case04")
lc = load(d, "lifecycle.json"); lc["events"][-1]["actor"] = "mallory"; save(d, "lifecycle.json", lc)
run("case04", d)
# 05 index note tamper
d = cp(DEMO, "case05")
idx = load(d, "evidence/index.json"); idx["entries"][0]["note"] = "reviewed and approved"; save(d, "evidence/index.json", idx)
run("case05", d)
# 06 evidence byte flip
d = cp(DEMO, "case06")
p = os.path.join(d, "evidence/files/report.txt")
b = bytearray(open(p, "rb").read()); b[0] ^= 0xFF; open(p, "wb").write(bytes(b))
run("case06", d)
# 07 duplicate key in manifest (raw)
d = cp(DEMO, "case07")
mp = os.path.join(d, "manifest.json")
raw = open(mp).read()
open(mp, "w").write(raw.replace("{", '{ "schema": "uibc-core/0.3.3-proposal", "schema": "dup",', 1))
run("case07", d)
# 08 malformed lifecycle JSON
d = cp(DEMO, "case08")
open(os.path.join(d, "lifecycle.json"), "w").write("{ not json ]")
run("case08", d)
# 09 legacy v0.3 sample (frozen copy of the pre-v1.1 page sample)
d = cp(os.path.join(HERE, "legacy_sample"), "case09")
run("case09", d)
# 10 unsigned (seal removed)
d = cp(DEMO, "case10"); os.remove(os.path.join(d, "signatures/seal.json"))
run("case10", d)
# 11 stray root file
d = cp(DEMO, "case11"); open(os.path.join(d, "notes.md"), "w").write("trust me\n")
run("case11", d)
# 12 nested extra file (note only)
d = cp(DEMO, "case12"); open(os.path.join(d, "evidence/extra.txt"), "w").write("aux\n")
run("case12", d)
# 13 HMAC package (current + legacy coverage), built with the library
from uibc_core.lifecycle import validate_lifecycle  # noqa
base = cp(DEMO, "case13")
ident = load(base, "identity.json"); man = load(base, "manifest.json"); lc = load(base, "lifecycle.json")
key = bytes(range(32))
sig, = [S.seal_sign(key, ident, man, lc)]
seal = {"schema": "uibc-core/0.3.3-proposal", "algorithm": "HMAC-SHA256",
        "key_id": S.key_id(key), "signed": "identity+manifest+lifecycle",
        "signature": sig, "created_at": man["created_at"]}
save(base, "signatures/seal.json", seal)
run("case13", base, key=key)
run("case13-nokey", base)
run("case13-wrongkey", base, key=b"\xff" * 32)
# 13b HMAC legacy coverage (no lifecycle in payload)
base = cp(DEMO, "case13b")
sig = S.seal_sign(key, ident, man)
seal = {"schema": "uibc-core/0.3.0-proposal", "algorithm": "HMAC-SHA256",
        "key_id": S.key_id(key), "signed": "identity+manifest",
        "signature": sig, "created_at": man["created_at"]}
save(base, "signatures/seal.json", seal)
run("case13b", base, key=key)
# 14 S9 pinned head: correct and wrong
d = cp(DEMO, "case14")
run("case14", d, expect_head=man["checkpoint_head"])
run("case14-wrong", d, expect_head="sha256:" + "0" * 64)
# 15 NaN in manifest (raw JSON)
d = cp(DEMO, "case15")
mp = os.path.join(d, "manifest.json")
raw = open(mp).read()
open(mp, "w").write(raw.replace('"status": "SUBMITTED"', '"status": "SUBMITTED", "score": NaN'))
run("case15", d)
# 16 future created_at in identity (S12)
d = cp(DEMO, "case16")
ident = load(d, "identity.json"); ident["created_at"] = "2027-01-01T00:00:00Z"; save(d, "identity.json", ident)
run("case16", d)
# 17 merkle package (S13): add evidence/merkle.json over the demo evidence
d = cp(DEMO, "case17")
idx = load(d, "evidence/index.json")
order = sorted(idx["entries"], key=lambda e: e["path"])
leaves = [MK.leaf_hash(open(os.path.join(d, "evidence", e["path"]), "rb").read()) for e in order]
root = MK.root_hash(leaves)
proofs = [{"index": i, "path": e["path"], "proof": MK.build_proof(leaves, i)} for i, e in enumerate(order)]
save(d, "evidence/merkle.json", {"algorithm": "rfc6962-sha256", "size": len(leaves),
                                 "root": root.hex(), "proofs": proofs})
run("case17", d)
# 17b corrupted proof
d = cp(os.path.join(CASES, "case17"), "case17b")
mk = load(d, "evidence/merkle.json"); mk["root"] = "00" * 32; save(d, "evidence/merkle.json", mk)
run("case17b", d)
# 18 chain package (S17)
d = cp(DEMO, "case18")
env1 = {"receipt": 1, "what": "first"}
env2 = {"receipt": 2, "what": "second", "policy_digest": "sha256:" + "ab" * 32}
chain = {"schema": "test", "receipts": [
    {"envelope": env1, "previous_receipt_hash": "0" * 64},
    {"envelope": env2, "previous_receipt_hash": hash_obj(env1)},
]}
save(d, "evidence/chain.json", chain)
run("case18", d)
# 18b broken link
d = cp(os.path.join(CASES, "case18"), "case18b")
ch = load(d, "evidence/chain.json"); ch["receipts"][1]["previous_receipt_hash"] = "f" * 64; save(d, "evidence/chain.json", ch)
run("case18b", d)
# 19 policies (S18) resolving the chain's policy_digest
d = cp(os.path.join(CASES, "case18"), "case19")
artefact = {"policy": "demo", "rules": ["r1"]}
save(d, "evidence/policy-a.json", artefact)
save(d, "evidence/policies.json", {"policies": [
    {"digest": "sha256:" + "ab" * 32, "path": "evidence/policy-a.json"}]})
# fix the digest to the artefact's real hash AND update the chain envelope digest
real = hash_obj(artefact)
env2b = dict(env2); env2b["policy_digest"] = "sha256:" + real
ch = load(d, "evidence/chain.json"); ch["receipts"][1]["envelope"] = env2b; save(d, "evidence/chain.json", ch)
save(d, "evidence/policies.json", {"policies": [
    {"digest": "sha256:" + real, "path": "evidence/policy-a.json"}]})
run("case19", d)
# 20 anchors (S15): anchor the second evidence leaf of the 2-file package
d = cp(DEMO2, "case20")
idx = load(d, "evidence/index.json")
order = sorted(idx["entries"], key=lambda e: e["path"])
leaves = [MK.leaf_hash(open(os.path.join(d, "evidence", e["path"]), "rb").read()) for e in order]
root = MK.root_hash(leaves)
anchor = {"id": "anchor-001", "version": 1, "leaf_hash": leaves[1].hex(),
          "anchored_at": "2026-11-17T08:00:00Z", "root": root.hex(),
          "size": len(leaves), "index": 1, "proof": MK.build_proof(leaves, 1)}
save(d, "evidence/anchors.json", {"resolver": "evidence-merkle", "anchors": [anchor]})
run("case20", d)

json.dump(truth, open(os.path.join(os.getcwd(), "truth.json"), "w"), indent=1)
print("cases:", len(truth))
for k, v in truth.items():
    print(k, "->", v["result"], {i: r for i, r in v["checks"].items() if r != "PASS"})
