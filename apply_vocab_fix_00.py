"""Apply the same `vds` -> `verifier_id` rename to the -00 draft.

-00 is the earlier version kept for diff; the vocabulary fix belongs in both so that
a reader comparing them does not see two different member names for one object.
Anchors are exact strings; a miss stops the run instead of writing a half-patched file.
"""
import io
import sys

P = "drafts/draft-zhao-uibc-evidence-chain-00.md"

REPL = [
    ("keys), and optionally the verifier identity `vds`. A head is not a package",
     "keys), and optionally the verifier identity `verifier_id`. A head is not a package"),

    ("- **Vds**: a verifier identity — the key-id hash of the verifier's key — carried\n"
     "  inside a signed statement so a reader can tell which verifier saw which size.\n"
     "  It names a verifier, never an algorithm; \"a `vds` the reader does not",
     "- **Verifier id** (`verifier_id`): the key-id hash of the verifier's key, carried\n"
     "  inside a signed statement so a reader can tell which verifier observed which\n"
     "  size. It names a verifier, never a hash algorithm. RFC 9942 and the CCF and MMR\n"
     "  receipt profiles use `vds` (label 395) for the verifiable-data-structure\n"
     "  algorithm, which fixes the hash and the node size and MUST be rejected when\n"
     "  unsupported; this document does not use that name. \"a `verifier_id` the reader does not"),

    ("| Head (Section 16) | the root, the tree size, and optionally the verifier identity `vds`, inside one signed statement",
     "| Head (Section 16) | the root, the tree size, and optionally the verifier identity `verifier_id`, inside one signed statement"),

    ("(`owner` or `witness`), `tree_size`, and `vds`. It is signed over RFC 8785\n"
     "canonical bytes of that object, with `tree_size` and `vds` omitted only when the\n"
     "signer did not observe them. `tree_size` and `vds` sit inside the signed",
     "(`owner` or `witness`), `tree_size`, and optionally `verifier_id`. It is signed\n"
     "over RFC 8785 canonical bytes of that object, with `tree_size` and `verifier_id`\n"
     "omitted only when the signer did not observe them. Both sit inside the signed"),

    ("requires rejecting a receipt whose `vds` names a verifier outside the reader's",
     "requires rejecting a receipt whose `vds` (an algorithm identifier) the reader"),
]


def main():
    text = io.open(P, encoding="utf-8").read()
    for old, new in REPL:
        if old not in text:
            print("PATTERN MISS: " + old.splitlines()[0][:80])
            return 1
        text = text.replace(old, new)
    io.open(P, "w", encoding="utf-8", newline="\n").write(text)
    print("patched " + P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
