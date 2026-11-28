"""Lint a verify-report JSONL file against the schema that shape belongs to.

Why a separate linter: the schema is a promise to someone outside this
repository. Testing our own output against a schema we wrote and validating
*their* file with the same rules are different jobs, and the second one is what
makes the promise usable. This tool takes any producer's file - ours, a
competitor's, a stranger's - and says which lines do not hold.

No third-party dependency: the schema subset used here is small enough to check
by hand, and a consumer who cannot install `jsonschema` should still be able to
read the rules.

    python tools/report_lint.py runs.jsonl

Six shapes are in use, and a line is judged only by the rules its own `format`
names. That is deliberate: a linter that accepts anything recognisable is a
linter that promises nothing. The pair of formats added on 2026-11-28 (the
readers for the peer's MCP authorization and revocation-list corpora) follow the
same rule — a valid answer carries no finding, a refusal carries at least one,
and `no statement` is never written as `not revoked`. The sixth shape, a receipt
over an A2A card, adds one rule of its own: `accept` has exactly one reason and
a PASS line cannot carry a refusing one.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(HERE, "interop", "verify-report.schema.json")
COSE_SCHEMA = os.path.join(HERE, "interop", "scitt-cose-report.schema.json")
MCP_SCHEMA = os.path.join(HERE, "interop", "mcp-authz-report.schema.json")
REVOKE_SCHEMA = os.path.join(HERE, "interop", "revocation-list-report.schema.json")
KEY_REVOKE_SCHEMA = os.path.join(HERE, "interop", "key-revocation-list-report.schema.json")
RECEIPT_SCHEMA = os.path.join(HERE, "interop", "agent-card-receipt-report.schema.json")
DELTA_SCHEMA = os.path.join(HERE, "interop", "revocation-delta-report.schema.json")

FORMAT = "uibc-verify-report/1"
COSE_FORMAT = "uibc-scitt-cose-report/1"
MCP_FORMAT = "uibc-mcp-authz-report/1"
REVOKE_FORMAT = "uibc-revocation-list-report/1"
KEY_REVOKE_FORMAT = "uibc-key-revocation-list-report/1"
RECEIPT_FORMAT = "uibc-agent-card-receipt-report/1"
DELTA_FORMAT = "uibc-revocation-delta-report/1"
SCHEMAS = {
    FORMAT: SCHEMA,
    COSE_FORMAT: COSE_SCHEMA,
    MCP_FORMAT: MCP_SCHEMA,
    REVOKE_FORMAT: REVOKE_SCHEMA,
    KEY_REVOKE_FORMAT: KEY_REVOKE_SCHEMA,
    RECEIPT_FORMAT: RECEIPT_SCHEMA,
    DELTA_FORMAT: DELTA_SCHEMA,
}
COSE_CODE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESULTS = {"PASS", "FAIL", "INCONCLUSIVE", "ERROR"}
EXITS = {0, 1, 2, 3}
WHEN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
CHECK_ID = re.compile(r"^S[0-9]+$")
#: The ten refusals the peer's revocation-list suite defines, in its order.
REVOKE_REASONS = (
    "revocation_list_shape",
    "revocation_list_signer_not_a_root",
    "revocation_list_signature_unverified",
    "revocation_list_other_chain",
    "revocation_list_rollback",
    "revocation_list_gap",
    "revocation_list_previous_mismatch",
    "revocation_list_time_reversed",
    "revocation_entry_from_future",
    "revocation_list_drops_entry",
)
#: The nine reasons and five decisions of the key-revocation suite.
KEY_REVOKE_REASONS = (
    "signer_not_trusted",
    "list_signature_invalid",
    "list_older_than_accepted",
    "list_stale",
    "revoked_in_list",
    "revoked_kept_from_earlier_list",
    "revocation_not_yet_effective",
    "key_not_covered",
    "covered_no_entry",
)
KEY_REVOKE_DECISIONS = ("revoked", "not_revoked", "no_statement", "rejected", "stale")
KEY_REVOKE_EXIT = {"revoked": 0, "not_revoked": 1, "no_statement": 2, "rejected": 3, "stale": 4}
KEY_REVOKE_BASIS = ("trusted_by_recomputed_thumbprint", "signature", "freshness",
                    "in_list", "retained", "absent", "shape")
#: The sixteen reasons of the agent-card-receipt suite: one accepting, fifteen refusing.
RECEIPT_REASONS = (
    "receipt_current",
    "statement_malformed",
    "statement_type_wrong",
    "predicate_type_wrong",
    "subject_malformed",
    "predicate_malformed",
    "validity_window_inverted",
    "card_malformed",
    "card_digest_mismatch",
    "receipt_not_yet_valid",
    "receipt_expired",
    "revocation_list_absent",
    "revocation_list_malformed",
    "revocation_list_signature",
    "revocation_list_stale",
    "receipt_revoked",
)
REQUIRED = ("format", "vector", "result", "checks_failed", "verifier_id",
            "verifier_version", "when_utc", "exit")
OPTIONAL = ("error",)


def problems(line):
    """Every reason this object is not a report line, in plain words."""
    if not isinstance(line, dict):
        return ["not a JSON object"]
    out = []
    for k in REQUIRED:
        if k not in line:
            out.append("missing %r" % k)
    for k in sorted(set(line) - set(REQUIRED) - set(OPTIONAL)):
        out.append("unknown key %r" % k)
    if out:
        return out
    if line["format"] != FORMAT:
        out.append("format is %r, expected %r" % (line["format"], FORMAT))
    for k in ("vector", "verifier_id", "verifier_version"):
        if not isinstance(line[k], str) or not line[k]:
            out.append("%s must be a non-empty string" % k)
    if line["result"] not in RESULTS:
        out.append("result %r is not one of %s" % (line["result"], sorted(RESULTS)))
    cf = line["checks_failed"]
    if not isinstance(cf, list) or any(not isinstance(c, str) or not CHECK_ID.match(c) for c in cf):
        out.append("checks_failed must be a list of check ids like S4")
    elif line["result"] == "FAIL" and not cf:
        out.append("a FAIL line with no failing check names nothing")
    elif line["result"] != "FAIL" and cf:
        out.append("result %r must not carry failed checks" % line["result"])
    if not isinstance(line["when_utc"], str) or not WHEN.match(line["when_utc"]):
        out.append("when_utc must be YYYY-MM-DDTHH:MM:SSZ")
    if line["exit"] not in EXITS or isinstance(line["exit"], bool):
        out.append("exit must be one of 0, 1, 2, 3")
    elif line["result"] == "ERROR" and line["exit"] != 3:
        out.append("an ERROR line exits 3, not %r" % line["exit"])
    if line["result"] == "ERROR":
        if "error" not in line:
            out.append("an ERROR line must say why")
    elif "error" in line:
        out.append("only an ERROR line carries 'error'")
    if "error" in line:
        e = line["error"]
        if not isinstance(e, str) or not e or len(e) > 300:
            out.append("error must be a string of 1..300 characters")
    return out


COSE_REQUIRED = ("format", "vector", "verdict", "codes", "notes", "verifier_id",
                 "verifier_version", "when_utc", "exit")
COSE_OPTIONAL = ("conforms_to_expected",)


def cose_problems(line):
    """The second shape: what a verifier decided about one Transparent Statement.

    Kept separate from `problems` rather than generalised into it: the two
    shapes answer different questions, and a validator that accepts either
    without saying which rules it applied is the failure mode this file exists
    to catch. The contract is small enough to state: a valid verdict carries no
    codes, a refusal carries at least one and exits 1.
    """
    if not isinstance(line, dict):
        return ["not a JSON object"]
    out = []
    for k in COSE_REQUIRED:
        if k not in line:
            out.append("missing %r" % k)
    for k in sorted(set(line) - set(COSE_REQUIRED) - set(COSE_OPTIONAL)):
        out.append("unknown key %r" % k)
    if out:
        return out
    if line["format"] != COSE_FORMAT:
        out.append("format is %r, expected %r" % (line["format"], COSE_FORMAT))
    for k in ("vector", "verifier_id", "verifier_version"):
        if not isinstance(line[k], str) or not line[k]:
            out.append("%s must be a non-empty string" % k)
    if line["verdict"] not in ("valid", "invalid"):
        out.append("verdict %r is neither 'valid' nor 'invalid'" % (line["verdict"],))
    codes = line["codes"]
    if not isinstance(codes, list) or any(
            not isinstance(c, str) or not COSE_CODE.match(c) for c in codes):
        out.append("codes must be a list of lower-case hyphenated tokens")
    elif line["verdict"] == "invalid" and not codes:
        out.append("an invalid verdict with no code names no ground for the refusal")
    elif line["verdict"] == "valid" and codes:
        out.append("a valid verdict must not carry refusal codes")
    notes = line["notes"]
    if not isinstance(notes, list) or any(not isinstance(n, str) for n in notes):
        out.append("notes must be a list of strings")
    if "conforms_to_expected" in line:
        v = line["conforms_to_expected"]
        if v is not None and not isinstance(v, bool):
            out.append("conforms_to_expected must be true, false or null")
    if not isinstance(line["when_utc"], str) or not WHEN.match(line["when_utc"]):
        out.append("when_utc must be YYYY-MM-DDTHH:MM:SSZ")
    if line["exit"] not in (0, 1) or isinstance(line["exit"], bool):
        out.append("exit must be 0 (valid) or 1 (refused)")
    elif (line["verdict"] == "valid") != (line["exit"] == 0):
        out.append("exit %r does not match verdict %r" % (line["exit"], line["verdict"]))
    return out


MCP_REQUIRED = ("format", "vector", "result", "verdict", "codes", "verifier_id",
                "verifier_version", "when_utc", "exit")
MCP_OPTIONAL = ("error",)


def _scaffold(line, required, optional, fmt):
    """Shape checks every line of every format owes, or None when they hold."""
    if not isinstance(line, dict):
        return ["not a JSON object"]
    out = []
    for k in required:
        if k not in line:
            out.append("missing %r" % k)
    for k in sorted(set(line) - set(required) - set(optional)):
        out.append("unknown key %r" % k)
    if out:
        return out
    if line["format"] != fmt:
        out.append("format is %r, expected %r" % (line["format"], fmt))
    for k in ("vector", "verifier_id", "verifier_version"):
        if not isinstance(line[k], str) or not line[k]:
            out.append("%s must be a non-empty string" % k)
    if not isinstance(line["when_utc"], str) or not WHEN.match(line["when_utc"]):
        out.append("when_utc must be YYYY-MM-DDTHH:MM:SSZ")
    return out


def _error_block(line, out):
    """The error field's own contract, shared by the four non-legacy shapes."""
    if line["result"] == "ERROR":
        if "error" not in line:
            out.append("an ERROR line must say why")
        return
    if "error" in line:
        out.append("only an ERROR line carries 'error'")


