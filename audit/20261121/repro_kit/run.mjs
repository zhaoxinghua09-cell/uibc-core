#!/usr/bin/env node
/**
 * XLGD 一致性向量的第二实现（Node.js / 零依赖）
 *
 * 目的：证明这套向量是**语言中立**的——同一份 vectors.json，
 *       用完全独立的代码库、不同语言，必须得到完全相同的判定。
 *
 * 诚实声明：本实现与 run.py 由同一作者编写，因此**不构成第三方验证**，
 *           也不构成独立实现。它只证明"跨语言可达性"。
 *
 * 用法：node run.mjs [--out path]
 */
import { createHash, createHmac } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const KEYS = { 'key-A': 'secret-A', 'key-B': 'secret-B', 'key-EVIL': 'secret-EVIL' };
const SUBJECT_REGISTRY = { 'skill-x': 'key-A', 'skill-y': 'key-B' };
const NOW = Date.parse('2026-11-19T09:00:00+00:00');

/** 规范化 JSON：递归排序键 + 紧凑分隔符（与规范 §Rule semantics 一致） */
function canon(v) {
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  if (v && typeof v === 'object') {
    const keys = Object.keys(v).sort();
    return '{' + keys.map((k) => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
  }
  return JSON.stringify(v);
}
const sha256 = (v) => createHash('sha256').update(canon(v), 'utf8').digest('hex');
const mac = (body, keyId) =>
  createHmac('sha256', KEYS[keyId]).update(canon(body), 'utf8').digest('hex');

function checkBinding(v) {
  const body = v.evidence.body;
  if (body.subject !== v.subject) return false;
  const allowed = SUBJECT_REGISTRY[body.subject];
  if (!allowed || v.evidence.key_id !== allowed) return false;
  if (mac(body, allowed) !== v.evidence.mac) return false;
  return sha256(body) === v.registered_digest;
}

function checkUsable(v) {
  if (!['AUTHORIZED', 'MONITORED'].includes(v.state)) return false;
  if (!v.expires_at) return false;
  return Date.parse(v.expires_at) > NOW;
}

function checkTransition(v) {
  if (v.to === 'AUTHORIZED') {
    const a = v.authorization;
    if (!a) return false;
    for (const k of ['subject', 'scope', 'expires_at']) if (!(k in a)) return false;
  }
  return !v.score_only;
}

const COMPAT = {
  'uibc/0.4.0|rules/2': ['engine/2', 'engine/3'],
  'uibc/0.3.x|rules/1': ['engine/1'],
  'uibc/0.3.x|rules/2': ['engine/2'],
  'uibc/0.2.x|rules/1': ['engine/1'],
};
function checkCompat(v) {
  const k = `${v.evidence_version}|${v.rule_version}`;
  return (COMPAT[k] || []).includes(v.engine);
}

function checkRevocation(v) {
  const targets = new Set(v.revocations.map((r) => r.target));
  const cascaded = new Set(v.revocations.flatMap((r) => r.propagates_to || []));
  return !(targets.has(v.object) || cascaded.has(v.object));
}

function checkExchange(v) {
  if (v.pinned_fp !== v.identity_fp) return false;
  if (!v.compat.some(([r, e]) => r === v.rule_version && e === v.engine_version)) return false;
  if (Date.parse(v.expires_at) <= NOW) return false;
  if ([...v.requested_scope].some((s) => !v.granted_scope.includes(s))) return false;
  const snap = v.snapshot;
  if (!snap) return false;
  if (snap.age_hours > (v.max_snapshot_age_hours ?? 6)) return false;
  return !snap.revoked.includes(v.entity);
}

/** 检测原始文本中的重复键：不同解析器会取不同值，验签必须拒绝歧义输入 */
function hasDupKeys(raw) {
  const stack = [];
  let i = 0;
  let dup = false;
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === '{') stack.push(new Set());
    else if (ch === '}') stack.pop();
    else if (ch === '"') {
      let j = i + 1;
      while (j < raw.length && raw[j] !== '"') j += raw[j] === '\\' ? 2 : 1;
      const token = raw.slice(i + 1, j);
      if (stack.length && raw[j + 1] === ':') {
        const top = stack[stack.length - 1];
        if (top.has(token)) dup = true;
        top.add(token);
      }
      i = j;
    }
    i += 1;
  }
  return dup;
}

function checkCanon(v) {
  switch (v.case) {
    case 'duplicate_key':
      return !hasDupKeys(v.raw);
    case 'nfc':
      // Node 的 ICU 归一化必须与 Python 一致：两边都归到 NFC 再比较
      return v.registered.normalize('NFC') === v.presented.normalize('NFC');
    case 'nan':
      return !/(?<![\w"])(NaN|-?Infinity)(?![\w"])/.test(v.raw);
    case 'bigint':
      return BigInt(v.value) <= BigInt(v.max_safe) && BigInt(v.value) >= -BigInt(v.max_safe);
    case 'float':
      return v.presented === v.canonical;
    default:
      throw new Error(`unknown canon case ${v.case}`);
  }
}

function checkNegotiate(v) {
  return v.supported.includes(v.peer);
}

function checkRevmerge(v) {
  const union = new Set(v.sources.flatMap((s) => s.revoked));
  return !union.has(v.object);
}

function checkSkew(v) {
  if (v.age_minutes < -v.tolerance_minutes) return false;
  return v.age_minutes <= v.max_age_minutes;
}

const CHECKS = {
  binding: checkBinding,
  usable: checkUsable,
  transition: checkTransition,
  compat: checkCompat,
  revocation: checkRevocation,
  exchange: checkExchange,
  canon: checkCanon,
  negotiate: checkNegotiate,
  revmerge: checkRevmerge,
  skew: checkSkew,
};

const argv = process.argv.slice(2);
const outIdx = argv.indexOf('--out');
const outPath = outIdx >= 0 ? argv[outIdx + 1] : join(HERE, 'external_node_result_node.json');

const vectors = JSON.parse(readFileSync(join(HERE, 'vectors.json'), 'utf8'));
const results = [];
const mismatches = [];
for (const v of vectors) {
  const fn = CHECKS[v.check];
  if (!fn) throw new Error(`no check for ${v.check} (${v.id})`);
  const actual = fn(v) ? 'ALLOW' : 'REJECT';
  const match = actual === v.expected;
  results.push({ id: v.id, expected: v.expected, actual, match });
  if (!match) mismatches.push({ id: v.id, expected: v.expected, actual });
}

const out = {
  kit_version: 'xlgd-trust-repro/1',
  implementation: 'node-reference (same author as run.py — NOT third-party)',
  reproducer: process.env.REPRODUCER || 'unknown',
  affiliation: process.env.AFFILIATION || 'unknown',
  conflict_declared: process.env.CONFLICT_DECLARED || 'unknown',
  environment: {
    runtime: `node ${process.versions.node}`,
    os: `${os.platform()} ${os.release()}`,
    machine: os.arch(),
  },
  started_at: new Date().toISOString(),
  vectors_total: vectors.length,
  matched: results.length - mismatches.length,
  mismatches,
  results,
};
writeFileSync(outPath, JSON.stringify(out, null, 2), 'utf8');
console.log(`vectors=${vectors.length} matched=${out.matched} mismatches=${mismatches.length}`);
console.log(`result written to ${outPath}`);
process.exit(mismatches.length === 0 ? 0 : 1);
