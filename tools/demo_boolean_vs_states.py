"""Two worlds, one scenario: a boolean gate versus this repository.

    python tools/demo_boolean_vs_states.py

Scenario, all UTC on one day: the authority answered "verified" at 08:00. The
decision is taken at 09:00. The authority is revoked at 09:30. The action
commits at 10:00.

  A. commit at 09:00  -- nothing changed
  B. commit at 10:00  -- revoked in between
  C. no answer was ever recorded

The boolean gate holds one bit. So every case is compared on three layers, and
the table prints all three rather than picking the flattering one:

  decision state  -- what was established when the decision was taken
  commit outcome  -- what happens at commit
  reason          -- why, in a word a reader can check

Exit code 0 means every assertion held.
"""
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

from uibc_core.authority_age import (  # noqa: E402
    CHANGED,
    CURRENT,
    EXECUTED,
    INCONCLUSIVE,
    PASS,
    REFUSED,
    check_link,
    commit_recheck_from_history,
)

IAT = "2026-11-24T08:00:00Z"
T = "2026-11-24T09:00:00Z"
REVOKED = "2026-11-24T09:30:00Z"
LATE = "2026-11-24T10:00:00Z"
BOUND = 7200

HISTORY = [
    {"at": IAT, "new": "VERIFIED"},
    {"at": REVOKED, "new": "REVOKED", "reason": "key compromise"},
]


def boolean_world(case):
    """A gate that knows only allow/deny, holding one bit of state."""
    if case == "C":
        return "deny"
    return "allow"


def uibc_world(case):
    """(decision state, commit state, outcome, reasons, note)"""
    if case == "A":
        age = check_link(IAT, T, BOUND, link="mandate")
        commit = commit_recheck_from_history({"mandate": HISTORY}, T, {"mandate": BOUND})
        return (age["state"], commit["state"], commit["outcome"],
                commit["reason_codes"],
                "answer %ds old at decision; status at commit VERIFIED"
                % age["age_seconds"])
    if case == "B":
        commit = commit_recheck_from_history({"mandate": HISTORY}, LATE, {"mandate": BOUND})
        return (PASS, commit["state"], commit["outcome"], commit["reason_codes"],
                "answer is young, but status at commit is REVOKED since 09:30")
    commit = commit_recheck_from_history({"mandate": []}, LATE, {"mandate": BOUND})
    return (INCONCLUSIVE, commit["state"], commit["outcome"], commit["reason_codes"],
            "no answer was ever recorded")


def main() -> int:
    failures = 0
    print("scenario: answered 08:00 | decision 09:00 | revoked 09:30 | commit varies\n")
    header = "%-2s %-7s | %-11s %-11s %-8s %-18s | %s" % (
        "#", "boolean", "decision", "commit", "outcome", "reason", "note")
    print(header)
    print("-" * len(header))

    expectations = {
        "A": dict(boolean="allow", decision=PASS, outcome=EXECUTED, reasons=[]),
        "B": dict(boolean="allow", decision=PASS, outcome=REFUSED,
                  reasons=["authority_revoked"]),
        "C": dict(boolean="deny", decision=INCONCLUSIVE, outcome=REFUSED,
                  reasons=["authority_unknown"]),
    }

    for case in ("A", "B", "C"):
        b = boolean_world(case)
        dec, cstate, outcome, reasons, note = uibc_world(case)
        print("%-2s %-7s | %-11s %-11s %-8s %-18s | %s" % (
            case, b, dec, cstate, outcome, ",".join(reasons) or "-", note))

        want = expectations[case]
        got = dict(boolean=b, decision=dec, outcome=outcome, reasons=reasons)
        if got != want:
            failures += 1
            print("    ASSERT FAILED for %s: got %r, want %r" % (case, got, want))

    print()
    print("What the three layers say, read together:")
    print("  A  boolean allow   | decision fresh      | commit execute  | -")
    print("  B  boolean allow   | decision fresh      | commit refuse   | authority_revoked")
    print("  C  boolean deny    | decision unresolved | commit refuse   | authority_unknown")
    print()
    print("Two sentences, no more:")
    print("  1. On B the boolean gate lets the action run while this repository refuses")
    print("     it -- the status went from verified to revoked between decision and commit.")
    print("  2. On B and C this repository refuses in both cases but names different")
    print("     reasons, authority_revoked versus authority_unknown, and keeps C's")
    print("     decision unresolved so a later reader can tell 'withdrawn' from")
    print("     'never looked'. A one-bit gate has no third value to hold that.")
    print()
    print("3 case(s), %d assertion failure(s)" % failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