def mcp_problems(line):
    """What a verifier observed about one MCP authorization chain.

    A valid observation carries no code; a refusal carries at least one. Keeping
    that pair tied to the exit code is the point of linting the line at all: a
    refusal that exits 0 would be read as an approval by any harness.
    """
    out = _scaffold(line, MCP_REQUIRED, MCP_OPTIONAL, MCP_FORMAT)
    if out:
        return out
    if line["result"] not in ("PASS", "FAIL", "ERROR"):
        out.append("result %r is not one of PASS, FAIL, ERROR" % (line["result"],))
    codes = line["codes"]
    if not isinstance(codes, list) or any(
            not isinstance(c, str) or not COSE_CODE.match(c) for c in codes):
        out.append("codes must be a list of lower-case hyphenated tokens")
        codes = None
    if line["verdict"] is not None and line["verdict"] not in ("valid", "invalid"):
        out.append("verdict %r is neither 'valid' nor 'invalid'" % (line["verdict"],))
    expected_exit = {"PASS": 0, "FAIL": 1, "ERROR": 3}[line["result"]] \
        if line["result"] in ("PASS", "FAIL", "ERROR") else None
    if expected_exit is not None and line["exit"] != expected_exit:
        out.append("result %r exits %d, not %r" % (line["result"], expected_exit, line["exit"]))
    if line["result"] == "PASS":
        if line["verdict"] != "valid":
            out.append("a PASS line carries verdict 'valid', not %r" % (line["verdict"],))
        if codes:
            out.append("a valid observation must not carry findings")
    elif line["result"] == "FAIL":
        if line["verdict"] != "invalid":
            out.append("a FAIL line carries verdict 'invalid', not %r" % (line["verdict"],))
        if codes is not None and not codes:
            out.append("a refusal with no code names no ground for it")
    elif line["result"] == "ERROR":
        if line["verdict"] is not None:
            out.append("an ERROR line carries verdict null, not %r" % (line["verdict"],))
        if codes:
            out.append("an ERROR line carries no findings")
    _error_block(line, out)
    return out


