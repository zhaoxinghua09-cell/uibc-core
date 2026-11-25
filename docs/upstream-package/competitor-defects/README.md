# A competitor's "reject" that does not come from the numbers (v0.38.0)

Three negative vectors from `probityai/agent-evidence-vectors` (commit `22764551`,
release `v0.38.0`) each declare an empty tree **and** carry a Merkle root that is not
the RFC 6962 root of an empty tree:

| vector | says | carries | RFC 6962 §2.1 says a 0-leaf tree has |
|---|---|---|---|
| `INC-N-size-zero` | `tree_size: 0`, `index: 0`, `proof: []` | root `5488b5f1…ed1f6` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `CON-N-old-size-zero` | `old_size: 0` | old_root `b3d9166b…74c30` | same constant |
| `TOK-N-tree-size-zero` | `poc_claims.tree_size: 0` | merkle_root `5604d10f…93703` | same constant |

All three publish `result: reject`. The problem is not that they reject - it is that
the reject is **forced by the broken constant**, so none of the three can show
whether their verifier handles an empty tree at all. A reader cannot distinguish
"rejected the arithmetic" from "refused an input that contradicts itself".

`tools/check_competitor_vectors.py` judges each file **without reading their verifier**:
it recomputes the one constant the RFC pinpoints, and reports `declared_code`
vs `forced_code`.

```
$ python tools/check_competitor_vectors.py \
    --dir docs/upstream-package/competitor-defects/v0.38.0 \
    --dir docs/upstream-package/competitor-defects/v0.38.0-counter
CON-N-old-size-zero.json     consistency declared=not-consistent  forced=root-contradicts-size-zero   agrees=False
INC-N-size-zero.json         inclusion   declared=not-included    forced=not-included,root-contradicts-size-zero agrees=False
TOK-N-tree-size-zero.json    token       declared=schema          forced=root-contradicts-size-zero   agrees=False
CON-N-size-zero-counter.json consistency declared=schema          forced=schema                        agrees=True
INC-N-size-zero-counter.json inclusion   declared=not-included    forced=not-included                  agrees=True
TOK-N-tree-size-zero-counter.json token   declared=schema          forced=schema                        agrees=True
VERDICT: 3/6 vectors where the data forces the published code
```

The `v0.38.0-counter/` twins are ours: same shapes, correct constants, and a reject
that a structural rule forces (leaf count, proof shape, value type) instead of a
broken number. They exist so the comparison has a control - without them "3/6" would
only say "their files are odd", not "our rule agrees with well-formed files".

## What this shows, and what it does not

Shows: the three vectors are malformed by their own data, and the published code is
not the code the arithmetic forces. Anyone can reproduce it offline with this repo's
tool; the upstream bytes are vendored with their sha256 in `SHA256SUMS.json`.

Does not show: that their implementation is wrong, or that it accepts an empty-tree
proof it should reject. To say that, one would have to run their verifier and read
its code - neither is done here. The failure is in the **fixture**, and the fixture
is what a consumer of that corpus would test against.

Does not show: anything about their `INDEPENDENT-RUNS.json`, where eight runs are all
labelled `independent`. That is a separate claim about provenance, not arithmetic.

## Why vendored bytes instead of links

The upstream corpus moves (v0.37.1 → v0.38.0 in two days). A finding that only
exists as a URL rots. The three files here are byte-for-byte copies at commit
`22764551`; `SHA256SUMS.json` records the sha256 and byte count of each, plus the
counter-vectors, so a reader can re-fetch upstream and compare without trusting us.
