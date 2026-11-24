"""Tests for the authority answer-age check (WG0 #71 R1 / R3).

The case that matters is the one IETF WIMSE lists as *planned* rather than
shipped: an answer that is fresh at the validation instant T and over the bound
by the decision instant A, because a person waited between them. That is
`test_fresh_at_T_over_the_bound_at_A` below.
"""
import unittest

from uibc_core.authority_age import (
    FAIL,
    INCONCLUSIVE,
    PASS,
    answer_age,
    check_link,
    decision_record,
    evaluate_links,
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
