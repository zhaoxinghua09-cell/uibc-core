# UIBC conformance corpus — run it yourself

This archive contains 36 packages: a correct one, and 35 that each had exactly
one thing broken. Your verifier has to accept the correct one and refuse the
rest, naming at least one check that this manifest expects. Refusing everything
scores nothing — the accept cases fail.

Nothing here needs our repository.

## Run it (two commands)

```bash
python -m pip install uibc-core==0.4.1     # the reference verifier
python run.py
```

Expected tail: `strict 36/36`.

Testing a different implementation:

```bash
python run.py --verify "/path/to/your/verifier {pkg}"   # {pkg} = package path
```

Your verifier must print JSON on stdout with `result` in
`PASS | FAIL | INCONCLUSIVE` and a `checks` list of `{"id": ..., "result": ...}`
using the same check ids as the manifest (`S1`–`S18`). Exit code is ignored
when JSON parses, so a non-zero exit on FAIL is fine.

`python run.py` writes `receipt.json`: the command, the time, the Python and
platform, the verifier version, a hash of the manifest, and every case's
verdict. Publish it if you want your run to be citable, and fill in `--run-by`.

**If the verifier is missing, no receipt is written.** When not one case produces
parseable JSON, `run.py` exits 3, prints the interpreter it used and the install
command, and stops. A receipt saying `0/36` in that situation would be a lie that
looks like evidence: it is indistinguishable from "these packages all fail", and
someone could publish it in good faith. Exit codes: `0` all cases behaved, `1`
some case did not, `3` no verifier output at all (setup problem, not a result).

## What a pass means — and what it does not

It means: on this machine, with this corpus, your verifier refused the 35 broken
packages naming an expected check each, and accepted the correct one.

It does **not** mean your verifier is secure, complete, or audited. It is not a
certification. The corpus, the manifest and `run.py` are all written by the
project: this is a *test of the verifier against our expectations*, not an
independent audit of either side. A run here is also not a reproduction of
anyone else's result unless the same archive hash was used.

`expected.json` lists what each case requires, so you can disagree with a case
and say why — a case that is wrong is a finding in our favour to fix, not a
reason to tune your verifier until it matches.
