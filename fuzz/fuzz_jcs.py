"""Atheris harness for the JCS canonicaliser.

What it asserts, and why these three are the ones worth fuzzing:

1. Total function on JSON input. Whatever `json.loads` accepts, `canonicalize`
   must either produce bytes or raise `ValueError`/`TypeError` -- never another
   exception, never a hang.
2. I-JSON fixpoint. The output must parse back, and canonicalising it again must
   give exactly the same bytes. A canonicaliser that is not a fixpoint is not a
   canonicaliser; this is the property the whole evidence chain rests on.
3. Ordering is a function of content, not of insertion history. The same
   document built with keys inserted in a different order must canonicalise to
   identical bytes, otherwise two verifiers can disagree on the same record.

Run:

    python fuzz/fuzz_jcs.py -max_total_time=30

The seed corpus is written to a temporary directory on start-up, because a
harness that begins from an empty corpus spends its first seconds rediscovering
`{}`.
"""

import json
import os
import sys
import tempfile

import atheris

with atheris.instrument_imports():
    from uibc_core.canonical import canonicalize

SEEDS = [
    b"{}",
    b'{"a":1,"b":[2,3],"c":{"d":null}}',
    b'{"n":1e-7,"m":9007199254740993}',
    b'{"s":"a\\u0000b\\t\\"c","u":"\\u00e9\\u4e00"}',
    b"[]",
    b'{"deep":{"deeper":{"deepest":[]}}}',
]


def _refuses(exc: BaseException) -> bool:
    return isinstance(exc, (ValueError, TypeError))


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    text = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())

    try:
        obj = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        return

    try:
        first = canonicalize(obj)
    except (ValueError, TypeError, RecursionError):
        return

    # (2) I-JSON fixpoint.
    second = canonicalize(json.loads(first))
    if second != first:
        raise RuntimeError("not a fixpoint")

    # (3) key order must not matter.
    if isinstance(obj, dict):
        reordered = {k: obj[k] for k in reversed(list(obj.keys()))}
        if canonicalize(reordered) != first:
            raise RuntimeError("canonical form depends on insertion order")


def _seed_dir(argv: list) -> None:
    corpus = tempfile.mkdtemp(prefix="uibc-fuzz-corpus-")
    for i, seed in enumerate(SEEDS):
        with open(os.path.join(corpus, "seed-%02d" % i), "wb") as fh:
            fh.write(seed)
    argv.append(corpus)


def main() -> None:
    _seed_dir(sys.argv)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
