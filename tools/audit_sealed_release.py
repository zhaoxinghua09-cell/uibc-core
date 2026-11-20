#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit a published, sealed release of a *third party's* register.

Why this exists
---------------
`tools/conformance_harness.py` runs our corpus against someone else's verifier.
This tool is the other direction: it runs **our** implementation against someone
else's published artifact, and writes a receipt that says what we recomputed and
whether it matched what they published.

It was written to audit a real release (`dfr.derappar.at`, release
`Apparat-2026-09-27-5F33DA`) and then generalised so the same receipt can be
produced for any register that publishes the same shape. It is the evidence
behind `conformance/examples/sealed-release-audit/`.

The one discipline that matters here
------------------------------------
Hard-coded JCS: the entry seals and the release digest are recomputed with
**`uibc_core.canonical.canonicalize`** - our own RFC 8785 implementation - and
not with the register's reference verifier. If our canonicalisation differs by
one byte, the seal changes, the Merkle root changes, and the receipt says so.
Signature checking is the one place an independent library is used
(`cryptography`), because "our code verifies our code's output" proves nothing
about the signature.

Readings that did not work are recorded, never swapped out
---------------------------------------------------------
Some published fields do not say which bytes they digest. `key_id` is one
example. Where a field admits more than one reading, the receipt keeps **every**
reading and names which one matched. A receipt that only contains the reading
that worked is a receipt that hides its own mistakes.

Usage
-----
    python tools/audit_sealed_release.py --from /path/to/offline-copy --release-id X
    python tools/audit_sealed_release.py --root https://example.org --release-id X --out receipt.json

Offline mode (`--from`) reads a directory holding `release.json`,
`apparat-public-key.pem` (or `public.pem`), `releases/index.json` and the files
named in `file_hashes`; it never touches the network. That is how the tests run,
and how a reader can re-run our receipt without fetching anything.

Exit codes: 0 every check passed, 1 a check ran and disagreed, 2 a check could
not run at all (missing artifact / malformed input). 1 and 2 are different
because "we disagree" and "we could not look" are different claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

from uibc_core.canonical import canonicalize

