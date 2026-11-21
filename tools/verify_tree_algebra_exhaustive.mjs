// SPDX-License-Identifier: Apache-2.0
//
// Second-language sweep of the same instances the Python sweep generated:
//
//     node tools/verify_tree_algebra_exhaustive.mjs inst.json
//
// The instances file is produced by
//     python tools/verify_tree_algebra_exhaustive.py --max-size 64 --dump inst.json
//
// This file re-derives every root from the recorded bytes alone — the leaf inputs
// are not in the file, so a pass here means the recorded path or proof is
// self-sufficient, not that a shared generator agreed with itself. The algebra is
// written again here, from the text, sharing no code with the Python side.
//
// Exit code 1 on any disagreement.

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const sha256 = (buf) => createHash('sha256').update(buf).digest();
const hex = (buf) => Buffer.from(buf).toString('hex');
const NODE = (l, r) => sha256(Buffer.concat([Buffer.from([0x01]), l, r]));

// Inclusion: the leaf is unknown here, so start from the leaf digest recorded in
// the instance. A verifier that starts from the digest and still reaches the
// recorded root has confirmed the path; the leaf-input binding is checked
// separately by the corpus checker, which does have the leaf inputs.
function foldFromDigest(leafDigest, index, size, path) {
  let fn = index;
  let sn = size - 1;
  let r = leafDigest;
  for (const p of path) {
    if ((fn & 1) === 1 || fn === sn) {
      r = NODE(p, r);
      while ((fn & 1) === 0 && fn !== 0) {
        fn >>>= 1;
        sn >>>= 1;
      }
    } else {
      r = NODE(r, p);
    }
    fn >>>= 1;
    sn >>>= 1;
  }
  return r;
}

function split(n) {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

function rebuildConsistency(m, n, oldRoot, proof) {
  if (m < 1 || n < m) return null;
  if (m === n) return proof.length === 0 ? [oldRoot, oldRoot] : null;

  const walk = (a, b, pos, seeded) => {
    if (a === b) {
      if (seeded) return [oldRoot, oldRoot, pos];
      if (pos >= proof.length) return null;
      return [proof[pos], proof[pos], pos + 1];
    }
    const k = split(b);
    if (a <= k) {
      const res = walk(a, k, pos, seeded);
      if (res === null || res[2] >= proof.length) return null;
      return [res[0], NODE(res[1], proof[res[2]]), res[2] + 1];
    }
    const res = walk(a - k, b - k, pos, false);
    if (res === null || res[2] >= proof.length) return null;
    return [NODE(proof[res[2]], res[0]), NODE(proof[res[2]], res[1]), res[2] + 1];
  };

  const res = walk(m, n, 0, true);
  if (res === null || res[2] !== proof.length) return null;
  return [res[0], res[1]];
}

function main() {
  const pathArg = process.argv[2];
  if (!pathArg) {
    console.log('usage: node tools/verify_tree_algebra_exhaustive.mjs <instances.json>');
    return 2;
  }
  const instances = JSON.parse(readFileSync(pathArg, 'utf8'));
  let inc = 0;
  let cons = 0;
  const bad = [];

  for (const it of instances) {
    if (it.kind === 'inclusion') {
      inc += 1;
      // The sweep instance records the leaf digest under `path` index 0? No — it
      // records the proof only, so the leaf digest is recomputed from the stored
      // leaf index by the Python side; here the root must come out of the path
      // and the digest that the Python side recorded as the first element.
      const leaf = Buffer.from(it.leaf_digest, 'hex');
      const got = foldFromDigest(
        leaf, it.index, it.size, it.path.map((h) => Buffer.from(h, 'hex')));
      if (hex(got) !== it.root) bad.push(`inclusion size=${it.size} index=${it.index}`);
    } else {
      cons += 1;
      const rec = rebuildConsistency(
        it.m, it.n, Buffer.from(it.old_root, 'hex'),
        it.proof.map((h) => Buffer.from(h, 'hex')));
      if (rec === null
          || hex(rec[0]) !== it.old_root
          || hex(rec[1]) !== it.new_root) {
        bad.push(`consistency m=${it.m} n=${it.n}`);
      }
    }
  }

  console.log(`inclusion instances  : ${inc}`);
  console.log(`consistency instances: ${cons}`);
  console.log(`disagreements        : ${bad.length}`);
  for (const b of bad.slice(0, 20)) console.log('  ' + b);
  console.log(`VERDICT: ${bad.length === 0 ? 'SWEEP-AGREES' : 'SWEEP-DISAGREES'}`);
  return bad.length === 0 ? 0 : 1;
}

process.exit(main());
