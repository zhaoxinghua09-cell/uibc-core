"""uibc-core: UIBC Core reference implementation v0.3.0 [PROPOSAL].

Implements the minimal object model from the LGD/UIBC master archive (v0.1.0, SS9-SS22):
Agent, Identity, Event, Evidence, Run/Manifest, Evidence Root, Verification, Seal Signature.

v0.2: adds seal signatures (HMAC-SHA256 PROVISIONAL, Ed25519 = v0.3 target),
verifier check S6, and strict verification mode (--key). Closes the v0.1
'malicious' fixture blind spot (self-consistent forgery without the key).

v0.2.2: two verdict-affecting fixes surfaced by the new memory mutation corpus
(see fixtures/generate_memory_fixtures.py) - an injected duplicate memory_id in
a migration target is no longer silently discarded, and an empty-to-empty
migration is no longer a PASS. Registered as a breaking change in CHANGELOG.md.

Status: PROPOSAL. Not a ratified standard. Verification results are scoped proofs:
a PASS means "no violation detected within the observed evidence boundary".
"""

__version__ = "0.4.1"
# A version string that is a literal, not a lookup. A clean `git clone` with
# no installed distribution must still report the same identifier; deriving it
# from installed package metadata made an outsider see "0.0.0-proposal"
# (pre-release review blocker P0-2). The importlib branch kept on `main` is the
# version of that code this merge deliberately drops: an outsider who clones and
# runs from the source tree is exactly the case it broke.
SPEC_VERSION = "uibc-core/0.3.3-proposal"
VERIFIER_ID = "uibc-core-verifier"


def impl_digest() -> str:
    """sha256 over every module of this package, sorted by name.

    Muse asked for an *immutable* identifier: a version string alone can be
    reused across different bytes. SPEC_ID pins the label to the code, so a
    verifier's report can never claim a provenance it did not execute.
    """
    import hashlib
    import os
    d = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for name, body in _module_bodies(d):
        h.update(name.encode("utf-8") + b"\0" + hashlib.sha256(body).digest())
    return h.hexdigest()


def _module_bodies(directory):
    """(name, bytes) for every module of this package, sorted by name.

    A zipapp puts the package inside an archive, so `__file__` names a path that
    is not a directory. Reading through the archive keeps SPEC_ID identical to
    the checkout it was built from - a verifier that reports a different
    provenance depending on how it was packaged would be reporting the
    packaging rather than the code.
    """
    import os
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".py"))
        return [(n, open(os.path.join(directory, n), "rb").read()) for n in names]
    except OSError:
        import zipfile
        archive = os.path.dirname(directory)
        prefix = os.path.basename(directory) + "/"
        with zipfile.ZipFile(archive) as z:
            out = []
            for name in sorted(z.namelist()):
                if (name.startswith(prefix) and name.endswith(".py")
                        and "/" not in name[len(prefix):]):
                    out.append((name[len(prefix):], z.read(name)))
            return out


def spec_id() -> str:
    """`<version>@<12 hex>` — the label plus the bytes it names."""
    return "%s@%s" % (SPEC_VERSION, impl_digest()[:12])