REVOKE_REQUIRED = ("format", "vector", "result", "verdict", "reason", "index",
                   "verifier_id", "verifier_version", "when_utc", "exit")
REVOKE_OPTIONAL = ("error",)


def revoke_problems(line):
    """What a signed cumulative revocation chain forced, and where it stopped."""
    out = _scaffold(line, REVOKE_REQUIRED, REVOKE_OPTIONAL, REVOKE_FORMAT)
    if out:
        return out
    if line["result"] not in ("PASS", "FAIL", "ERROR"):
        out.append("result %r is not one of PASS, FAIL, ERROR" % (line["result"],))
    if line["verdict"] is not None and line["verdict"] not in ("valid", "invalid"):
        out.append("verdict %r is neither 'valid' nor 'invalid'" % (line["verdict"],))
    reason = line["reason"]
    idx = line["index"]
    if idx is not None and (isinstance(idx, bool) or not isinstance(idx, int) or idx < 0):
        out.append("index must be a non-negative integer or null")
        idx = None
    if line["result"] == "PASS":
        if line["verdict"] != "valid":
            out.append("a PASS line carries verdict 'valid', not %r" % (line["verdict"],))
        if reason is not None:
            out.append("a valid chain carries no reason")
        if idx is not None:
            out.append("a valid chain names no position")
    elif line["result"] == "FAIL":
        if line["verdict"] != "invalid":
            out.append("a FAIL line carries verdict 'invalid', not %r" % (line["verdict"],))
        if reason not in REVOKE_REASONS:
            out.append("reason %r is not one of the ten revocation_list_* tokens" % (reason,))
    elif line["result"] == "ERROR":
        if line["verdict"] is not None or reason is not None or idx is not None:
            out.append("an ERROR line carries null verdict, reason and index")
    expected_exit = {"PASS": 0, "FAIL": 1, "ERROR": 3}.get(line["result"])
    if expected_exit is not None and line["exit"] != expected_exit:
        out.append("result %r exits %d, not %r" % (line["result"], expected_exit, line["exit"]))
    _error_block(line, out)
    return out


