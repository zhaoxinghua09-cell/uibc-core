# Node runbook — how to close the last anchor gap

Written 2026-11-26, right after probing every machine we have, so the next
person does not repeat the search. The hook is already built (`--node`); what is
missing is a machine running Bitcoin Core. This page says what that machine
would add, what it costs, and exactly what to type when it exists.

## Probe result (2026-11-26): no node anywhere we control

| machine | checked | result |
|---|---|---|
| DESKTOP-IGJBTUB (this repo's machine) | `Get-Command bitcoind`, four common install paths, `Get-NetTCPConnection -LocalPort 8332`, `Get-Service *bitcoin*` | no binary, no listener, no service |
| 赵兴华的台式机 (home PC) | same four checks | no binary, no 8332 listener |
| 云主机 (linux VM) | `command -v bitcoind`, `ss -ltnp \| grep 8332`, `dpkg -l \| grep bitcoin` | nothing installed; 9.7 GB free on `/` |

So `node.checked=false` in both receipts is a fact about the fleet, not a coding
shortcut. Nothing on these machines claims otherwise.

## What a node adds, precisely

`--node http://user:pass@127.0.0.1:8332` makes `node_block_evidence` call three
RPCs - `getblockhash(height)`, `getblockheader(hash)`, `getblockchaininfo` - and
records: the node's block hash at that height, its `confirmations`, its
`chainwork`, its tip height and chain name. Then:

- `hash_matches_explorers` must be true, otherwise the verdict stops naming the
  disagreement instead of hiding it;
- `most_work_established` flips to true, and the first `unchecked` line (the
  "needs a node" one) comes off the receipt by itself - a test pins that
  (`test_answer_from_a_node_removes_the_most_work_caveat`);
- what does **not** change: competing branches are still not enumerated, reorg
  risk is still not modelled.

## What it costs, honestly

Bitcoin Core validates the chain it answers for: a node that has only headers is
not a node that can tell you chainwork. That means a full initial block download
(hundreds of GB of traffic and disk to validate once; pruned mode keeps ~550 MiB
of blocks after that but does not skip the download). On a typical home link this
is days, not minutes. Plan it as an environment project, not a task.

## Steps once the node is up

1. `bitcoind -daemon -server -rpcuser=uibc -rpcpassword=<secret> -prune=550`
   (add `-rpcbind` / `-rpcallowip` only if the caller is another machine).
2. Wait for `getblockchaininfo.initialblockdownload == false`.
3. Regenerate the chain receipt **with** the node, so the evidence and the claim
   move together:
   ```
   python tools/ots_block_crosscheck.py \
     --proof tests/fixtures/anchor/ots_head.ots \
     --chain --node http://uibc:<secret>@127.0.0.1:8332 \
     --chain-out docs/anchor-ots-chain-977449.json \
     --out docs/anchor-ots-block-977449.json
   ```
4. Full verdict:
   ```
   python tools/ots_full_verify.py \
     --file tests/fixtures/anchor/anchored_head.json \
     --proof tests/fixtures/anchor/ots_head.ots \
     --tsa-token tests/fixtures/anchor/freetsa.tsr \
     --rekor-entry tests/fixtures/anchor/rekor_entry.json
   ```
   Expected: `verdict=FULL_CHAIN_OF_EVIDENCE_VERIFIED`,
   `most_work_established: true`, and the `unchecked` list down to the two lines
   a node cannot answer.
5. Tests: `python -m unittest tests.test_ots_node_evidence tests.test_ots_full_verify`
   - the stub suite must stay green too; it is what proves the wiring without a node.

## Two things not to do

- **Do not hand-write `node.checked=true`** into a receipt. The field means "a
  node answered at this time from this chain"; a fabricated one is worse than the
  honest `false` we ship today.
- **Do not point `--node` at someone else's public node.** A remote RPC endpoint
  is one more server to trust, which is the thing this whole layer exists to
  avoid. If it is not on a machine you administer, it does not count.

## What would still be open after this

| question | after a node |
|---|---|
| most-work chain (this node's view) | answered, dated, recorded |
| two independent nodes agreeing | not covered - the tool takes one node; a second would be a real improvement |
| competing branches / reorg risk | still open; needs a node plus a stated attacker model |
