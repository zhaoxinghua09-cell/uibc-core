#!/usr/bin/env node
// An independent structural verifier for UIBC packages, written in JavaScript
// with no dependency on uibc-core and no third-party packages.
//
// Covered here: package structure (S1), identity consistency (S2), evidence
// integrity (S4), evidence root (S5), index metadata shape (S7), strict
// serialization (S11), timestamp and identifier strictness (S12).
//
// Not covered, on purpose: seal signatures (S6), Merkle inclusion proofs
// (S13), external timestamps (S16), the receipt chain (S17), policy artefact
// resolution (S18), closure declaration (S10) and the package checkpoint (S8).
// Those need Ed25519, RFC 3161 and the v1.1 tree. A checker that claimed them
// without implementing them would be worse than one that says it cannot.
// Because it cannot attest signatures, it never returns PASS.
//
// Usage:  node tools/verify-js/verify.mjs <package-dir>

import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, normalize, sep } from "node:path";

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

// --- RFC 8785 (JCS) -------------------------------------------------------
function jcs(value) {
  if (value === null) return "null";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("JCS: non-finite number");
    if (!Number.isSafeInteger(value) && Number.isInteger(value)) {
      throw new Error("JCS: integer outside the ECMAScript safe range");
    }
    return Object.is(value, -0) ? "0" : JSON.stringify(value);
  }
  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
  }
  throw new Error("JCS: unsupported type " + typeof value);
}

const canonicalBytes = (value) => Buffer.from(jcs(value), "utf8");

// --- duplicate member detection -------------------------------------------
// JSON.parse keeps the last duplicate silently, so a document with a repeated
// key survives parsing. Scanning the raw text is the only way to see it.
function duplicateKeys(raw) {
  const stack = [];
  const hits = [];
  let i = 0;
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === "{") { stack.push({ keys: new Set(), expectKey: true }); i++; continue; }
    if (ch === "}") { stack.pop(); i++; continue; }
    if (ch === "[") { stack.push(null); i++; continue; }
    if (ch === "]") { stack.pop(); i++; continue; }
    if (ch === "\"") {
      let j = i + 1;
      while (j < raw.length) {
        if (raw[j] === "\\") { j += 2; continue; }
        if (raw[j] === "\"") break;
        j++;
      }
      const token = raw.slice(i, j + 1);
      const top = stack[stack.length - 1];
      if (top && top.expectKey) {
        const key = JSON.parse(token);
        if (top.keys.has(key)) hits.push(key);
        top.keys.add(key);
        top.expectKey = false;
      }
      i = j + 1;
      continue;
    }
    if (ch === "," && stack.length) {
      const top = stack[stack.length - 1];
      if (top) top.expectKey = true;
    }
    i++;
  }
  return hits;
}

// --- helpers --------------------------------------------------------------
const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

function listFiles(root, prefix = "") {
  const out = [];
  const dir = prefix ? join(root, prefix) : root;
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const rel = prefix ? prefix + "/" + name : name;
    if (statSync(join(root, rel)).isDirectory()) out.push(...listFiles(root, rel));
    else out.push(rel);
  }
  return out;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

function realDate(text) {
  if (typeof text !== "string" || !STAMP.test(text)) return false;
  if (Number.isNaN(Date.parse(text))) return false;
  const d = new Date(Date.parse(text));
  const [y, mo, da] = text.slice(0, 10).split("-").map(Number);
  return d.getUTCFullYear() === y && d.getUTCMonth() + 1 === mo && d.getUTCDate() === da;
}

// Files that are declared structurally rather than in the evidence index.
const STRUCTURAL = new Set(["evidence/index.json", "evidence/merkle.json",
                            "evidence/chain.json", "evidence/anchors.json",
                            "evidence/policies.json"]);