KEY_REVOKE_REQUIRED = ("format", "vector", "result", "decision", "reason", "basis",
                       "verifier_id", "verifier_version", "when_utc", "exit")
KEY_REVOKE_OPTIONAL = ("error",)


def key_revoke_problems(line):
    """Whether this key is revoked at this time, and the rule that said so.

    The suite's whole point is that three different answers all count as
    reached — revoked, not revoked, and no statement — and that `rejected` and
    `stale` are refusals. A line that files no_statement under FAIL, or that
    lets a refusal exit 0, would hand the reader the exact confusion the reader
    exists to prevent.
    """
    out = _scaffold(line, KEY_REVOKE_REQUIRED, KEY_REVOKE_OPTIONAL, KEY_REVOKE_FORMAT)
    if out:
        return out
    if line["result"] not in ("PASS", "FAIL", "ERROR"):
        out.append("result %r is not one of PASS, FAIL, ERROR" % (line["result"],))
    dec = line["decision"]
    reason = line["reason"]
    basis = line["basis"]
    if dec is not None and dec not in KEY_REVOKE_DECISIONS:
        out.append("decision %r is not one of %s" % (dec, list(KEY_REVOKE_DECISIONS)))
        dec = None
    if reason is not None and reason not in KEY_REVOKE_REASONS:
        out.append("reason %r is not one of the nine suite tokens" % (reason,))
    rule = None
    if basis is not None:
        if not isinstance(basis, dict):
            out.append("basis must be an object like {\"rule\": ...}")
        else:
            rule = basis.get("rule")
            if rule not in KEY_REVOKE_BASIS:
                out.append("basis rule %r is not one of %s" % (rule, list(KEY_REVOKE_BASIS)))
    if line["result"] == "ERROR":
        if dec is not None or reason is not None or basis is not None:
            out.append("an ERROR line carries null decision, reason and basis")
        if line["exit"] != 3:
            out.append("an ERROR line exits 3, not %r" % (line["exit"],))
    elif dec is not None:
        if line["result"] == "PASS" and dec in ("rejected", "stale"):
            out.append("decision %r is a refusal and cannot be filed as PASS" % (dec,))
        if line["result"] == "FAIL" and dec in ("revoked", "not_revoked", "no_statement"):
            out.append("decision %r is an answer that was reached and cannot be filed "
                       "as FAIL" % (dec,))
        if line["exit"] != KEY_REVOKE_EXIT[dec]:
            out.append("decision %r exits %d, not %r"
                       % (dec, KEY_REVOKE_EXIT[dec], line["exit"]))
    if line["result"] != "ERROR" and basis is None:
        out.append("a reached decision must name the rule that produced it")
    if line["result"] == "FAIL" and reason is None:
        out.append("a refusal with no reason names no ground for it")
    _error_block(line, out)
    return out


