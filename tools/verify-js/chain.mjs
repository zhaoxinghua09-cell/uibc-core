// The line of anchors, judged by the second implementation.
//
// `anchor_chain.py` decides CHAIN OK / BROKEN / STALE with Python. This file
// decides the same question with node:crypto and no shared code, because a
// check only one implementation can perform is a check only one machine can
// disagree with - and disagreement is how bugs get found.
//
// The rule, in six lines of prose:
//   seq counts from 1, no gaps, no repeats;
//   seq 1 has no predecessor;
//   every later seq carries sha256(JCS(agent_id, key_id, pubkey_b64, head))
//   of the anchor before it - so swapping an anchor in place rewrites a digest
//   somebody downstream is already holding;
//   a chain shorter than what the caller knows exists means anchors are being
//   withheld, which is STALE rather than absent.
//
// What this does not do: judge the packages themselves (that is anchor.mjs) or
// the timestamps (that is anchor_check.py). One question, one tool.
//
// Usage:  node tools/verify-js/chain.mjs <anchor-dir> [--expect-latest N]
// Exit:   0 CHAIN OK   4 CHAIN BROKEN   5 STALE

import { createHash } from "node:crypto";
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

const sha256 = (s) => createHash("sha256").update(s).digest("hex");

// RFC 8785 (JCS). Deliberately the same six lines as anchor.mjs: a shared
// helper would be one more thing that could drift, and the rule is tiny.
function jcs(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
}

function anchorDigest(a) {
  const core = {
    agent_id: a.agent_id ?? null,
    key_id: a.key_id ?? null,
    pubkey_b64: a.pubkey_b64 ?? null,
    checkpoint_head: a.checkpoint_head ?? null,
  };
  return sha256(jcs(core));
}

function loadAnchors(dir) {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    if (!name.endsWith(".json")) continue;
    const p = join(dir, name);
    try { if (!statSync(p).isFile()) continue; } catch { continue; }
    let a;
    try { a = JSON.parse(readFileSync(p, "utf8")); } catch { continue; }
    if (!a || typeof a !== "object" || !("checkpoint_head" in a)) continue;
    out.push({ file: name, a });
  }
  return out;
}

function main() {
  const argv = process.argv.slice(2);
  let dir = null;
  let expectLatest = null;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--expect-latest") { expectLatest = Number(argv[i + 1]); i += 1; }
    else if (dir === null) dir = argv[i];
  }
  if (dir === null || !existsSync(dir)) {
    console.error("usage: node tools/verify-js/chain.mjs <anchor-dir> [--expect-latest N]");
    return 4;
  }

  const entries = loadAnchors(dir);
  const problems = [];
  if (entries.length === 0) problems.push("no anchor files found");

  const bySeq = new Map();
  for (const e of entries) {
    const seq = e.a.seq;
    if (!Number.isInteger(seq) || seq < 1) {
      problems.push(e.file + ": seq is missing or not a positive integer " +
                    "(an anchor without a position cannot be ordered)");
      continue;
    }
    if (bySeq.has(seq)) {
      problems.push("seq " + seq + " appears twice: " + bySeq.get(seq).file +
                    " and " + e.file + " - a replayed anchor");
      continue;
    }
    bySeq.set(seq, e);
  }
  if (problems.length) {
    console.log("VERDICT: CHAIN BROKEN");
    for (const p of problems) console.log("  - " + p);
    return 4;
  }

  const ordered = [...bySeq.keys()].sort((x, y) => x - y);
  let expect = 1;
  for (const seq of ordered) {
    const e = bySeq.get(seq);
    if (seq !== expect) {
      problems.push("seq " + expect + " is missing: the chain has a gap between " +
                    (expect - 1) + " and " + seq);
      break;
    }
    const prev = e.a.prev_anchor_digest;
    if (seq === 1) {
      if (prev !== null && prev !== undefined) {
        problems.push("seq 1 declares prev_anchor_digest " + JSON.stringify(prev) +
                      " - the first anchor has nothing before it");
        break;
      }
    } else {
      const before = bySeq.get(seq - 1).a;
      if (prev !== anchorDigest(before)) {
        problems.push("seq " + seq + " declares prev_anchor_digest " +
                      String(prev || "<null>").slice(0, 16) + "... but seq " + (seq - 1) +
                      " is " + anchorDigest(before).slice(0, 16) + "... - the chain was " +
                      "rewritten, or an anchor was swapped in place");
        break;
      }
    }
    expect += 1;
  }

  const latest = ordered.length ? ordered[ordered.length - 1] : 0;
  let stale = false;
  if (!problems.length && expectLatest !== null && latest < expectLatest) {
    stale = true;
    problems.push("chain stops at seq " + latest + " but the caller already knows of seq " +
                  expectLatest + " - newer anchors are missing, not merely absent");
  }

  console.log("VERDICT: " + (problems.length ? (stale ? "STALE" : "CHAIN BROKEN") : "CHAIN OK"));
  console.log("anchors: " + ordered.length + " (seq 1.." + latest + ")");
  for (const seq of ordered) {
    const e = bySeq.get(seq);
    console.log("  " + String(seq).padStart(2) + "  " + e.file + "  head " +
                String(e.a.checkpoint_head || "").slice(0, 18));
  }
  for (const p of problems) console.log("  - " + p);
  console.log("implementation: verify-js (independent of uibc-core)");
  return problems.length ? (stale ? 5 : 4) : 0;
}

process.exit(main());
