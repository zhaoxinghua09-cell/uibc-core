"""Tests for the authority answer-age check (WG0 #71 R1 / R3).

The case that matters is the one IETF WIMSE lists as *planned* rather than
shipped: an answer that is fresh at the validation instant T and over the bound
by the decision instant A, because a person waited between them. That is
`test_fresh_at_T_over_the_bound_at_A` below.
"""
import unittest

from uibc_core.authority_age import (
    CHANGED,
    CURRENT,
    EXECUTED,
    FAIL,
    INCONCLUSIVE,
    PASS,
    REFUSED,
    answer_age,
    check_link,
    commit_recheck,
    commit_recheck_from_history,
    decision_record,
    evaluate_links,
    status_at,
)

T = "2026-11-24T09:00:00Z"   # validation instant
A = "2026-11-24T11:00:00Z"   # decision instant, two hours later
IAT = "2026-11-24T08:00:00Z"  # the source answered at 08:00 per the case in #71


class TestAnswerAge(unittest.TestCase):
    def test_age_is_plain_difference(self):
        self.assertEqual(answer_age(IAT, T), 3600.0)

    def test_local_time_without_zone_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            answer_age("2026-11-24T08:00:00", T)
        self.assertIn("timezone", str(caught.exception).lower())

    def test_not_iso_is_refused(self):
        with self.assertRaises(ValueError):
            answer_age("yesterday", T)


class TestCheckLink(unittest.TestCase):
    def test_within_bound_passes(self):
        row = check_link(IAT, T, 7200, link="mandate")
        self.assertEqual(row["state"], PASS)
        self.assertEqual(row["age_seconds"], 3600.0)
        self.assertEqual(row["link"], "mandate")

    def test_over_bound_fails(self):
        row = check_link(IAT, A, 7200, link="mandate")
        self.assertEqual(row["state"], FAIL)
        self.assertIn("exceeds", row["detail"])

    def test_no_answer_is_inconclusive_not_pass(self):
        row = check_link(None, T, 7200, link="mandate")
        self.assertEqual(row["state"], INCONCLUSIVE)
        self.assertIsNone(row["age_seconds"])

    def test_future_dated_answer_is_inconclusive(self):
        row = check_link("2026-11-24T09:30:00Z", T, 7200, link="mandate")
        self.assertEqual(row["state"], INCONCLUSIVE)
        self.assertLess(row["age_seconds"], 0)

    def test_bad_bound_is_refused(self):
        for bound in (None, 0, -5):
            with self.subTest(bound=bound):
                with self.assertRaises(ValueError):
                    check_link(IAT, T, bound)


class TestAggregate(unittest.TestCase):
    def test_worst_wins_and_unanswered_cannot_pass(self):
        result = evaluate_links(
            {"anchor": IAT, "mandate": None, "operator": IAT},
            T, {"anchor": 7200, "mandate": 7200, "operator": 7200})
        self.assertEqual(result["state"], INCONCLUSIVE)
        states = {row["link"]: row["state"] for row in result["links"]}
        self.assertEqual(states["anchor"], PASS)
        self.assertEqual(states["mandate"], INCONCLUSIVE)

    def test_one_fail_beats_other_passes(self):
        result = evaluate_links(
            {"anchor": IAT, "mandate": IAT}, T,
            {"anchor": 7200, "mandate": 10})
        self.assertEqual(result["state"], FAIL)

    def test_star_default_applies(self):
        result = evaluate_links({"anchor": IAT}, T, {"*": 7200})
        self.assertEqual(result["state"], PASS)

    def test_every_link_appears(self):
        result = evaluate_links({"anchor": IAT, "mandate": IAT}, T,
                                {"anchor": 7200, "mandate": 7200})
        self.assertEqual(len(result["links"]), 2)


class TestFreshAtTOverTheBoundAtA(unittest.TestCase):
    """The concrete two-instants case: same answer, different verdicts."""

    def test_fresh_at_T_over_the_bound_at_A(self):
        at_T = check_link(IAT, T, 7200, link="mandate")
        at_A = check_link(IAT, A, 7200, link="mandate")
        self.assertEqual(at_T["state"], PASS)
        self.assertEqual(at_A["state"], FAIL)
        self.assertEqual(at_A["age_seconds"], 3 * 3600.0)
        self.assertEqual(at_T["age_seconds"], 3600.0)


class TestCommitRecheck(unittest.TestCase):
    """The window between decision and commit (OAR Section 4.2)."""

    def test_still_current_at_commit_executes(self):
        result = commit_recheck({"mandate": IAT}, T, {"mandate": 7200})
        self.assertEqual(result["state"], CURRENT)
        self.assertEqual(result["outcome"], EXECUTED)
        self.assertEqual(result["reason_codes"], [])

    def test_going_stale_before_commit_refuses(self):
        result = commit_recheck({"mandate": IAT}, A, {"mandate": 7200})
        self.assertEqual(result["state"], CHANGED)
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_expired"])

    def test_no_answer_at_commit_refuses(self):
        result = commit_recheck({"mandate": None}, T, {"mandate": 7200})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_unknown"])

    def test_answer_dated_after_commit_refuses_with_skew(self):
        result = commit_recheck({"mandate": "2026-11-24T09:30:00Z"}, T, {"mandate": 7200})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_clock_skew"])

    def test_one_changed_link_is_enough_to_refuse(self):
        result = commit_recheck(
            {"anchor": IAT, "mandate": IAT}, A,
            {"anchor": 7200, "mandate": 86400})
        self.assertEqual(result["outcome"], REFUSED)