RECEIPT_REQUIRED = ("format", "vector", "result", "decision", "reason", "subject_digest",
                    "verifier_id", "verifier_version", "when_utc", "exit")
RECEIPT_OPTIONAL = ("error",)
DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def receipt_problems(line):
    """What a verifier decided about one receipt over an A2A card.

    Two things are worth pinning here, because both are easy to get subtly
    wrong and neither shows in the exit code alone: `accept` has exactly one
    reason and every other decision has a refusing one, so a PASS line cannot
    smuggle a `revocation_list_absent` past a reader; and the digest the line
    prints is the one the verifier computed, so a third party can recompute it
    from the card and check the arithmetic rather than the assertion.
    """
    out = _scaffold(line, RECEIPT_REQUIRED, RECEIPT_OPTIONAL, RECEIPT_FORMAT)
    if out:
        return out
    if line["result"] not in ("PASS", "FAIL", "ERROR"):
        out.append("result %r is not one of PASS, FAIL, ERROR" % (line["result"],))
    dec, reason, digest = line["decision"], line["reason"], line["subject_digest"]
    if dec not in ("accept", "reject", None):
        out.append("decision %r is neither 'accept' nor 'reject'" % (dec,))
        dec = None
    if reason is not None and reason not in RECEIPT_REASONS:
        out.append("reason %r is not one of the sixteen suite tokens" % (reason,))
    if digest is not None and (not isinstance(digest, str) or not DIGEST64.match(digest)):
        out.append("subject_digest must be 64 lowercase hex characters or null")
    if line["result"] == "PASS":
        if dec != "accept" or reason != "receipt_current":
            out.append("a PASS line carries accept/receipt_current, not %r/%r"
                       % (dec, reason))
        if digest is None:
            out.append("a PASS line must carry the digest it computed")
    elif line["result"] == "FAIL":
        if dec != "reject":
            out.append("a FAIL line carries decision 'reject', not %r" % (dec,))
        if reason is None or reason == "receipt_current":
            out.append("a refusal must name a refusing reason, not %r" % (reason,))
    elif line["result"] == "ERROR":
        if dec is not None or reason is not None or digest is not None:
            out.append("an ERROR line carries null decision, reason and subject_digest")
        if line["exit"] != 3:
            out.append("an ERROR line exits 3, not %r" % (line["exit"],))
    expected_exit = {"PASS": 0, "FAIL": 1}.get(line["result"])
    if expected_exit is not None and line["exit"] != expected_exit:
        out.append("result %r exits %d, not %r" % (line["result"], expected_exit, line["exit"]))
    _error_block(line, out)
    return out


DELTA_REQUIRED = ("format", "vector", "result", "decision", "reason", "index", "head", "seq",
                  "verifier_id", "verifier_version", "when_utc", "exit")
DELTA_OPTIONAL = ("error",)
DELTA_REASONS = (
    "revocation_list_shape",
    "revocation_list_signer_not_a_root",
    "revocation_list_signature_unverified",
    "revocation_list_other_chain",
    "revocation_list_rollback",
    "revocation_list_gap",
    "revocation_list_previous_mismatch",
    "revocation_list_time_reversed",
    "revocation_entry_from_future",
    "revocation_entry_repeated",
)
LIST_HEAD = re.compile(r"^sha256:[0-9a-f]{64}$")


