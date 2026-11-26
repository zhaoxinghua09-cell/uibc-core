# Registry census, all 282 methods

Facts: current. Regenerate with `python tools/registry_census.py --write`, verify with `--check`.

Everyone quotes "282 DID methods". Almost nobody has counted what the entries themselves contain.
This counts four things per entry, and nothing else: the verifiable data registry field, the
specification URL, the kind of account hosting that URL, and whether the example identifier
agrees with the method's own name.

| what the entry says | count | share |
|---|---|---|
| entries in `methods/` | 282 | 100% |
| verifiable data registry **empty** | 10 | 3.5% |
| verifiable data registry filled | 272 | 96.5% |
| no specification URL at all | 3 | 1.1% |
| specification hosted on GitHub | 187 | 66.3% |
| — of those, **personal account** | 53 | 18.8% |
| — of those, organisation account | 129 | 45.7% |
| specification on some other host | 92 | 32.6% |
| example identifier disagrees with the method name | 0 | 0.0% |
| entry carries a contact name | 276 | 97.9% |
| status `registered` | 279 | 98.9% |
| status `deprecated` | 3 | 1.1% |

The entries with no verifiable data registry are: `agent`, `ciphora`, `content`, `ctid`, `dsrv`, `hpo`, `iamx`, `os`, `valyu`, `vtid`.
The entries with no specification URL are: `dom`, `tls`, `uport`.
The deprecated ones are: `fairx`, `tangle`, `uport`.

## What this number means for a resolver

An empty `verifiableDataRegistry` means the entry does not say where identifiers live. That is
not the same as "no registry exists" — it means a reader cannot check the method's own account of
itself, and a resolver built from it is resolving against something the entry never described.

Specifications hosted on a personal account are checkable but not durable: the account can
disappear, the repository can be force-pushed, and the registry keeps pointing at it. The census
records which ones, so the question can be asked by name instead of in aggregate.

## What this census does not claim

what the registry entries say, nothing about whether a method resolves, is operated, or is authorised. An empty verifiableDataRegistry is a gap in the entry, not evidence that no registry exists; a personal account hosting a specification is a hosting fact, not a claim about who wrote it.

Nor does it claim any of the 282 methods can be resolved: the registry has no endpoint field.
