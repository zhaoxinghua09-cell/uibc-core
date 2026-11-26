"""Patch: stop colliding with the now-published SCITT vocabulary.

Three defects, all found by reading the WG's November 2026 output:

1. This draft used the member name `vds` for "which verifier key signed", while
   RFC 9942 and both published receipt profiles use `vds` (label 395) for the
   verifiable-data-structure *algorithm* identifier, which fixes the hash and the
   node value size, and which a verifier MUST reject if unsupported. Two meanings
   on one name is the kind of collision a working group notices first.
   Rename ours to `verifier_id` and say why.

2. G.2 paraphrased the MMR profile as "reject a receipt whose vds names a verifier
   outside the reader's policy set". That is not what the profile says. Correct it
   and cite the profile.

3. The draft builds on SCITT but never says so: RFC 9943 and RFC 9942 exist as of
   2026-06-30. Add the dependency in the references, plainly, and keep the older
   individual drafts as history.
"""
import io
import sys

FILES = ["drafts/draft-zhao-uibc-evidence-chain-01.md",
         "drafts/draft-zhao-uibc-evidence-chain-00.md"]

REPL = [
    # --- 1. the member name --------------------------------------------------
    ("  (`owner` or `witness`, and the two roles must use distinct\n"
     "  keys), and optionally the verifier identity `vds`. A head is not a package",
     "  (`owner` or `witness`, and the two roles must use distinct\n"
     "  keys), and optionally the verifier identity `verifier_id` (Section 2.1).\n"
     "  A head is not a package"),

    ("(`owner` or `witness`), `tree_size`, and `vds`. It is signed over RFC 8785\n"
     "canonical bytes of that object, with `tree_size` and `vds` omitted only when the\n"
     "signer did not observe them. `tree_size` and `vds` sit inside the signed\n"
     "statement, so neither the size nor the verifier identity can be swapped after\n"
     "signing.",
     "(`owner` or `witness`), `tree_size`, and optionally `verifier_id`. It is signed\n"
     "over RFC 8785 canonical bytes of that object, with `tree_size` and `verifier_id`\n"
     "omitted only when the signer did not observe them. Both sit inside the signed\n"
     "statement, so neither the size nor the verifier identity can be swapped after\n"
     "signing."),

    ("- **Vds**: a verifier identity — the key-id hash of the verifier's key — carried\n"
     "  inside a signed statement so a reader can tell which verifier saw which size.\n"
     "  It names a verifier, never an algorithm; \"a `vds` the reader does not\n"
     "  recognise\" (Appendix G.2) means \"a verifier outside the reader's policy set\",\n"
     "  and scheme support is a separate question, decided by `resolver`.",
     "- **Verifier id** (`verifier_id`): the key-id hash of the verifier's key, carried\n"
     "  inside a signed statement so a reader can tell which verifier observed which\n"
     "  size. It names a verifier, never a hash algorithm.\n"
     "- **Not `vds`.** RFC 9942 and the CCF and MMR receipt profiles use the header\n"
     "  parameter `vds` (label 395) for the verifiable-data-structure *algorithm*: the\n"
     "  value fixes the hash function and the node value size, and a verifier MUST\n"
     "  reject a receipt whose `vds` it does not support (Section 2.1 of\n"
     "  `draft-ietf-scitt-receipts-mmr-profile-00`). This document does not use that\n"
     "  name for anything. Reusing a published name for a different object is how a\n"
     "  reader ends up unable to tell an algorithm identifier from a key identifier,\n"
     "  and the collision is cheap to avoid."),

    ("| Head (Appendix F) | the root, the tree size, and optionally the verifier identity `vds`, inside one signed statement",
     "| Head (Appendix F) | the root, the tree size, and optionally the verifier identity `verifier_id`, inside one signed statement"),

    # --- 2. correct the paraphrase of the MMR profile -----------------------
    ("   right answer for an algorithm we do not support — the MMR receipts profile\n"
     "   requires rejecting a receipt whose `vds` names a verifier outside the reader's\n"
     "policy set, and",
     "   right answer for an algorithm we do not support — the MMR receipts profile\n"
     "   requires rejecting a receipt whose `vds` (the algorithm identifier) the reader\n"
     "   does not support, and"),

    ("consistent REJECT, matching the\n"
     "MMR receipts profile's requirement to reject a receipt whose VDS the reader\n"
     "does not recognise.",
     "consistent REJECT, matching the\n"
     "MMR receipts profile's requirement to reject a receipt whose `vds` the reader\n"
     "does not support. Note that the profile's `vds` is an algorithm identifier; this\n"
     "document's `verifier_id` is a key identifier, and the two are never compared."),

    # --- 3. the dependency on published standards ----------------------------
    ("Normative: [RFC2119], [RFC8174], [RFC3339], [RFC8032], [RFC2104].",
     "Normative: [RFC2119], [RFC8174], [RFC3339], [RFC8032], [RFC2104].\n"
     "\n"
     "Published standards this document builds on, read 2026-11-27: [RFC9943]\n"
     "(*An Architecture for Trustworthy and Transparent Digital Supply Chains*,\n"
     "Proposed Standard, 2026-06-30) and [RFC9942] (*CBOR Object Signing and\n"
     "Encryption (COSE) Receipts*, Proposed Standard, 2026-06-30). This document does\n"
     "not define a transparency service, a receipt format, or a verifiable-data-structure\n"
     "algorithm; it defines what a *package* commits and does not commit, and it reads\n"
     "receipts produced under those documents. Where a receipt is present, its meaning\n"
     "is theirs, not ours.\n"
     "\n"
     "The two receipt profiles the working group added in November 2026 are cited as\n"
     "live, at the revisions read on 2026-11-27:\n"
     "`draft-ietf-scitt-receipts-ccf-profile` **06** (2026-11-19) and\n"
     "`draft-ietf-scitt-receipts-mmr-profile` **00** (2026-11-21)."),
]


def main():
    for path in FILES:
        text = io.open(path, encoding="utf-8").read()
        miss = []
        for old, new in REPL:
            if old not in text:
                miss.append(old.splitlines()[0][:70])
                continue
            text = text.replace(old, new)
        if miss:
            print("PATTERN MISS in %s:" % path)
            for m in miss:
                print("  " + m)
            return 1
        io.open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("patched %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