def delta_problems(line):
    """What a verifier holding a delta-form chain says it holds.

    Three things are pinned: an acceptance names the head a reader would pin
    next and the sequence it reached (a "the chain holds" with no head cannot
    be carried forward); a refusal names neither, because a head for a list that
    was never installed is the mistake the refusal exists to prevent; and the
    ten tokens are the whole vocabulary, so a refusal invented outside them
    would pass an exit-code check while saying nothing a reader can act on.
    """
    out = _scaffold(line, DELTA_REQUIRED, DELTA_OPTIONAL, DELTA_FORMAT)
    if out:
        return out
    if line["result"] not in ("PASS", "FAIL", "ERROR"):
        out.append("result %r is not one of PASS, FAIL, ERROR" % (line["result"],))
    dec, reason, idx = line["decision"], line["reason"], line["index"]
    head, seq = line["head"], line["seq"]
    if dec not in ("accept", "reject", None):
        out.append("decision %r is neither 'accept' nor 'reject'" % (dec,))
        dec = None
    if reason is not None and reason != "in_force" and reason not in DELTA_REASONS:
        out.append("reason %r is not 'in_force' or one of the ten suite tokens" % (reason,))
    if idx is not None and (isinstance(idx, bool) or not isinstance(idx, int) or idx < 0):
        out.append("index must be a non-negative integer or null")
        idx = None
    if head is not None and (not isinstance(head, str) or not LIST_HEAD.match(head)):
        out.append("head must be 'sha256:' plus 64 lowercase hex, or null")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int) or seq < 1):
        out.append("seq must be a positive integer or null")
    if line["result"] == "PASS":
        if dec != "accept" or reason != "in_force":
            out.append("a PASS line carries accept/in_force, not %r/%r" % (dec, reason))
        if idx is not None:
            out.append("an accepted chain names no position")
        if head is None or seq is None:
            out.append("a PASS line must carry the head and seq it holds")
    elif line["result"] == "FAIL":
        if dec != "reject":
            out.append("a FAIL line carries decision 'reject', not %r" % (dec,))
        if reason not in DELTA_REASONS:
            out.append("a refusal must name one of the ten suite tokens, not %r" % (reason,))
        if idx is None:
            out.append("a refusal must name the position it stopped on")
        if head is not None or seq is not None:
            out.append("a refusal installs nothing, so it carries null head and seq")
    elif line["result"] == "ERROR":
        if dec is not None or reason is not None or idx is not None or head is not None or seq is not None:
            out.append("an ERROR line carries null decision, reason, index, head and seq")
        if line["exit"] != 3:
            out.append("an ERROR line exits 3, not %r" % (line["exit"],))
    expected_exit = {"PASS": 0, "FAIL": 1}.get(line["result"])
    if expected_exit is not None and line["exit"] != expected_exit:
        out.append("result %r exits %d, not %r" % (line["result"], expected_exit, line["exit"]))
    _error_block(line, out)
    return out


def problems_any(line):
    """Validate one line against the shape its `format` field names."""
    if isinstance(line, dict):
        fmt = line.get("format")
        if fmt == COSE_FORMAT:
            return cose_problems(line)
        if fmt == MCP_FORMAT:
            return mcp_problems(line)
        if fmt == REVOKE_FORMAT:
            return revoke_problems(line)
        if fmt == KEY_REVOKE_FORMAT:
            return key_revoke_problems(line)
        if fmt == RECEIPT_FORMAT:
            return receipt_problems(line)
        if fmt == DELTA_FORMAT:
            return delta_problems(line)
    return problems(line)


def lint(path):
    bad, total = [], 0
    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            total += 1
            try:
                line = json.loads(raw)
            except ValueError as exc:
                bad.append((n, ["not JSON: %s" % exc]))
                continue
            why = problems_any(line)
            if why:
                bad.append((n, why))
    return total, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report")
    ap.add_argument("--schema", default=SCHEMA, help="informational: the rules checked here")
    args = ap.parse_args(argv)
    if not os.path.exists(args.report):
        print("FAIL no such file: %s" % args.report)
        return 3
    total, bad = lint(args.report)
    for n, why in bad[:20]:
        print("line %d: %s" % (n, "; ".join(why)))
    if len(bad) > 20:
        print("... and %d more" % (len(bad) - 20))
    if not total:
        print("FAIL the file holds no report line")
        return 1
    if bad:
        print("\nREPORT LINT FAIL (%d of %d line(s))" % (len(bad), total))
        return 1
    print("REPORT LINT OK: %d line(s), schemas %s"
          % (total, ", ".join(os.path.basename(p) for p in SCHEMAS.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
