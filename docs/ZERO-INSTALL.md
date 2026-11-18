# One file, no install

Every "outsider" run in this repository so far still needed the repository.
`tools/outsider_audit.py` is one command, but that command starts in a checkout
and imports `uibc_core` from it. For us that is a convenience; for someone who
was handed a package and a URL it is an obstacle, and an obstacle is where
verification quietly stops happening.

A zipapp removes it.

```
$ python3 tools/build_zipapp.py
built dist/uibc.pyz (95208 bytes)

$ cd /tmp && python3 /path/uibc.pyz verify  package/
{ "result": "PASS", "trust_level": "anchored", ... }

$ python3 /path/uibc.pyz anchor  bundle/
VERDICT: ANCHORED
```

Two commands, one file, standard library only: no pip, no network, no checkout.

| command | answers |
|---|---|
| `verify <package>` | is this package internally consistent? exit 0 only for PASS |
| `explain <package>` | the same, one line per check, with what each one read |
| `anchor <bundle>` | is this the package the publisher signed, in the state they published? |

## The part that matters is the equality

A packaged verifier that reported a different provenance than the source it was
built from would be reporting the packaging. `SPEC_ID` is a digest over every
module, so the zipapp recomputes it from inside the archive and the tests require
it to equal the checkout's:

```python
report = json.loads(zipapp_output)
self.assertEqual(report["spec_id"], spec_id())     # tests/test_zipapp.py
```

The same test runs the zipapp from an empty directory with `PYTHONPATH` stripped,
so "no install required" is executed rather than asserted. A third test feeds it
a bundle with one evidence byte changed and requires exit 1.

## What it still does not solve

- The zipapp is built by us. Someone who does not trust the build should build
  it from source - which puts them back in a checkout, and is the honest limit
  of this.
- It carries no anchor. `anchor` needs the anchor file from outside; without it,
  the command refuses, exactly like `tools/anchor_check.py`.
- It is not signed. A zipapp built by a stranger that reports the right `SPEC_ID`
  is equivalent, byte for byte, because the digest covers the code rather than
  the container - but the container itself proves nothing.

## Where this sits against the peers

`docs/PEERS.json` records what each peer ships for a stranger with no install:
sigstore and in-toto both need their own toolchain; the C2PA reference verifier
is a package install; agent-action-capsule publishes a hosted verify endpoint,
which trades the install for a network dependency and a service that has to be
trusted. A single standard-library file that runs offline and states its own
SPEC_ID is a different point on that axis, not a better one everywhere - it is
weaker on hosted convenience and stronger on "nothing between you and the bytes".

The measurement is in `docs/ZERO-INSTALL.md` because it is checkable: build it,
strip the path, run it.
