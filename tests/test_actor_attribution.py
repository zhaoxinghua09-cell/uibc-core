"""21 CFR 11.10(e), the part that can be demonstrated: operator attribution.

The clause asks that audit trails independently record the date and time of
"operator entries and actions". Attribution is the half a record layer can
show rather than assert: every event carries an actor, and the lifecycle check
refuses an event whose actor is not one of the principals recorded for the
package (owner, agent_id). The identity that lists those principals is inside
the seal, so widening the list means re-sealing.

Two packages, identical apart from one event's actor:

- actor defaults to the owner        -> S3 PASS
- actor set to an unrelated name     -> S3 FAIL, naming that actor

Read from S3's own row, not from the package verdict: a minimal package is
legitimately INCONCLUSIVE for reasons unrelated to actors (no external anchor,
no timestamp), and a probe that conflated them would report the wrong thing.
"""
import json
import subprocess
import sys

REPO_ROOT = __file__
PY = sys.executable


def _cli(*args):
    return subprocess.run(
        [PY, "-m", "uibc_core.cli"] + [str(a) for a in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def _build(tmp_path, name, actor=None):
    pkg = tmp_path / name
    key = tmp_path / "key.hex"
    steps = [["keygen", "--out", str(key)], ["init", str(pkg)],
             ["register", str(pkg), "--agent-id", "agent-t", "--owner", "owner-t",
              "--principal-type", "HUMAN"]]
    act = ["event", str(pkg), "--type", "ACTIVATE"]
    if actor:
        act += ["--actor", actor]
    steps += [act, ["submit", str(pkg), "--key", str(key)]]
    for step in steps:
        r = _cli(*step)
        assert r.returncode == 0, (step[0], (r.stdout + r.stderr)[:200])
    return pkg, key


def _s3(pkg, key):
    r = _cli("verify", str(pkg), "--key", str(key))
    data = json.loads(r.stdout)
    for c in data.get("checks", []):
        if c.get("id") == "S3":
            return c.get("result"), (c.get("detail") or "")
    return None, ""


def test_actor_defaults_to_the_owner_and_passes(tmp_path):
    pkg, key = _build(tmp_path, "good")
    res, detail = _s3(pkg, key)
    assert res == "PASS", detail
    assert "actors authorised" in detail


def test_an_event_by_a_non_principal_fails_and_is_named(tmp_path):
    pkg, key = _build(tmp_path, "bad", actor="intruder-not-a-principal")
    res, detail = _s3(pkg, key)
    assert res == "FAIL", detail
    assert "not an authorised principal" in detail
    assert "intruder-not-a-principal" in detail