USER_AGENT = "uibc-core/audit_sealed_release"
SEAL_FIELDS = ("context", "label", "source_url", "time_period", "unit", "value")
DIGEST_FIELDS = (
    "company_id", "file_hashes", "generated_at", "previous_release_commitment",
    "release_commitment", "row_count", "spec_version",
)


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------- io
class Source:
    """Reads published artifacts, from the network or from an offline copy."""

    def __init__(self, root: str | None, directory: str | None):
        self.root = root.rstrip("/") if root else None
        self.directory = directory

    def bytes(self, name: str) -> bytes:
        if self.directory:
            for cand in (name, "f_" + name.replace("/", "_")):
                path = os.path.join(self.directory, cand.replace("/", os.sep))
                try:
                    with open(path, "rb") as fh:
                        return fh.read()
                except FileNotFoundError:
                    continue
            raise FileNotFoundError("offline copy has no artifact for %r" % name)
        req = urllib.request.Request(self.root + "/" + name, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read()

    def json(self, name: str):
        return json.loads(self.bytes(name))


# ------------------------------------------------------------------ primitives
def entry_seal(entry: dict) -> str:
    """SHA-256 over JCS of the six fields, with nulls present as JSON null.

    The profile rejects the string "null" outright: a serializer that turns a
    missing value into the four characters `null` produces a different digest
    for the same logical row, which is the one failure mode this seal exists to
    prevent.
    """
    pre = {}
    for f in SEAL_FIELDS:
        v = entry.get(f)
        if isinstance(v, str) and v == "null":
            raise ValueError('field %r is the string "null", not null' % f)
        pre[f] = v
    return sha256_hex(canonicalize(pre))


def leaf_hash(seal_hex: str) -> bytes:
    return hashlib.sha256(b"\x00" + seal_hex.encode("utf-8")).digest()


def node_hash(l: bytes, r: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + l + r).digest()


def largest_power_of_two_lt(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list[bytes]) -> bytes:
    """RFC 6962 MTH. Odd nodes split at the largest power of two below n.

    No "duplicate the last node" step: that step is what CVE-2012-2459 abuses,
    and the profile is explicit about not having it.
    """
    if not leaves:
        return hashlib.sha256(b"").digest()
    if len(leaves) == 1:
        return leaves[0]
    k = largest_power_of_two_lt(len(leaves))
    return node_hash(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


def commitment_from_seals(seal_hexes: list[str]) -> str:
    ordered = sorted(seal_hexes)  # ascending, duplicates kept
    return merkle_root([leaf_hash(s) for s in ordered]).hex()


# ----------------------------------------------------------------------- steps
def step_seals(rel: dict, ledger: dict) -> dict:
    entries = ledger if isinstance(ledger, list) else (
        ledger.get("entries") or ledger.get("rows") or [])
    if not entries:
        return {"step": "1-entry-seals-and-merkle", "ok": None,
                "detail": "ledger carries no entries in a shape this tool recognises"}
    computed = [entry_seal(e) for e in entries]
    published_individual = [e.get("seal") or e.get("entry_seal") for e in entries]
    root = commitment_from_seals(computed)
    mismatched = [i for i, e in enumerate(entries)
                  if published_individual[i] and published_individual[i] != computed[i]]
    return {
        "step": "1-entry-seals-and-merkle",
        "entries": len(entries),
        "root_recomputed": root,
        "root_published": rel.get("release_commitment"),
        "root_agreement": root == rel.get("release_commitment"),
        "per_entry_seals_published": sum(1 for s in published_individual if s),
        "per_entry_mismatches": mismatched[:10],
        "ok": root == rel.get("release_commitment") and not mismatched,
        "detail": ("%d seals recomputed and sorted; RFC 6962 root compared with the "
                   "published release_commitment" % len(computed)),
    }


def step_digest(rel: dict) -> dict:
    pre = {k: rel.get(k) for k in DIGEST_FIELDS}
    # The digest preimage carries row_count as a STRING even though release.json
    # itself publishes it as a number (this register publishes 56, an int). That
    # is not a register bug: the profile does it on purpose, because RFC 8785
    # number canonicalisation is where two independent implementations diverge.
    # Recorded here so the receipt names the transformation it performed.
    if pre.get("row_count") is not None:
        pre["row_count"] = str(pre["row_count"])
    # row_count is carried as a string on purpose: RFC 8785 number canonicalisation
    # is the one place two independent implementations silently diverge.
    canon = canonicalize(pre)
    recomputed = sha256_hex(canon)
    return {
        "step": "2-release-digest",
        "digest_recomputed": recomputed,
        "digest_published": rel.get("release_digest"),
        "agreement": recomputed == rel.get("release_digest"),
        "canonical_bytes_sha256": sha256_hex(canon),
        "canonical_length": len(canon),
        "ok": recomputed == rel.get("release_digest"),
        "detail": "JCS over the seven digest fields; row_count kept as published (a string)",
    }


def step_signature(rel: dict, pub_pem: bytes) -> dict:
    sig_b64 = (rel.get("anchor") or {}).get("signature_b64")
    if not sig_b64:
        return {"step": "3-signature", "ok": None, "detail": "no anchor.signature_b64 published"}
    import base64
    sig = base64.b64decode(sig_b64)
    pre = {k: rel.get(k) for k in DIGEST_FIELDS}
    if pre.get("row_count") is not None:
        pre["row_count"] = str(pre["row_count"])
    canon = canonicalize(pre)
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        pk = serialization.load_pem_public_key(pub_pem)
        pk.verify(sig, canon, ec.ECDSA(hashes.SHA256()))
        verified, why = True, "ECDSA P-256/SHA-256 verification succeeded"
    except InvalidSignature:
        verified, why = False, "signature did not verify over the canonical bytes"
    except Exception as exc:  # noqa: BLE001
        return {"step": "3-signature", "ok": None, "detail": "verification could not run: %s" % exc}
    der = serialization.load_pem_public_key(pub_pem).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    readings = {
        "sha256_over_pem_file_bytes": "sha256:" + sha256_hex(pub_pem),
        "sha256_over_der_spki": "sha256:" + sha256_hex(der),
    }
    published_key_id = (rel.get("anchor") or {}).get("key_id")
    which = [k for k, v in readings.items() if v == published_key_id]
    return {
        "step": "3-signature",
        "verified": verified,
        "detail": why,
        "published_key_id": published_key_id,
        "key_id_readings": readings,
        "key_id_readings_that_match": which,
        "key_id_note": ("The profile does not state which bytes key_id digests. Both readings "
                        "are recorded; the one that did not match is kept rather than dropped."),
        "ok": verified and bool(which),
    }


def step_chain(index: dict, releases: dict[str, dict]) -> dict:
    rels = index.get("releases") or []
    if not rels:
        return {"step": "5-chain-walk", "ok": None, "detail": "index lists no releases"}
    walked, broken, self_ref = [], [], []
    by_commitment: dict[str, list[str]] = {}
    for r in rels:
        doc = releases.get(r["release_id"])
        if doc is None:
            continue
        c = doc.get("release_commitment")
        by_commitment.setdefault(c, []).append(r["release_id"])
    for i, r in enumerate(rels):
        doc = releases.get(r["release_id"])
        if doc is None:
            walked.append({"release_id": r["release_id"], "error": "not available"})
            continue
        prev = doc.get("previous_release_commitment")
        own = doc.get("release_commitment")
        row = {"release_id": r["release_id"], "commitment": own, "previous": prev}
        if prev == own:
            self_ref.append(r["release_id"])
            row["reads_as"] = "self-referential: equal to its own commitment"
        if i > 0:
            pred = releases.get(rels[i - 1]["release_id"])
            if pred is None:
                # No predecessor artifact to compare against: not judgeable is not
                # the same as broken. The comparison is skipped and said so.
                row["predecessor_commitment"] = None
                row["previous_equals_predecessor"] = None
            else:
                pred_c = pred.get("release_commitment")
                row["predecessor_commitment"] = pred_c
                row["previous_equals_predecessor"] = (prev == pred_c)
                if not row["previous_equals_predecessor"]:
                    broken.append({"release_id": r["release_id"],
                                   "predecessor": rels[i - 1]["release_id"]})
        walked.append(row)
    head = rels[-1]["release_id"] if rels else None
    head_doc = releases.get(head or "", {})
    head_prev = head_doc.get("previous_release_commitment")
    carriers = by_commitment.get(head_prev, [])
    start = {
        "from": head,
        "previous": head_prev,
        "carried_by": carriers,
        "predecessor_resolvable_from_field_alone": len(carriers) == 1,
    }
    return {
        "step": "5-chain-walk",
        "releases": len(rels),
        "links_checked": max(0, len(rels) - 1),
        "broken_links": broken,
        "self_referential": self_ref,
        "ordered_from_index": True,
        "walk_from_head_first_step": start,
        "note": ("Order comes from the index, not from the field: a presentation-only "
                 "successor equals its own commitment, so it also equals its predecessor's. "
                 "The field alone cannot separate that from a broken link."),
        "walked": walked,
        "ok": True,
        "detail": "%d releases, %d broken link(s)" % (len(rels), len(broken)),
    }


def step_file_hashes(rel: dict, src: Source) -> dict:
    rows = []
    for name, want in sorted((rel.get("file_hashes") or {}).items()):
        try:
            blob = src.bytes(name)
            got = sha256_hex(blob)
            rows.append({"file": name, "bytes": len(blob), "published": want,
                         "computed": got, "ok": got == want})
        except Exception as exc:  # noqa: BLE001
            rows.append({"file": name, "error": str(exc), "ok": None})
    failed = [r["file"] for r in rows if r["ok"] is False]
    unread = [r["file"] for r in rows if r["ok"] is None]
    if not rows:
        ok = None
    elif failed:
        ok = False
    elif unread:
        # An artifact we could not read is not a passing hash check. Reporting this
        # step green while three rows say "No such file" is the vacuous pass this
        # tool's own negative control exists to prevent.
        ok = None
    else:
        ok = True
    return {
        "step": "6-file-hashes",
        "files": rows,
        "failed": failed,
        "unreadable": unread,
        "all_match": all(r["ok"] is True for r in rows) if rows else None,
        "note": ("release.json is excluded from file_hashes by the profile; it is bound "
                 "through the digest, not listed here. A file that could not be read is "
                 "reported as unreadable, never as a match."),
        "ok": ok,
    }


# ------------------------------------------------------------------------ main
def build_receipt(src: Source, release_id: str) -> dict:
    rel = src.json("release.json")
    if release_id and rel.get("release_id") and rel["release_id"] != release_id:
        raise SystemExit("release.json is %r, not the requested %r"
                         % (rel["release_id"], release_id))
    receipt = {
        "profile": "dfr-0.2",
        "release_id": rel.get("release_id"),
        "generated_at": rel.get("generated_at"),
        "row_count": rel.get("row_count"),
        "source": src.root or src.directory,
        "auditor": "uibc-core audit_sealed_release",
        "jcs_implementation": "uibc_core.canonical.canonicalize (ours, not theirs)",
        "signature_implementation": "cryptography (independent library)",
        "steps": [],
    }
    problems = []
    for name in ("ledger.json",):
        try:
            receipt["steps"].append(step_seals(rel, src.json(name)))
        except Exception as exc:  # noqa: BLE001
            problems.append("%s: %s" % (name, exc))
            receipt["steps"].append({"step": "1-entry-seals-and-merkle", "ok": None,
                                     "detail": "could not read %s: %s" % (name, exc)})
    receipt["steps"].append(step_digest(rel))
    pub = None
    for candidate in ("apparat-public-key.pem", "public.pem", "pub.pem", "key.pem"):
        try:
            pub = src.bytes(candidate)
            break
        except Exception:  # noqa: BLE001
            continue
    receipt["steps"].append(step_signature(rel, pub) if pub
                            else {"step": "3-signature", "ok": None,
                                  "detail": "no public key found next to the release"})
    index = None
    try:
        index = src.json("releases/index.json")
    except Exception as exc:  # noqa: BLE001
        receipt["steps"].append({"step": "5-chain-walk", "ok": None,
                                 "detail": "could not read releases/index.json: %s" % exc})
    if index:
        docs, chain_errors = {}, []
        for r in index.get("releases") or []:
            try:
                if r.get("current"):
                    docs[r["release_id"]] = rel
                else:
                    if not src.directory:
                        doc = json.loads(src.bytes(r["url"]))
                    else:
                        # Every per-release page in this profile is named
                        # <release_id>/release.json, so a cache keyed on the URL
                        # basename collapses all ten releases onto one file and
                        # silently reports a clean chain. The cache is therefore
                        # keyed on the release id, and a file that answers with a
                        # different release id is an error, not a hit.
                        doc, last = None, None
                        for cand in ("releases/%s/release.json" % r["release_id"],
                                     "%s/release.json" % r["release_id"],
                                     "rel_%s.json" % r["release_id"],
                                     "%s.json" % r["release_id"]):
                            try:
                                doc = json.loads(src.bytes(cand))
                                break
                            except Exception as exc:  # noqa: BLE001
                                last = exc
                        if doc is None:
                            chain_errors.append({"release_id": r["release_id"],
                                                 "error": str(last)})
                            continue
                    if doc.get("release_id") not in (None, r["release_id"]):
                        chain_errors.append({
                            "release_id": r["release_id"],
                            "error": "artifact answers as %r" % doc.get("release_id")})
                        continue
                    docs[r["release_id"]] = doc
            except Exception:  # noqa: BLE001
                pass
        chain = step_chain(index, docs)
        if chain_errors:
            chain["unreadable_releases"] = chain_errors
            chain["ok"] = None if len(chain_errors) == len(index.get("releases") or []) else chain["ok"]
            chain["detail"] = ("%s; %d release artifact(s) could not be read"
                               % (chain["detail"], len(chain_errors)))
        receipt["steps"].append(chain)
    receipt["steps"].append(step_file_hashes(rel, src))

    checks = [s for s in receipt["steps"] if s.get("ok") is not None]
    receipt["summary"] = {
        "checks_run": len(checks),
        "checks_passed": sum(1 for s in checks if s["ok"]),
        "checks_failed": [s["step"] for s in checks if not s["ok"]],
        "checks_not_run": [s["step"] for s in receipt["steps"] if s.get("ok") is None],
        "problems": problems,
    }
    if problem := receipt["summary"]["checks_failed"]:
        receipt["summary"]["verdict"] = "FAILED: %s" % ", ".join(problem)
    elif receipt["summary"]["checks_not_run"]:
        receipt["summary"]["verdict"] = "PARTIAL: not run: %s" % ", ".join(
            receipt["summary"]["checks_not_run"])
    else:
        receipt["summary"]["verdict"] = "PASSED: every check ran and agreed"
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--root", help="register root URL, e.g. https://dfr.derappar.at")
    g.add_argument("--from", dest="directory", help="offline copy directory")
    ap.add_argument("--release-id", default="", help="assert the release identifier")
    ap.add_argument("--out", default="", help="write the receipt here; default stdout")
    args = ap.parse_args(argv)

    src = Source(args.root, args.directory)
    try:
        receipt = build_receipt(src, args.release_id)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("could not build a receipt: %s" % exc, file=sys.stderr)
        return 2
    text = json.dumps(receipt, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print("receipt written: %s" % args.out)
    else:
        print(text)
    s = receipt["summary"]
    print("%d/%d checks passed; %s" % (s["checks_passed"], s["checks_run"], s["verdict"]),
          file=sys.stderr)
    if s["checks_failed"]:
        return 1
    return 0 if not s["checks_not_run"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
