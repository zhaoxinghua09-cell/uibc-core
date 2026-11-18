"""Export a U-IBC package as an Agent Action Capsule (format 4).

Two profiles describe the same thing -- what an agent did, committed to by
digests -- in different shapes. Both claim RFC 8785 JCS for their digests, so
a capsule we build should be readable by their reference verifier. Whether it
actually is, is not something a document can assert.

So this tool builds the capsule with OUR canonicalizer (uibc_core.canonical),
never theirs, and the test hands the result to `agent_action_capsule.verify`
when that package is installed. Their verifier is the judge; our code is only
the producer. If the two JCS implementations ever disagreed, the capsule_id
would fail their recomputation and the test would say so -- that is the point
of testing against someone else's implementation rather than our own.

    python3 tools/emit_aac_capsule.py --package fixtures/clean.uibc --out cap.json

Field mapping (package -> capsule):

    manifest.evidence_root   -> action_id      (the digest of what was recorded)
    identity.agent_id        -> operator       (who acted)
    manifest.agent_version   -> developer      (which build acted)
    manifest.created_at      -> timestamp
    (fixed)                  -> action_type "fyi": a record, not a decision

Nothing is invented: every value comes off the package. A package that fails
its own verification still exports -- the export describes the claim, it does
not endorse it.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.canonical import canonicalize  # noqa: E402

SPEC_VERSION = "draft-mih-scitt-agent-action-capsule-05"
FORMAT_VERSION = "4"
CANONICALIZATION_ID = "jcs"
# The two local-only fields the profile excludes from any capsule_id preimage.
_EXCLUDED = ("capsule_id", "signature", "key_id")


def _load(pkg, name):
    with open(os.path.join(pkg, name), encoding="utf-8") as f:
        return json.load(f)


def _jcs_digest(value):
    raw = canonicalize(value)
    if not isinstance(raw, bytes):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def capsule_id_of(capsule):
    """Recompute the capsule_id the way the profile says, with our JCS."""
    body = {k: v for k, v in capsule.items() if k not in _EXCLUDED}
    return _jcs_digest(body)


def build_capsule(package_dir):
    manifest = _load(package_dir, "manifest.json")
    identity = _load(package_dir, "identity.json")
    root = manifest.get("evidence_root")
    if not root:
        raise ValueError("manifest has no evidence_root; nothing to commit to")
    body = {
        "spec_version": SPEC_VERSION,
        "format_version": FORMAT_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "action_id": root,
        "action_type": "fyi",
        "operator": identity.get("agent_id") or manifest.get("agent_id"),
        "developer": "uibc-core %s" % manifest.get("agent_version", "?"),
        "timestamp": manifest.get("created_at"),
    }
    capsule = dict(body)
    capsule["capsule_id"] = capsule_id_of(capsule)
    return capsule


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=os.path.join(_REPO, "fixtures",
                                                     "clean.uibc"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--verify", action="store_true",
                    help="also hand the capsule to agent_action_capsule")
    args = ap.parse_args()
    cap = build_capsule(args.package)
    text = json.dumps(cap, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote %s" % args.out)
    else:
        sys.stdout.write(text)
    print("capsule_id: %s" % cap["capsule_id"])
    if args.verify:
        try:
            from agent_action_capsule.verify import verify
        except ImportError:
            print("agent_action_capsule not installed; cannot judge "
                  "(pip install agent-action-capsule)")
            return 2
        result = verify(cap)
        print("their verifier: ok=%s" % result.ok)
        for finding in result.findings or []:
            print("  - %s" % finding)
        return 0 if result.ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
