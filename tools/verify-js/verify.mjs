#!/usr/bin/env node
// An independent structural verifier for UIBC packages, written in JavaScript
// with no dependency on uibc-core and no third-party packages.
//
// Covered here: package structure (S1), identity consistency (S2), evidence
// integrity (S4), evidence root (S5), Ed25519 seals (S6), index metadata (S7),
// the package checkpoint (S8), the closure declaration (S10), strict
// serialization (S11), timestamp and identifier strictness (S12), Merkle
// inclusion (S13), strict base64 (S14), anchor resolution (S15), the linear
// receipt chain (S17) and policy artefact resolution (S18).
//
// Not covered, on purpose: external timestamps (S16) and the out-of-band pin
// (S9) -- both need something this checker does not hold: a token signed by a
// key we do not have, and an observation made outside this package. Those need
// RFC 3161 and an observation made outside this package. A checker that claimed them without implementing them would be worse
// than one that says it cannot.
// Because it cannot attest signatures, it never returns PASS.
//
// Usage:  node tools/verify-js/verify.mjs <package-dir>

import { createHash, createPublicKey, verify as cryptoVerify } from "node:crypto";
import { verifyToken as verifyRfc3161 } from "./rfc3161.mjs";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, normalize, sep } from "node:path";

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

// --- RFC 8785 (JCS) -------------------------------------------------------

// RFC 6962 Merkle tree: leaf = SHA-256(0x00 || data), node = SHA-256(0x01 || l || r).
// An unbalanced tail is promoted, not duplicated: duplicating it lets two
// different trees share a root, which is the classic mistake.
const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);

function leafHash(data) {
  return createHash("sha256").update(Buffer.concat([LEAF_PREFIX, data])).digest();
}

function nodeHash(left, right) {
  return createHash("sha256").update(Buffer.concat([NODE_PREFIX, left, right])).digest();
}

function merkleRoot(leaves) {
  if (leaves.length === 0) return Buffer.alloc(32);
  if (leaves.length === 1) return leaves[0];
  let k = 1;
  while (k * 2 < leaves.length) k *= 2;
  return nodeHash(merkleRoot(leaves.slice(0, k)), merkleRoot(leaves.slice(k)));
}

