"""uibc-core: UIBC Core reference implementation v0.2.2 [PROPOSAL].

Implements the minimal object model from the XLGD/LGD/UIBC master archive (v0.1.0, SS9-SS22):
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

__version__ = "0.2.2"
SPEC_VERSION = "uibc-core/0.2.2-proposal"
VERIFIER_ID = "uibc-core-verifier"