REVOKED_AT_1030 = [
    {"at": "2026-11-24T08:00:00Z", "new": "VERIFIED"},
    {"at": "2026-11-24T10:30:00Z", "new": "REVOKED", "reason": "key compromise"},
]


class TestStatusAt(unittest.TestCase):
    """Our own revocation history, read at an instant."""

    def test_status_before_revocation_is_verified(self):
        status = status_at(REVOKED_AT_1030, "2026-11-24T10:00:00Z")
        self.assertEqual(status["state"], "VERIFIED")
        self.assertEqual(status["records_used"], 1)

    def test_status_after_revocation_is_revoked(self):
        status = status_at(REVOKED_AT_1030, "2026-11-24T11:00:00Z")
        self.assertEqual(status["state"], "REVOKED")
        self.assertEqual(status["reason"], "key compromise")

    def test_later_records_are_not_read_backwards(self):
        # A revocation dated after the instant must not describe that instant.
        status = status_at(REVOKED_AT_1030, "2026-11-24T09:00:00Z")
        self.assertEqual(status["state"], "VERIFIED")

    def test_no_record_at_all_is_no_state(self):
        status = status_at([], "2026-11-24T09:00:00Z")
        self.assertIsNone(status["state"])
        self.assertIn("not the same as being valid", status["detail"])


class TestCommitRecheckFromHistory(unittest.TestCase):
    """Revocation derived from our record, not from a caller's answer."""

    def test_revoked_before_commit_refuses_even_with_young_answer(self):
        result = commit_recheck_from_history(
            {"mandate": REVOKED_AT_1030}, A, {"mandate": 7200})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_revoked"])

    def test_still_verified_at_commit_executes(self):
        result = commit_recheck_from_history(
            {"mandate": REVOKED_AT_1030}, "2026-11-24T10:00:00Z", {"mandate": 7200})
        self.assertEqual(result["outcome"], EXECUTED)
        self.assertEqual(result["reason_codes"], [])

    def test_revocation_after_commit_does_not_affect_this_action(self):
        result = commit_recheck_from_history(
            {"mandate": REVOKED_AT_1030}, "2026-11-24T10:00:00Z", {"mandate": 7200})
        self.assertEqual(result["state"], CURRENT)

    def test_verified_but_over_the_bound_still_refuses(self):
        fresh_but_old = [{"at": "2026-11-24T08:00:00Z", "new": "VERIFIED"}]
        result = commit_recheck_from_history({"mandate": fresh_but_old}, A,
                                             {"mandate": 7200})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_expired"])

    def test_no_history_refuses_as_unknown(self):
        result = commit_recheck_from_history({"mandate": []}, A, {"mandate": 7200})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_unknown"])

    def test_one_revoked_link_refuses_the_whole_action(self):
        result = commit_recheck_from_history(
            {"anchor": [{"at": "2026-11-24T08:00:00Z", "new": "VERIFIED"}],
             "mandate": REVOKED_AT_1030},
            A, {"anchor": 86400, "mandate": 86400})
        self.assertEqual(result["outcome"], REFUSED)
        self.assertEqual(result["reason_codes"], ["authority_revoked"])


class TestDecisionRecord(unittest.TestCase):
    def test_record_carries_both_instants_and_ages(self):
        record = decision_record(T, A, {"mandate": None}, {"mandate": 7200},
                                 conditions_met=["revocation notice received"],
                                 recourse_relied_on=["30-day chargeback"])
        self.assertEqual(record["schema"], "uibc-authority-age/1")
        self.assertEqual(record["validation_at"], T)
        self.assertEqual(record["decision_at"], A)
        self.assertEqual(record["state"], INCONCLUSIVE)
        self.assertEqual(record["conditions_met"], ["revocation notice received"])
        self.assertEqual(record["recourse_relied_on"], ["30-day chargeback"])

    def test_unresolved_with_named_recourse_is_kept_unresolved(self):
        # Requirement 3: a reversible action may proceed, and the record keeps
        # the outcome as unresolved -- it must not become a pass because it
        # carries conditions and a recourse.
        record = decision_record(T, A, {"mandate": None}, {"mandate": 7200},
                                 conditions_met=["reversible"],
                                 recourse_relied_on=["chargeback"])
        self.assertEqual(record["state"], INCONCLUSIVE)

    def test_empty_lists_are_still_emitted(self):
        record = decision_record(T, T, {"mandate": IAT}, {"mandate": 7200})
        self.assertEqual(record["conditions_met"], [])
        self.assertEqual(record["recourse_relied_on"], [])

    def test_conditions_cannot_rescue_a_failed_age_check(self):
        with self.assertRaises(ValueError) as caught:
            decision_record(T, A, {"mandate": IAT}, {"mandate": 7200},
                            conditions_met=["we hoped it was fine"])
        self.assertIn("cannot be justified", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