// --- checks ---------------------------------------------------------------
function verify(pkg) {
  const checks = [];
  const note = (id, name, ok, detail) =>
    checks.push({ id, name, result: ok ? "PASS" : "FAIL", detail });

  // S1 package structure, including files nobody declared
  {
    const problems = [];
    const required = ["manifest.json", "identity.json", "lifecycle.json",
                      "evidence/index.json"];
    for (const p of required) {
      if (!existsSync(join(pkg, p))) problems.push("missing: " + p);
    }
    let manifest = null;
    try { manifest = readJson(join(pkg, "manifest.json")); } catch { problems.push("manifest is not JSON"); }
    if (manifest && (typeof manifest.schema !== "string" || !manifest.schema.startsWith("uibc-core/"))) {
      problems.push("manifest.schema is not a uibc-core schema");
    }
    let declared = new Set();
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      declared = new Set((index.entries || []).map((e) => "evidence/" + String(e.path)));
    } catch { /* S4 reports the index */ }
    for (const rel of listFiles(pkg)) {
      if (rel === "manifest.json" || rel === "identity.json" || rel === "lifecycle.json") continue;
      if (rel.startsWith("signatures/")) continue;
      if (STRUCTURAL.has(rel) || rel.startsWith("evidence/policies/")) continue;
      // Lock and backup files are how a writer protects a package, not
      // evidence. Anything hidden is machinery.
      if (rel.split("/").pop().startsWith(".")) continue;
      if (!declared.has(rel)) problems.push("undeclared file: " + rel);
    }
    note("S1", "package structure", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S2 identity consistency
  {
    let ok = false, detail = "missing files";
    try {
      const id = readJson(join(pkg, "identity.json"));
      const manifest = readJson(join(pkg, "manifest.json"));
      ok = !!id.agent_id && id.agent_id === manifest.agent_id &&
           typeof id.owner === "string" && id.owner.length > 0;
      detail = ok ? "ok" : "agent_id or owner does not line up with the manifest";
    } catch { /* detail already set */ }
    note("S2", "identity consistency", ok, detail);
  }

  // S4 evidence integrity
  const hashes = [];
  {
    const problems = [];
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      const entries = index.entries || [];
      if (!entries.length) problems.push("evidence index has no entries");
      for (const e of entries) {
        if (typeof e.path !== "string") { problems.push("entry without a path"); continue; }
        const rel = normalize("evidence/" + e.path);
        if (rel.startsWith("..") || rel.includes(".." + sep)) {
          problems.push("path escapes the package: " + e.path); continue;
        }
        let body = null;
        try { body = readFileSync(join(pkg, rel)); }
        catch { problems.push("missing evidence file: " + e.path); continue; }
        const got = sha256(body);
        if (got !== e.content_hash) problems.push("content hash mismatch: " + e.path);
        else hashes.push(got);
      }
    } catch (err) { problems.push("unreadable index: " + err.message); }
    note("S4", "evidence integrity", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S5 evidence root
  {
    let ok = false, detail = "no hashes to root";
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      const root = sha256(canonicalBytes(hashes.slice().sort()));
      ok = root === manifest.evidence_root;
      detail = ok ? "ok" : "evidence_root does not re-derive: computed " + root.slice(0, 12);
    } catch (err) { detail = err.message; }
    note("S5", "evidence root", ok, detail);
  }

  // S7 evidence index metadata
  {
    const problems = [];
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      for (const e of (index.entries || [])) {
        if (!UUID.test(String(e.evidence_id))) problems.push("evidence_id is not a UUID");
        if (!["ACTION", "OUTPUT", "DECISION"].includes(e.type)) {
          problems.push("unknown evidence type: " + e.type);
        }
        if (!realDate(String(e.created_at))) problems.push("created_at is not a real ISO-8601 Z time");
        if (typeof e.content_hash !== "string" || e.content_hash.length !== 64) {
          problems.push("content_hash is not a sha256 hex digest");
        }
      }
    } catch (err) { problems.push("unreadable index: " + err.message); }
    note("S7", "evidence index metadata", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S11 strict serialization, in the same sense the Python verifier means it:
  // duplicate member names, raw control characters inside a document, bytes
  // that are not valid UTF-8. All of these are invisible to JSON.parse and
  // survive it, which is exactly the two-reader split the check exists for.
  {
    const problems = [];
    const files = ["manifest.json", "identity.json", "lifecycle.json",
                   "evidence/index.json"];
    for (const rel of files) {
      const path = join(pkg, rel);
      if (!existsSync(path)) continue;
      const buf = readFileSync(path);
      const text = buf.toString("utf8");
      if (Buffer.from(text, "utf8").length !== buf.length || text.includes("\uFFFD")) {
        problems.push(rel + ": bytes are not valid UTF-8");
      }
      const dup = duplicateKeys(text);
      if (dup.length) problems.push(rel + ": repeated member name " + dup[0]);
      const ctrl = [...text].find((ch) => ch.codePointAt(0) < 0x20 &&
                     !("\t\n\r".includes(ch)));
      if (ctrl) problems.push(rel + ": unescaped control character");
    }
    note("S11", "strict serialization", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S7 continued: the index METADATA digest must match the one carried in the
  // manifest. Content hashes are already bound by S4 and S5; what was left
  // unbound was path, declared type and the free-text note -- a forged
  // "reviewed and approved" note passes every hash check without this.
  {
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      const index = readJson(join(pkg, "evidence/index.json"));
      const declared = manifest.evidence_index_digest || index.evidence_index_digest;
      if (declared) {
        const meta = (index.entries || []).map((e) => ({
          path: String(e.path || ""), type: e.type, note: e.note,
          action_digest: e.action_digest ?? null,
        }));
        meta.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
        const got = "sha256:" + sha256(canonicalBytes(meta));
        if (got !== declared) {
          const c = checks.find((x) => x.id === "S7");
          c.result = "FAIL";
          c.detail = "metadata digest does not re-derive";
        }
      }
    } catch { /* S7 already reported what it could read */ }
  }

  // S12 timestamps, identifiers and the counts that must agree with them
  {
    const problems = [];
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      if (!realDate(manifest.created_at)) problems.push("manifest.created_at is not a real ISO-8601 Z time");
      if (!Number.isInteger(manifest.evidence_count)) problems.push("evidence_count is not an integer");
      const index = readJson(join(pkg, "evidence/index.json"));
      const n = (index.entries || []).length;
      if (Number.isInteger(manifest.evidence_count) && manifest.evidence_count !== n) {
        problems.push("evidence_count says " + manifest.evidence_count + ", index holds " + n);
      }
      const lc = readJson(join(pkg, "lifecycle.json"));
      const events = Array.isArray(lc) ? lc : (lc.events || []);
      let last = null;
      for (const ev of events) {
        const at = ev.at || ev.created_at || ev.timestamp;
        if (!realDate(at)) { problems.push("lifecycle event without a real time"); break; }
        if (last && Date.parse(at) < Date.parse(last)) {
          problems.push("lifecycle time goes backwards"); break;
        }
        last = at;
      }
    } catch (err) { problems.push(err.message); }
    note("S12", "timestamp and identifier strictness", problems.length === 0,
         problems.slice(0, 4).join("; ") || "ok");
  }

  const failed = checks.filter((c) => c.result === "FAIL").map((c) => c.id);
  return {
    result: failed.length ? "FAIL" : "INCONCLUSIVE",
    trust_level: failed.length ? "FAIL" : "INCONCLUSIVE",
    failed_checks: failed.length,
    checks,
    note: "structural verifier: signatures, Merkle proofs, external timestamps and " +
          "the receipt chain are not checked here, so a sound package is " +
          "INCONCLUSIVE rather than PASS",
    implementation: "verify-js (independent of uibc-core)",
  };
}

const target = process.argv[2];
if (!target) {
  console.error("usage: node tools/verify-js/verify.mjs <package-dir>");
  process.exit(2);
}
try {
  process.stdout.write(JSON.stringify(verify(target), null, 2) + "\n");
} catch (err) {
  process.stdout.write(JSON.stringify({
    result: "FAIL", trust_level: "FAIL", failed_checks: 1,
    checks: [{ id: "S0", name: "verifier robustness", result: "FAIL", detail: String(err.message) }],
    implementation: "verify-js",
  }, null, 2) + "\n");
}
