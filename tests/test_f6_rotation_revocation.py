"""F6 acceptance: key rotation must not erase or silently lift a revocation.

F6 (from `_104` W4 / `_101` Item 1) asks for four things. Three of them are
assertable here and one is not, so this file states which is which rather than
claiming a clean sweep:

- (1) rotation revocation records are read back — asserted, including records
      that carry different key ids across the rotation;
- (2) behaviour before and after the revocation instant differs — asserted;
- (3) rotation preserves history — asserted, and asserted in the strong form:
      a rotation may not lift a revocation without evidence and explicit
      reinstatement, which is `trust_state`'s existing rule, not a new one;
- (4) full suite green with runner + platform + commit reported — **not** all
      green on this host. Two subprocess tests need a POSIX shell and fail with
      `FileNotFoundError [WinError 2]`; that is declared in the README note of
      PR #425. The last check therefore stays PARTIAL rather than PASS.

Two modules are used together on purpose: `trust_state.transition` decides
whether a sequence is legal, `authority_age.status_at` decides what the status
was at an instant. A rotation that produces an illegal sequence fails the first
even when the second would read it happily.
"""
import unittest

from uibc_core.authority_age import (
    commit_recheck_from_history,
    status_at,
)
from uibc_core.trust_state import TransitionError, transition
from uibc_core.interop_result import ResultError

# One authority, seen across a key rotation at 10:00, revoked at 09:30.
HISTORY = [
    {"at": "2026-11-24T08:00:00Z", "new": "VERIFIED", "key_id": "key-1"},
    {"at": "2026-11-24T09:30:00Z", "new": "REVOKED", "reason": "key compromise",
     "key_id": "key-1"},
    {"at": "2026-11-24T10:00:00Z", "new": "VERIFIED", "key_id": "key-2",
     "reinstated": True},
]

T = "2026-11-24T09:00:00Z"
AFTER_REVOKE = "2026-11-24T09:45:00Z"
AFTER_ROTATION = "2026-11-24T10:30:00Z"


class F6_1_RecordsReadBack(unittest.TestCase):
    """(1) rotation revocation records are read back."""

    def test_records_with_different_key_ids_are_all_read(self):
        status = status_at(HISTORY, AFTER_ROTATION)
        self.assertEqual(status["state"], "VERIFIED")
        self.assertEqual(status["records_used"], 3)

    def test_key_id_does_not_change_the_verdict(self):
        without_keys = [{k: v for k, v in r.items() if k != "key_id"} for r in HISTORY]
        self.assertEqual(status_at(HISTORY, AFTER_ROTATION)["state"],
                         status_at(without_keys, AFTER_ROTATION)["state"])

    def test_revocation_record_is_visible_while_a_later_key_exists(self):
        status = status_at(HISTORY, AFTER_REVOKE)
        self.assertEqual(status["state"], "REVOKED")
        self.assertEqual(status["reason"], "key compromise")


class F6_2_BeforeAndAfterTheRevocation(unittest.TestCase):
    """(2) behaviour differs either side of the revocation instant."""

    def test_before_the_instant_the_link_was_verified(self):
        self.assertEqual(status_at(HISTORY, T)["state"], "VERIFIED")

    def test_after_the_instant_the_link_is_revoked(self):
        self.assertEqual(status_at(HISTORY, AFTER_REVOKE)["state"], "REVOKED")

    def test_commit_recheck_refuses_on_the_revoked_side(self):
        result = commit_recheck_from_history({"mandate": HISTORY}, AFTER_REVOKE,
                                             {"mandate": 7200})
        self.assertEqual(result["outcome"], "refused")
        self.assertEqual(result["reason_codes"], ["authority_revoked"])

    def test_commit_recheck_executes_on_the_verified_side(self):
        result = commit_recheck_from_history({"mandate": HISTORY}, T,
                                             {"mandate": 7200})
        self.assertEqual(result["outcome"], "executed")


class F6_3_RotationPreservesHistory(unittest.TestCase):
    """(3) rotation preserves history, and cannot silently lift a revocation."""

    def test_the_sequence_after_rotation_is_still_readable(self):
        # The revocation stays in the record, with its reason, and is still
        # visible after the later key appears.
        self.assertEqual(len(HISTORY), 3)
        self.assertEqual(HISTORY[1]["new"], "REVOKED")
        self.assertIn("reason", HISTORY[1])
        self.assertEqual(status_at(HISTORY, AFTER_REVOKE)["reason"], "key compromise")

    def test_rotation_without_evidence_is_rejected_by_the_state_machine(self):
        with self.assertRaises((TransitionError, ValueError)):
            transition("REVOKED", "VERIFIED", evidence=[], reinstated=False)

    def test_rotation_without_reinstatement_flag_is_rejected(self):
        with self.assertRaises(TransitionError):
            transition("REVOKED", "VERIFIED",
                       evidence=[{"id": "e1", "type": "key", "issuer": "i",
                                  "digest": "sha256:" + "a" * 64}],
                       reinstated=False)

    def test_a_legal_reinstatement_is_accepted(self):
        record = transition("REVOKED", "VERIFIED",
                            evidence=[{"id": "e1", "type": "key", "issuer": "i",
                                       "digest": "sha256:" + "b" * 64}],
                            reinstated=True)
        self.assertEqual(record["rule"], "with_evidence_and_reinstatement")

    def test_rotation_cannot_move_a_revoked_link_back_silently(self):
        # What the state machine forbids is exactly the failure F6 guards: a
        # new key arriving is not evidence about the old subject.
        silent = [
            {"at": "2026-11-24T08:00:00Z", "new": "VERIFIED", "key_id": "key-1"},
            {"at": "2026-11-24T09:30:00Z", "new": "REVOKED", "reason": "compromise",
             "key_id": "key-1"},
            {"at": "2026-11-24T10:00:00Z", "new": "VERIFIED", "key_id": "key-2"},
        ]
        with self.assertRaises((TransitionError, ResultError)):
            transition(silent[-2]["new"], silent[-1]["new"], evidence=[],
                       reinstated=False)


class F6_4_FullSuiteGreen(unittest.TestCase):
    """(4) NOT green on this host. Skipped explicitly, never reported as pass."""

    @unittest.skip("needs a POSIX shell: two subprocess tests fail with "
                   "FileNotFoundError [WinError 2] on Windows (declared in the "
                   "README note of PR #425). F6 item (4) stays PARTIAL.")
    def test_full_suite_green(self):
        self.fail("cannot be asserted on this host")


if __name__ == "__main__":
    unittest.main()
