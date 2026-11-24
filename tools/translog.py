"""translog: operate a small append-only log of your own, from the command line.

    python3 tools/translog.py new  --out log.json
    python3 tools/translog.py append log.json record.json [--out log.json]
    python3 tools/translog.py checkpoint log.json [--seed k.edkey] [--note text] [--out cp.json]
    python3 tools/translog.py cosign cp.json --seed witness.edkey [--out cosig.json]
    python3 tools/translog.py prove log.json <index> [--out proof.json]
    python3 tools/translog.py verify-inclusion log.json <index> proof.json
    python3 tools/translog.py verify-checkpoint cp.json --pub <hex>
    python3 tools/translog.py verify-journal log.json journal.jsonl

Every subcommand prints JSON and exits 0 on success, 1 on a failed verification,
2 on a usage error. Nothing here talks to the network: publishing a head is a
git commit, publishing an entry is a line in a file.
"""
import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uibc_core import ed25519, translog as T   # noqa: E402


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save(obj, path):
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text, end="")


def _seed(path):
    with open(path, encoding="ascii") as fh:
        raw = fh.read().strip()
    if raw.startswith("ed25519:"):
        raw = raw.split(":", 1)[1]
    return bytes.fromhex(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="translog")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create an empty log")
    p.add_argument("--out")

    p = sub.add_parser("append", help="append a record (any JSON object)")
    p.add_argument("log")
    p.add_argument("record")
    p.add_argument("--out")

    p = sub.add_parser("checkpoint", help="commit the current head (optionally signed)")
    p.add_argument("log")
    p.add_argument("--seed")
    p.add_argument("--note", default="")
    p.add_argument("--out")

    p = sub.add_parser("cosign", help="a witness signs a checkpoint")
    p.add_argument("cp")
    p.add_argument("--seed", required=True)
    p.add_argument("--out")

    p = sub.add_parser("prove", help="inclusion proof for one leaf")
    p.add_argument("log")
    p.add_argument("index", type=int)
    p.add_argument("--out")

    p = sub.add_parser("verify-inclusion", help="check an inclusion proof")
    p.add_argument("log")
    p.add_argument("index", type=int)
    p.add_argument("proof")

    p = sub.add_parser("verify-checkpoint", help="check the operator signature")
    p.add_argument("cp")
    p.add_argument("--pub", required=True, help="public key as hex")

    p = sub.add_parser("verify-journal", help="does the published journal rebuild this log?")
    p.add_argument("log")
    p.add_argument("journal")

    a = ap.parse_args(argv)

    if a.cmd == "new":
        _save(T.new_log(), a.out)
        return 0

    if a.cmd == "append":
        log = _load(a.log)
        log, idx = T.append(log, _load(a.record))
        out = {"index": idx, "digest": log["entries"][idx], "tree_size": T.tree_size(log),
               "root": T.root_hex(log)}
        if a.out:
            _save(log, a.out)
        _save(out, None)
        return 0

    if a.cmd == "checkpoint":
        cp = T.checkpoint(_load(a.log), _seed(a.seed) if a.seed else None, a.note)
        _save(cp, a.out)
        return 0

    if a.cmd == "cosign":
        cos = T.cosign(_load(a.cp), _seed(a.seed))
        _save(cos, a.out)
        return 0

    if a.cmd == "prove":
        log = _load(a.log)
        _save({"tree_size": T.tree_size(log), "root": T.root_hex(log), "index": a.index,
               "leaf": log["entries"][a.index],
               "proof": [h.hex() for h in T.inclusion_proof(log, a.index)]}, a.out)
        return 0

    if a.cmd == "verify-inclusion":
        log = _load(a.log)
        proof = [bytes.fromhex(h) for h in _load(a.proof)["proof"]]
        ok = T.verify_inclusion(log, a.index, proof)
        _save({"verified": ok, "index": a.index, "tree_size": T.tree_size(log)}, None)
        return 0 if ok else 1

    if a.cmd == "verify-checkpoint":
        cp = _load(a.cp)
        ok = T.verify_checkpoint(cp, bytes.fromhex(a.pub))
        _save({"verified": ok, "tree_size": cp.get("tree_size"), "root": cp.get("root")}, None)
        return 0 if ok else 1

    if a.cmd == "verify-journal":
        log = _load(a.log)
        with open(a.journal, encoding="utf-8") as fh:
            rebuilt = T.from_jsonl(fh.read())
        same = rebuilt["entries"] == log["entries"]
        _save({"rebuilt_matches_log": same, "size": T.tree_size(rebuilt),
               "root": T.root_hex(rebuilt)}, None)
        return 0 if same else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
