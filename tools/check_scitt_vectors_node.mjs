// SPDX-License-Identifier: Apache-2.0
//
// Second-language differential check of docs/upstream-package/scitt-rfc9162.
//
//     node tools/check_scitt_vectors_node.mjs
//     node tools/check_scitt_vectors_node.mjs --self-test
//
// This file shares no code with the Python builder, the Python standalone
// checker, or uibc_core: the RFC 6962 tree algebra is written again here, from
// the text, in JavaScript. It exists to answer one question that a single
// implementation cannot answer about itself — whether the corpus is defined by
// the RFC or by the habits of the program that generated it.
//
// Honest limits, stated up front: this is a *second implementation, same
// author*. It is a differential test, not an independent run, and the external
// run ledger does not count it. Only someone else's verifier does.
//
// Checks, for every vector in manifest.json:
//   * leaf digest == SHA-256(0x00 || leaf_input_hex)
//   * folding the recorded path with (tree_size, leaf_index) reproduces
//     reconstructed_root — or, when tree_size is 0, that the RFC's empty-tree
//     root MTH({}) = SHA-256() is the declared root and no fold result is
//     recorded
//   * VALID* vectors: root_true == fold result; fail-* vectors: it does not
//   * the ambiguity vectors additionally fold to the same root at alt_tree_size
//   * SHA256SUMS matches every listed file byte-for-byte
//
// --self-test additionally proves the checks above are not vacuous: it feeds
// the same checker three deliberately broken vectors (the empty-tree root
// replaced by an all-zero digest, a size-0 fold result filled in, one leaf
// digest moved) and exits 1 unless every one of them is caught. A harness that
// cannot fail its own mutations is decoration.
//
// Exit code 1 on any disagreement.

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PKG = resolve(HERE, '..', 'docs', 'upstream-package', 'scitt-rfc9162');
const SELF_TEST = process.argv.includes('--self-test');

const sha256 = (buf) => createHash('sha256').update(buf).digest();
const hex = (buf) => Buffer.from(buf).toString('hex');
const LEAF = (data) => sha256(Buffer.concat([Buffer.from([0x00]), data]));
const NODE = (l, r) => sha256(Buffer.concat([Buffer.from([0x01]), l, r]));
const EMPTY_ROOT = sha256(Buffer.alloc(0)); // RFC 6962 Section 2.1: MTH({}) = SHA-256()

// RFC 6962 Section 2.1.3.2 style inclusion verification, written out again.
function fold(leaf, index, size, path) {
  let fn = index;
  let sn = size - 1;
  let r = leaf;
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

// Returns 'valid' | 'invalid' for the vector's declared class, pushing a
// message through fail() for every disagreement.
function checkOne(id, exp, fail) {
  const leafInput = Buffer.from(exp.leaf_entry.leaf_input_hex, 'hex');
  const leaf = LEAF(leafInput);

  if (hex(leaf) !== exp.leaf_entry.digest_hex.toLowerCase()) {
    fail(`${id}: leaf digest != SHA-256(0x00 || leaf input)`);
  }

  const rootTrue = exp.root_true.toLowerCase();

  if (exp.tree_size === 0) {
    // No leaf can sit in a tree of size 0 (PATH is defined only for
    // 0 <= m < n), so the declared root must be the empty-tree constant and
    // the verdict must be a refusal.
    if (rootTrue !== hex(EMPTY_ROOT)) {
      fail(`${id}: size 0 but root_true is not MTH({})`);
    }
    if (exp.reconstructed_root !== '') {
      fail(`${id}: size 0 but a fold result is recorded`);
    }
    if (exp.result.startsWith('VALID')) {
      fail(`${id}: size 0 accepted a leaf`);
    }
    return 'invalid';
  }

  const path = exp.inclusion_path.map((h) => Buffer.from(h, 'hex'));
  const rec = fold(leaf, exp.leaf_index, exp.tree_size, path);
  if (hex(rec) !== exp.reconstructed_root.toLowerCase()) {
    fail(`${id}: fold does not reproduce reconstructed_root`);
  }

  const isValidClass = exp.result.startsWith('VALID');
  if (isValidClass !== (hex(rec) === rootTrue)) {
    fail(`${id}: result ${exp.result} contradicts the root comparison`);
  }

  if (exp.alt_tree_size !== undefined) {
    const alt = fold(leaf, exp.leaf_index, exp.alt_tree_size, path);
    if (hex(alt) !== rootTrue) {
      fail(`${id}: declared ambiguity does not reproduce at size ${exp.alt_tree_size}`);
    }
  }
  return isValidClass ? 'valid' : 'invalid';
}

function main() {
  const manifest = JSON.parse(readFileSync(join(PKG, 'manifest.json'), 'utf8'));
  const messages = [];
  let ok = true;
  const fail = (m) => { ok = false; messages.push(m); };

  let valid = 0;
  let invalid = 0;
  for (const v of manifest.vectors) {
    const exp = JSON.parse(readFileSync(join(PKG, v.dir, 'expected.json'), 'utf8'));
    const kind = checkOne(v.id, exp, fail);
    if (kind === 'valid') valid += 1; else invalid += 1;
  }

  for (const line of readFileSync(join(PKG, 'SHA256SUMS'), 'utf8').split('\n')) {
    if (!line.trim()) continue;
    const i = line.indexOf('  ');
    const digest = line.slice(0, i);
    const rel = line.slice(i + 2);
    const actual = hex(sha256(readFileSync(join(PKG, rel))));
    if (actual !== digest) fail(`checksum mismatch: ${rel}`);
  }

  if (SELF_TEST) {
    const base = JSON.parse(
      readFileSync(join(PKG, 'v1', 'fail-empty-tree', 'expected.json'), 'utf8'));
    // A valid vector, to prove the leaf-digest binding is checked at all: the
    // other three probes are about size 0, and a checker could pass them while
    // never recomputing the leaf from its input.
    const manifestVector = manifest.vectors.find((v) => v.expected_result.startsWith('VALID'));
    const validBase = JSON.parse(
      readFileSync(join(PKG, manifestVector.dir, 'expected.json'), 'utf8'));
    const probes = [
      ['empty root replaced by an all-zero digest',
       { ...base, root_true: '00'.repeat(32) }],
      ['size-0 fold result filled in',
       { ...base, reconstructed_root: base.leaf_entry.digest_hex }],
      ['size-0 vector marked VALID',
       { ...base, result: 'VALID' }],
      ['leaf digest no longer matches its leaf input',
       { ...validBase, leaf_entry: { ...validBase.leaf_entry, digest_hex: '00'.repeat(32) } }],
    ];
    for (const [label, tampered] of probes) {
      const caught = [];
      checkOne('self-test', tampered, (m) => caught.push(m));
      if (caught.length === 0) {
        ok = false;
        messages.push(`self-test FAILED to catch: ${label}`);
      } else {
        messages.push(`self-test caught: ${label} — ${caught[0]}`);
      }
    }
  }

  for (const m of messages) console.log('  ' + m);
  console.log(`  vectors: ${manifest.vectors.length} (${valid} expect-valid, ${invalid} expect-refusal)`);
  console.log(`  relay: node ${process.version}, second implementation, same author (not counted as an independent run)`);
  console.log(`VERDICT: ${ok ? 'PARITY' : 'DISCREPANCY'}`);
  return ok ? 0 : 1;
}

process.exit(main());