function verifyInclusion(leaf, index, size, proof, root) {
  if (!Number.isInteger(size) || size <= 0) return false;
  if (!Number.isInteger(index) || index < 0 || index >= size) return false;
  let fn = index, sn = size - 1, r = leaf;
  for (const sibling of proof) {
    if (!Buffer.isBuffer(sibling) || sibling.length !== 32) return false;
    if (fn % 2 === 1 || fn === sn) {
      r = nodeHash(sibling, r);
      while (fn % 2 === 0 && fn !== 0) { fn /= 2; sn /= 2; }
    } else {
      r = nodeHash(r, sibling);
    }
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
  }
  return r.equals(root) && sn === 0;
}

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
function verify(pkg, opts = {}) {
  const expectHead = opts.expectHead ?? null;
  const strict = opts.strict === true;
  const checks = [];
  const warnings = [];
  const note = (id, name, ok, detail) =>
    checks.push({ id, name, result: ok ? "PASS" : "FAIL", detail });
  // The third verdict. A check whose input is itself untrustworthy has found
  // out nothing, and "nothing was found wrong" is not the same statement as
  // "the package is sound". Collapsing that into FAIL blames one root cause
  // twice; collapsing it into PASS asserts what was never checked.
  const inconclusive = (id, name, detail) =>
    checks.push({ id, name, result: "INCONCLUSIVE", detail });

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
    // Undeclared files split into three cases, and only one of them fails:
    //
    //   * a stray file at the package ROOT can contradict the evidence beside
    //     it, so it fails;
    //   * a file under evidence/ that the index never promised is a NOTE by
    //     default and a failure under --strict -- this format itself places
    //     structural members there (the anchor set, the receipt chain, the
    //     policy artefacts), and each is resolved by the check that owns it;
    //   * anything else outside evidence/ is auxiliary and stays a note.
    //
    // A previous version of this file failed every undeclared file under
    // evidence/, which made it stricter than the Python verifier's default. A
    // second implementation that is silently stricter is worse than one that
    // is lax: it refuses valid packages, and the difference only shows up on
    // packages nobody put in the suite.
    const rootExtras = [];
    const evidenceExtras = [];
    const auxExtras = [];
    for (const rel of listFiles(pkg)) {
      if (rel === "manifest.json" || rel === "identity.json" || rel === "lifecycle.json") continue;
      if (rel.startsWith("signatures/")) continue;
      if (STRUCTURAL.has(rel) || rel.startsWith("evidence/policies/")) continue;
      // Lock and backup files are how a writer protects a package, not
      // evidence. Anything hidden is machinery.
      if (rel.split("/").pop().startsWith(".")) continue;
      if (declared.has(rel)) continue;
      if (rel.includes("/")) {
        if (rel.startsWith("evidence/")) evidenceExtras.push(rel);
        else auxExtras.push(rel);
      } else {
        rootExtras.push(rel);
      }
    }
    if (rootExtras.length) problems.push("undeclared files at package root: " + rootExtras.join(", "));
    if (evidenceExtras.length) {
      if (opts.strict) problems.push("uncommitted files under evidence/: " + evidenceExtras.join(", "));
      else warnings.push("note (lenient mode): " + evidenceExtras.join(", ") +
                         " under evidence/ are structural or uncommitted; pass --strict to fail uncommitted ones");
    }
    if (auxExtras.length) warnings.push("note: " + auxExtras.join(", ") + " outside evidence/, not covered by the evidence root");
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

  // S3 lifecycle state machine and its semantic layer.
  //
  // Two families of rules, both from the specification and neither dependent on
  // the Python implementation:
  //
  //   L1-L7  the state machine: one REGISTER first, a chain of event_ids that
  //          reaches back exactly one step each time, RESUME only after SUSPEND,
  //          nothing after a terminal event.
  //   L8-L12 the semantics the bare state machine cannot see: timestamps that
  //          parse, do not run backwards, do not sit in the future or before
  //          1970; actors that are actually principals of this agent; ACTIVATE
  //          exactly once; a sequence_number that is contiguous from 0, because
  //          a gap in a sealed log is how a suppressed event looks.
  //
  // Lifetimes are compared as instants, not strings: "2026-02-30" is a string
  // that sorts fine and a date that does not exist.
  {
    const problems = [];
    const EVENTS = new Set(["REGISTER", "ACTIVATE", "UPDATE", "TRANSFER", "DELEGATE",
                            "MIGRATE", "SUSPEND", "RESUME", "REVOKE", "RETIRE"]);
    const TERMINAL = new Set(["REVOKE", "RETIRE"]);
    const ONCE_ONLY = new Set(["ACTIVATE"]);

    // A timestamp is usable here only if it names a real instant: ISO-8601 with
    // a zone, whose calendar fields exist. Anything else is L8, not a crash.
    const parseStamp = (value) => {
      if (typeof value !== "string") return null;
      const text = value.trim();
      const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/
        .exec(text);
      if (!m) return null;
      if (!realDate(text)) return null;
      const ms = Date.parse(text);
      return Number.isNaN(ms) ? null : ms;
    };

    let events = [];
    let manifest = {}, identity = {};
    try { events = readJson(join(pkg, "lifecycle.json")).events || []; }
    catch (err) { problems.push("lifecycle.json is not readable: " + err.message); }
    try { manifest = readJson(join(pkg, "manifest.json")); } catch { /* S1 reports it */ }
    try { identity = readJson(join(pkg, "identity.json")); } catch { /* S1 reports it */ }

    const allowedActors = new Set([identity.owner, identity.agent_id].filter((x) => x !== undefined && x !== null));
    const createdMs = parseStamp(String(manifest.created_at || identity.created_at || ""));
    const ceiling = createdMs === null ? null : createdMs + 86400 * 1000;

    const seenIds = new Set();
    let prevId = null, prevType = null, registered = false, prevMs = null;
    const counts = {};

    if (!Array.isArray(events)) {
      problems.push("lifecycle.events is not an array");
    } else {
      events.forEach((ev, i) => {
        if (typeof ev !== "object" || ev === null || Array.isArray(ev)) {
          problems.push("L8 event " + i + " is not an object");
          return;
        }
        const etype = ev.event_type;
        const eid = ev.event_id;

        if (!EVENTS.has(etype)) problems.push("L3 unknown event_type '" + String(etype) + "' at position " + i);
        if (seenIds.has(eid)) problems.push("L5 duplicate event_id '" + String(eid) + "' at position " + i);
        seenIds.add(eid);

        if ((ev.previous_event ?? null) !== prevId) {
          problems.push("L4 previous_event chain broken at position " + i +
                        " (expected " + String(prevId) + ", got " + String(ev.previous_event) + ")");
        }
        if (i === 0) {
          if (etype !== "REGISTER") problems.push("L1 first event must be REGISTER");
        } else if (!registered) {
          problems.push("L1 event before REGISTER at position " + i);
        } else if (etype === "REGISTER") {
          problems.push("L2 duplicate REGISTER at position " + i);
        }
        if (etype === "REGISTER") registered = true;
        if (etype === "RESUME" && prevType !== "SUSPEND") {
          problems.push("L6 RESUME at position " + i + " not preceded by SUSPEND");
        }
        if (i > 0 && TERMINAL.has(prevType)) {
          problems.push("L7 event after terminal event at position " + i);
        }

        const ms = parseStamp(ev.timestamp);
        if (ms === null) {
          problems.push("L8 event " + i + " has no parsible ISO-8601 timestamp ('" + String(ev.timestamp) + "')");
        } else {
          if (new Date(ms).getUTCFullYear() < 1970) problems.push("L9 event " + i + " timestamp predates 1970");
          if (prevMs !== null && ms < prevMs) {
            problems.push("L8 event " + i + " timestamp goes backwards (" + String(ev.timestamp) + " < previous)");
          }
          prevMs = ms;
          if (ceiling !== null && ms > ceiling) {
            problems.push("L9 event " + i + " timestamp " + String(ev.timestamp) +
                          " is later than manifest.created_at + 86400s (implausible: the log is sealed at creation time)");
          }
        }

        if (allowedActors.size && !allowedActors.has(ev.actor)) {
          problems.push("L10 event " + i + " actor '" + String(ev.actor) +
                        "' is not an authorised principal [" + [...allowedActors].join(", ") + "]");
        }

        counts[etype] = (counts[etype] || 0) + 1;
        if (ONCE_ONLY.has(etype) && counts[etype] > 1) {
          problems.push("L11 duplicate " + String(etype) + " at position " + i +
                        " (" + counts[etype] + " occurrences of a once-only event)");
        }

        if ("sequence_number" in ev) {
          const seq = ev.sequence_number;
          if (typeof seq !== "number" || !Number.isInteger(seq)) {
            problems.push("L12 event " + i + " sequence_number is not an integer (" + String(seq) + ")");
          } else if (seq !== i) {
            problems.push("L12 event " + i + " sequence_number=" + seq +
                          " breaks contiguity (expected " + i + "): a gap in a sealed log indicates a suppressed event");
          }
        }

        prevId = eid;
        prevType = etype;
      });
    }

    note("S3", "lifecycle state machine + semantics", problems.length === 0,
         problems.slice(0, 4).join("; ") ||
           (events.length + " events, chain valid, timestamps monotonic, actors authorised"));
  }

  // S4 evidence integrity
  const hashes = [];
  let s4Failed = false;
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
    s4Failed = problems.length !== 0;
    note("S4", "evidence integrity", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S5 evidence root
  //
  // Rooting a set of hashes that S4 has just shown to be wrong would score one
  // root cause twice: the file is not what the index promised, and therefore
  // the root derived from it is not the root the manifest promises either.
  // The second statement is not a second finding, it is the same finding.
  // When S4 fails the root is INCONCLUSIVE, matching the Python verifier.
  if (s4Failed) {
    inconclusive("S5", "evidence root", "skipped: evidence missing or S4 failed");
  } else {
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

  // S6 seal signature. Ed25519 can be checked here because the package
  // records the public key: that is the whole point of an asymmetric seal --
  // a stranger verifies provenance with no secret at all. An HMAC seal cannot
  // be checked without the owner's key, and this verifier says so instead of
  // guessing.
  {
    const sealPath = join(pkg, "signatures", "seal.json");
    if (!existsSync(sealPath)) {
      note("S6", "seal signature", false, "package is unsigned; provenance is not attested");
    } else {
      let verdict = "inconclusive", detail = "";
      try {
        const seal = readJson(sealPath);
        const identity = readJson(join(pkg, "identity.json"));
        const manifest = readJson(join(pkg, "manifest.json"));
        if (seal.algorithm !== "Ed25519") {
          detail = "seal uses " + seal.algorithm +
                   "; an HMAC seal cannot be verified without the owner's key";
        } else {
          const lifecycle = readJson(join(pkg, "lifecycle.json"));
          const signed = String(seal.signed || "");
          const doc = { identity, manifest };
          if (signed.includes("lifecycle")) doc.lifecycle = lifecycle;
          const msg = canonicalBytes(doc);
          const pub = Buffer.from(String(seal.public_key), "base64");
          const sig = Buffer.from(String(seal.signature), "base64");
          const x = pub.toString("base64url");
          const key = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x }, format: "jwk" });
          const ok = cryptoVerify(null, msg, key, sig);
          verdict = ok ? "pass" : "fail";
          detail = ok ? "ok (verified with the public key recorded in the package)"
                      : "signature does not verify against the recorded public key";
        }
      } catch (err) {
        verdict = "fail";
        detail = "seal is not readable: " + err.message;
      }
      if (verdict === "inconclusive") {
        checks.push({ id: "S6", name: "seal signature", result: "INCONCLUSIVE", detail });
      } else {
        note("S6", "seal signature", verdict === "pass", detail);
      }
    }
  }

  // S14 strict base64. A canonical encoding admits exactly one string per
  // byte sequence; pad bits, missing padding and stray characters all decode
  // permissively, so two decoders can disagree about what was signed. Only
  // fields the package itself marks as base64 are examined -- a schema that
  // does not use base64 cannot be false-flagged.
  {
    const docOf = (rel) => {
      const p = join(pkg, rel);
      return existsSync(p) ? readJson(p) : null;
    };
    const manifestD = docOf("manifest.json");
    const identityD = docOf("identity.json");
    const lifecycleD = docOf("lifecycle.json");
    const indexD = docOf("evidence/index.json");
    const b64Fields = [];
    const walk = (node, path) => {
      if (Array.isArray(node)) {
        node.forEach((v, i) => walk(v, path + "[" + i + "]"));
      } else if (node && typeof node === "object") {
        for (const [k, v] of Object.entries(node)) {
          const child = path ? path + "/" + k : k;
          if (typeof v === "string" &&
              (k.endsWith("_b64") || k.endsWith("_base64") || k === "base64")) {
            b64Fields.push([child, v, k === "base64_url"]);
          } else {
            walk(v, child);
          }
        }
      }
    };
    for (const [name, doc] of [["manifest.json", manifestD], ["identity.json", identityD],
                               ["lifecycle.json", lifecycleD],
                               ["evidence/index.json", indexD]]) {
      if (doc) walk(doc, name);
    }
    if (b64Fields.length) {
      const problems = [];
      const STD = /^[A-Za-z0-9+/=]+$/, URL = /^[A-Za-z0-9-_=]+$/;
      for (const [field, value, urlsafe] of b64Fields) {
        const why = (() => {
          if (!value) return "empty";
          if (!(urlsafe ? URL : STD).test(value)) return "character outside the base64 alphabet";
          const core = value.replace(/=+$/, "");
          if (core.length % 4 === 1) return "length cannot be base64";
          if (!value.endsWith("=") && value.length % 4 !== 0) return "unpadded input";
          if (value.endsWith("=") && value.length % 4 !== 0) return "padded length is not a multiple of 4";
          const buf = Buffer.from(value, "base64");
          const back = buf.toString("base64");
          if (value.endsWith("=") && back !== value) return "non-canonical: pad bits are not zero";
          if (!urlsafe && value !== value.replace(/-/g, "+").replace(/_/g, "/")) return "urlsafe characters in standard base64";
          return null;
        })();
        if (why) problems.push(field + ": " + why);
      }
      note("S14", "strict base64", problems.length === 0,
           problems.length ? problems.slice(0, 4).join("; ")
                           : b64Fields.length + " declared base64 field(s) are canonical");
    }
  }

  // S10 attestation closure. Whether the six digests correspond to what
  // actually ran is NOT decidable from a package; this check asks only that
  // all six are declared and look like digests. Saying more would be the
  // overclaim this project refuses elsewhere.
  {
    const mp = join(pkg, "manifest.json");
    const m = existsSync(mp) ? readJson(mp) : null;
  if (m && m.closure !== undefined && m.closure !== null) {
    const CLOSURE_FIELDS = ["model_weights", "tokenizer", "chat_template",
                            "engine_build", "decoding", "numeric_env"];
    const SHA = /^(sha256:)?[0-9a-f]{64}$/;
    const closure = m.closure;
    const missing = [];
    if (typeof closure !== "object" || Array.isArray(closure)) {
      missing.push("closure is not an object");
    } else {
      for (const k of CLOSURE_FIELDS) {
        const v = closure[k];
        if (typeof v !== "string" || !SHA.test(v)) missing.push(k);
      }
    }
    note("S10", "attestation closure declared", missing.length === 0,
         missing.length ? "closure is incomplete or malformed: " + missing.join(", ")
                        : "all 6 closure components declared with digests " +
                          "(declaration only, contents are not verified)");
  }
  }

  // S13 Merkle inclusion (RFC 6962). A hash chain answers "was file N
  // changed?"; a Merkle tree answers "is this one file inside a set of size N
  // that the manifest committed to, without handing over all N files?" Runs
  // only when the package carries evidence/merkle.json -- a package with no
  // tree is not penalised for it.
  {
    const merklePath = join(pkg, "evidence", "merkle.json");
    if (existsSync(merklePath)) {
      const problems = [];
      const mdoc = readJson(merklePath);
      const idx = existsSync(join(pkg, "evidence/index.json"))
        ? readJson(join(pkg, "evidence/index.json")) : { entries: [] };
      const order = (idx.entries || []).slice().sort((a, b) =>
        String(a.path) < String(b.path) ? -1 : String(a.path) > String(b.path) ? 1 : 0);
      const leaves = [];
      for (const e of order) {
        try {
          leaves.push(leafHash(readFileSync(join(pkg, "evidence", String(e.path)))));
        } catch (err) {
          problems.push("cannot read evidence file " + JSON.stringify(e.path));
        }
      }
      const root = merkleRoot(leaves);
      if (mdoc.algorithm !== "rfc6962-sha256") {
        problems.push("algorithm " + JSON.stringify(mdoc.algorithm) + " is not rfc6962-sha256");
      }
      if (mdoc.size !== leaves.length) {
        problems.push("declared size " + JSON.stringify(mdoc.size) + " != " +
                      leaves.length + " evidence leaves");
      }
      if (String(mdoc.root || "").toLowerCase() !== root.toString("hex")) {
        problems.push("declared root does not match recomputed root");
      }
      const proofs = mdoc.proofs || [];
      for (const pr of proofs) {
        const p = String(pr.path);
        const at = order.findIndex((e) => String(e.path) === p);
        if (at < 0) {
          problems.push("proof names unknown evidence " + JSON.stringify(p));
          continue;
        }
        if (pr.index !== undefined && pr.index !== at) {
          problems.push("proof index for " + JSON.stringify(p) + " is " +
                        JSON.stringify(pr.index) + ", recomputed " + at);
        }
        const siblings = [];
        let bad = false;
        for (const h of (pr.proof || [])) {
          const hex = String(h);
          if (!/^[0-9a-fA-F]{64}$/.test(hex)) { bad = true; break; }
          siblings.push(Buffer.from(hex, "hex"));
        }
        if (bad) { problems.push("proof for " + JSON.stringify(p) + " has a non-hex sibling"); continue; }
        if (at >= leaves.length) {
          problems.push("proof names evidence " + JSON.stringify(p) + " whose file is absent");
          continue;
        }
        if (!verifyInclusion(leaves[at], at, leaves.length, siblings, root)) {
          problems.push("inclusion proof for " + JSON.stringify(p) + " does not verify");
        }
      }
      note("S13", "merkle inclusion proofs", problems.length === 0,
           problems.length ? problems.slice(0, 4).join("; ")
                           : "root " + root.toString("hex").slice(0, 16) +
                             "... over " + leaves.length + " leaves; " +
                             proofs.length + " inclusion proof(s) verified");
    }
  }

  // S8 package checkpoint head. One value committing to the WHOLE package
  // state: the lifecycle head, the evidence root, the index metadata digest and
  // the evidence count. A lifecycle-only head was not enough -- adding evidence
  // changes the root but leaves the log untouched, so two different states
  // shared one head. Truncation, rollback and post-seal replacement are what
  // this detects, and only inside this package; a rollback of the whole
  // store needs an observation made somewhere else (S9, not checkable here).
  {
    const mp = join(pkg, "manifest.json");
    const m = existsSync(mp) ? readJson(mp) : null;
    if (m && m.checkpoint_head !== undefined && m.checkpoint_head !== null) {
      const problems = [];
      let state = null;
      try {
        const idx = existsSync(join(pkg, "evidence/index.json"))
          ? readJson(join(pkg, "evidence/index.json")) : { entries: [] };
        const entries = idx.entries || [];
        const hs = [];
        for (const e of entries) {
          try { hs.push(sha256(readFileSync(join(pkg, "evidence", String(e.path))))); }
          catch { /* S4 reports the missing file; the count still stands */ }
        }
        const root = sha256(canonicalBytes(hs.slice().sort()));
        const meta = entries.map((e) => ({
          path: String(e.path || ""), type: e.type, note: e.note,
          action_digest: e.action_digest ?? null,
        }));
        meta.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
        const indexDigest = "sha256:" + sha256(canonicalBytes(meta));
        const lcPath = join(pkg, "lifecycle.json");
        const lc = existsSync(lcPath) ? readJson(lcPath) : {};
        const events = lc.events || [];
        const last = events.length ? events[events.length - 1] : null;
        const lcHead = "sha256:" + sha256(canonicalBytes({
          count: events.length,
          last_sequence_number: last ? (last.sequence_number ?? null) : null,
          last_event_digest: last ? sha256(canonicalBytes(last)) : null,
        }));
        state = "sha256:" + sha256(canonicalBytes({
          lifecycle_head: lcHead,
          evidence_root: root,
          evidence_index_digest: indexDigest,
          evidence_count: entries.length,
        }));
        if (state !== String(m.checkpoint_head)) {
          problems.push("state does not match the sealed checkpoint_head (manifest " +
                        String(m.checkpoint_head).slice(0, 20) + "..., disk " +
                        state.slice(0, 20) + "...) - state truncated, rolled back, " +
                        "or replaced after sealing");
        }
      } catch (err) {
        problems.push("state is not canonicalizable: " + err.message);
      }
      note("S8", "package checkpoint head", problems.length === 0,
           problems.length ? problems.slice(0, 2).join("; ")
                           : "checkpoint matches");

      // S9 head pinned out-of-band. This is the one check nothing inside the
      // package can perform: an older package that is perfectly self-consistent
      // is indistinguishable from the current one unless somebody recorded the
      // head elsewhere and compares it here. The value is passed in, never read
      // from the package, or it would be the thing being checked.
      if (expectHead !== null && expectHead !== undefined) {
        if (state === null) {
          note("S9", "head pinned out-of-band", false,
               "the package state cannot be recomputed, so the pin cannot be compared");
        } else if (String(state) !== String(expectHead)) {
          note("S9", "head pinned out-of-band", false,
               "package checkpoint does not match the pinned value (" +
               String(expectHead).slice(0, 20) + "...) - a rollback to an older " +
               "self-consistent package, or a wrong pin");
        } else {
          note("S9", "head pinned out-of-band", true,
               "checkpoint matches the out-of-band pinned value");
        }
      }
    }
  }

  // S15 anchor resolution. A checkpoint head says "this is where my log was";
  // an anchor says "and here is evidence somebody outside my log saw it at
  // time T". Resolving against OUR OWN evidence root proves the anchor was
  // built from this package. It does NOT prove a third party saw it -- an
  // anchor naming an external log stays unresolved rather than being counted
  // as checked, because "I could not verify" is not "OK".
  {
    const anchorsPath = join(pkg, "evidence", "anchors.json");
    if (existsSync(anchorsPath)) {
      const problems = [];
      let resolved = 0;
      try {
        const adoc = readJson(anchorsPath);
        const idx = existsSync(join(pkg, "evidence/index.json"))
          ? readJson(join(pkg, "evidence/index.json")) : { entries: [] };
        const order = (idx.entries || []).slice().sort((a, b) =>
          String(a.path) < String(b.path) ? -1 : String(a.path) > String(b.path) ? 1 : 0);
        const leaves = [];
        for (const e of order) {
          try { leaves.push(leafHash(readFileSync(join(pkg, "evidence", String(e.path))))); }
          catch { /* S4 reports it; the anchor is then unresolvable */ }
        }
        const root = merkleRoot(leaves);
        if (!adoc || typeof adoc !== "object") {
          problems.push("anchors.json is not an object");
        } else if (adoc.resolver !== "evidence-merkle") {
          problems.push("resolver " + JSON.stringify(adoc.resolver) +
                        " is not one we can resolve offline (supported: evidence-merkle)");
        } else if (!Array.isArray(adoc.anchors) || !adoc.anchors.length) {
          problems.push("anchors list is missing or empty");
        } else {
          const HEX = /^[0-9a-f]{64}$/;
          const TS = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
          const calendarOk = (y, mo, d) => {
            if (!(mo >= 1 && mo <= 12 && d >= 1 && d <= 31)) return false;
            const days = [31, (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)) ? 29 : 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
            return d <= days[mo - 1];
          };
          const tsProblem = (v) => {
            if (typeof v !== "string") return "anchored_at is not a string";
            const m = TS.exec(v);
            if (!m) return "anchored_at is not RFC 3339 with a zone";
            if (!calendarOk(+m[1], +m[2], +m[3])) return "anchored_at is not a real calendar date";
            if (+m[6] > 59) return "anchored_at carries a leap second";
            const off = m[8];
            if (off !== "Z") {
              const hh = +off.slice(1, 3), mm = +off.slice(4, 6);
              if (hh > 14 || mm > 59) return "anchored_at has an out-of-range UTC offset";
            }
            return null;
          };
          adoc.anchors.forEach((a, i) => {
            const probs = [];
            const aid = a && a.id;
            if (typeof aid !== "string" || !aid.trim()) probs.push("anchor id is missing or empty");
            if (!Number.isInteger(a && a.version) || a.version < 1) probs.push("anchor version must be an integer >= 1");
            if (typeof a.leaf_hash !== "string" || !HEX.test(a.leaf_hash)) probs.push("leaf_hash is not 64 lowercase hex characters");
            const tp = tsProblem(a.anchored_at);
            if (tp) probs.push(tp);
            const declared = a.root;
            if (typeof declared !== "string" || !HEX.test(declared)) probs.push("root is not 64 lowercase hex characters");
            if (!Number.isInteger(a.index)) probs.push("index is not an integer");
            if (!Number.isInteger(a.size) || a.size < 1) probs.push("size is not a positive integer");
            if (!Array.isArray(a.proof) || !a.proof.length) probs.push("proof is missing or empty");
            if (typeof declared === "string" && declared !== root.toString("hex")) {
              probs.push("declared root is not the root this package resolves to");
            }
            if (!probs.length && Number.isInteger(a.index) && a.index >= 0 && a.index < leaves.length) {
              if (a.leaf_hash !== leaves[a.index].toString("hex")) {
                probs.push("leaf_hash does not match the evidence leaf at that index");
              }
            }
            if (!Number.isInteger(a.index) || a.index < 0 || a.index >= leaves.length) {
              probs.push("anchor index is outside the evidence set");
            }
            if (!probs.length) {
              const sib = [];
              let bad = false;
              for (const h of (a.proof || [])) {
                if (!/^[0-9a-fA-F]{64}$/.test(String(h))) { bad = true; break; }
                sib.push(Buffer.from(String(h), "hex"));
              }
              if (bad) probs.push("proof contains a non-hex sibling");
              else if (!verifyInclusion(Buffer.from(a.leaf_hash, "hex"), a.index, a.size, sib,
                                        Buffer.from(a.root, "hex"))) {
                probs.push("inclusion proof does not verify against the declared root");
              }
            }
            if (probs.length) problems.push("anchor[" + i + "] " + String(aid || "?") + ": " + probs.join("; "));
            else resolved += 1;
          });
        }
      } catch (err) {
        problems.push("anchors.json is not readable: " + err.message);
      }
      note("S15", "anchor event resolution", problems.length === 0,
           problems.length ? problems.slice(0, 3).join("; ")
                           : resolved + " anchor(s) resolved against the evidence Merkle root");
    }
  }

  // S16 external timestamp (RFC 3161). Everything above is witnessed by parties
  // we choose: our tree, our head, our pin. An RFC 3161 token is the one witness
  // we cannot mint - it dates a digest with a key held by somebody else, and the
  // check is that its signature verifies against a CA we were given. An
  // unjudgeable token is INCONCLUSIVE, never PASS: a timestamp nobody verified
  // is not a timestamp.
  {
    const extPath = join(pkg, "evidence", "external_anchor.json");
    if (existsSync(extPath)) {
      const problems = [];
      let summary = null;
      try {
        const ext = readJson(extPath);
        const relData = ext.digest_of || "manifest.json";
        const dataPath = join(pkg, relData);
        let dataBytes = null;
        try { dataBytes = readFileSync(dataPath); }
        catch { problems.push("cannot read anchored file " + JSON.stringify(relData)); }
        let body = null;
        try { body = readFileSync(join(pkg, String(ext.tsr || ""))); }
        catch { problems.push("cannot read token " + JSON.stringify(ext.tsr)); }
        let caPem = "";
        try { caPem = readFileSync(join(pkg, String(ext.cabundle || "")), "utf8"); }
        catch { problems.push("cannot read CA bundle " + JSON.stringify(ext.cabundle)); }
        if (body && ext.tsr_sha256) {
          const h = sha256(body);
          if (h !== ext.tsr_sha256) {
            problems.push("token digest is not the declared tsr_sha256 (declared " +
                          String(ext.tsr_sha256).slice(0, 16) + "..., actual " + h.slice(0, 16) + "...)");
          }
        }
        if (!problems.length && body && dataBytes) {
          const r = verifyRfc3161(body, sha256(dataBytes), caPem);
          summary = r.info;
          if (!r.ok) problems.push(...r.problems);
        }
      } catch (err) {
        problems.push("external_anchor.json is not readable: " + err.message);
      }
      note("S16", "external timestamp (RFC 3161)", problems.length === 0,
           problems.length ? problems.slice(0, 3).join("; ")
                           : "token verified: " + (summary && summary.gen_time ? "stamped " + summary.gen_time + ", " : "") +
                             "TSA " + (summary && summary.tsa && summary.tsa.subject
                               ? String(summary.tsa.subject).split(",")[0] : "unknown"));
    }
  }

  // S17 linear receipt chain. S8/S9/S13 all commit a TREE. None of them answers
  // "is this record the successor of that record" -- the question a regulator
  // asks when one receipt is pulled out of the middle of a stream. The link is
  // previousReceiptHash = SHA-256 over the JCS of the predecessor's signed
  // envelope, and the first receipt carries 64 zeros. A value JCS cannot encode
  // is a FAIL, not a skip: an unjudgeable link is not an intact link.
  {
    const chainPath = join(pkg, "evidence", "chain.json");
    if (existsSync(chainPath)) {
      const GENESIS = "0".repeat(64);
      const HEX64 = /^[0-9a-f]{64}$/;
      const problems = [];
      let checked = 0;
      try {
        const cdoc = readJson(chainPath);
        const receipts = (cdoc && cdoc.receipts);
        if (!cdoc || typeof cdoc !== "object") {
          problems.push("chain document is not an object");
        } else if (!Array.isArray(receipts) || !receipts.length) {
          problems.push("chain document carries no receipts");
        } else {
          let prev = null;
          for (let i = 0; i < receipts.length; i += 1) {
            const item = receipts[i];
            if (!item || typeof item !== "object") {
              problems.push("receipt " + i + " is not an object");
              continue;
            }
            const env = item.envelope;
            const declared = item.previous_receipt_hash;
            if (!env || typeof env !== "object") {
              problems.push("receipt " + i + " carries no envelope object");
              continue;
            }
            if (typeof declared !== "string" || !HEX64.test(declared)) {
              problems.push("receipt " + i + ": previous_receipt_hash is not 64 lowercase hex characters");
              continue;
            }
            if (i === 0 && declared !== GENESIS) {
              problems.push("receipt 0: previous_receipt_hash is " + declared.slice(0, 12) +
                            "..., but the first receipt of a chain must carry 64 zeros");
            } else if (i > 0 && declared !== prev) {
              problems.push("receipt " + i + ": previous_receipt_hash is " + declared.slice(0, 12) +
                            "..., but the predecessor's digest is " + String(prev).slice(0, 12) + "...");
            }
            try {
              prev = createHash("sha256").update(canonicalBytes(env)).digest("hex");
            } catch (err) {
              problems.push("receipt " + i + ": envelope cannot be canonicalized (" + err.message +
                            "); a chain is FAIL rather than inconclusive because the value is unjudgeable, not merely absent");
              prev = null;
              continue;
            }
            checked += 1;
          }
        }
      } catch (err) {
        problems.push("chain.json is not readable: " + err.message);
      }
      note("S17", "linear receipt chain", problems.length === 0,
           problems.length ? problems.slice(0, 3).join("; ")
                           : checked + " receipt(s) linked by previousReceiptHash over JCS; genesis is 64 zeros");
    }
  }

  // S18 policy artefact resolution. A policy_digest nobody can resolve is a
  // number, not evidence. Every digest listed must match the artefact shipped
  // next to it, and every digest a receipt declares must resolve in that map.
  // The artefact has to be JSON: the digest is defined over its JCS encoding,
  // so a PDF policy needs a JSON projection alongside -- a constraint of the
  // draft, not of this implementation.
  {
    const policiesPath = join(pkg, "evidence", "policies.json");
    if (existsSync(policiesPath)) {
      const HEX64 = /^[0-9a-f]{64}$/;
      const parseDigest = (v) => {
        if (typeof v !== "string") return null;
        let t = v.trim();
        if (t.startsWith("sha256:")) t = t.slice(7);
        return HEX64.test(t) ? t : null;
      };
      const required = [];
      const chainPath2 = join(pkg, "evidence", "chain.json");
      if (existsSync(chainPath2)) {
        try {
          const cdoc = readJson(chainPath2);
          for (const item of (cdoc.receipts || [])) {
            const env = item && item.envelope;
            if (env && typeof env === "object" && typeof env.policy_digest === "string" && env.policy_digest) {
              required.push(env.policy_digest);
            }
          }
        } catch { /* S17 reports an unreadable chain */ }
      }
      const problems = [];
      const known = new Set();
      let resolved = 0;
      try {
        const pdoc = readJson(policiesPath);
        const items = (pdoc && pdoc.policies);
        if (!pdoc || typeof pdoc !== "object") {
          problems.push("policies document is not an object");
        } else if (!Array.isArray(items) || !items.length) {
          problems.push("policies document lists no artefacts");
        } else {
          items.forEach((item, i) => {
            if (!item || typeof item !== "object") { problems.push("policy " + i + " is not an object"); return; }
            const declared = parseDigest(item.digest);
            if (!declared) { problems.push("policy " + i + ": digest is not sha256:<64 hex>"); return; }
            const rel = item.path;
            if (typeof rel !== "string" || !rel) { problems.push("policy " + i + ": no path"); return; }
            let body;
            try {
              body = readJson(join(pkg, rel));
            } catch (err) {
              problems.push("cannot read policy artefact " + JSON.stringify(rel) + " (" + err.message + "); " +
                            "the draft's digest is defined over its JCS encoding, so a non-JSON artefact needs a JSON projection shipped alongside");
              return;
            }
            let actual;
            try {
              actual = createHash("sha256").update(canonicalBytes(body)).digest("hex");
            } catch (err) {
              problems.push("policy " + i + ": artefact is not JCS-serializable (" + err.message + ")");
              return;
            }
            if (actual !== declared) {
              problems.push("policy " + i + ": declared digest " + declared.slice(0, 12) +
                            "... but the artefact hashes to " + actual.slice(0, 12) + "...");
              return;
            }
            known.add(declared);
            resolved += 1;
          });
        }
      } catch (err) {
        problems.push("policies.json is not readable: " + err.message);
      }
      for (const digest of required) {
        const d = parseDigest(digest);
        if (d === null) problems.push("a receipt declares a malformed policy_digest " + JSON.stringify(digest));
        else if (!known.has(d)) problems.push("receipt declares policy_digest " + d.slice(0, 12) +
                                              "... which does not resolve in the package");
      }
      note("S18", "policy artefact resolution", problems.length === 0,
           problems.length ? problems.slice(0, 3).join("; ")
                           : resolved + " policy artefact(s) resolve to their declared SHA-256 over JCS; " +
                             required.length + " digest(s) referenced by receipts resolved");
    }
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
    warnings,
    note: "structural verifier: signatures, Merkle proofs, external timestamps and " +
          "the receipt chain are not checked here, so a sound package is " +
          "INCONCLUSIVE rather than PASS",
    implementation: "verify-js (independent of uibc-core)",
  };
}

const argv = process.argv.slice(2);
let target = null;
let expectHead = null;
let strict = false;
for (let i = 0; i < argv.length; i += 1) {
  if (argv[i] === "--expect-head") {
    expectHead = argv[i + 1] ?? null;
    i += 1;
  } else if (argv[i] === "--strict") {
    strict = true;
  } else if (target === null) {
    target = argv[i];
  }
}
if (!target) {
  console.error("usage: node tools/verify-js/verify.mjs <package-dir> [--strict] [--expect-head <head>]");
  process.exit(2);
}
try {
  process.stdout.write(JSON.stringify(verify(target, { expectHead, strict }), null, 2) + "\n");
} catch (err) {
  process.stdout.write(JSON.stringify({
    result: "FAIL", trust_level: "FAIL", failed_checks: 1,
    checks: [{ id: "S0", name: "verifier robustness", result: "FAIL", detail: String(err.message) }],
    implementation: "verify-js",
  }, null, 2) + "\n");
}
