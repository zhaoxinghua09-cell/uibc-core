#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Four-lens external review over the same bus the pipeline uses (S4/S6).

Why this exists: the pipeline's `external_review.py` asks one fixed pair of
questions. That makes four "reviews" four copies of one question. This runner
keeps the bus contract (peer registry, inbox dispatch, outbox receipt, hash-chained
ledger, key only in memory) but sends a *different* question set per lens, so a
review of the same artifact under four lenses is actually four reviews.

It does not replace `external_review.py`; it imports it for `PEERS`, `load_key`,
`ledger_tail`, `make_ledger_record`, `sha256_text` and the bridge module.

CLI:
  python tools/lens_review.py --lens expert  --artifact docs/ECOSYSTEM-MAP.md          # dry-run
  python tools/lens_review.py --lens expert  --artifact docs/ECOSYSTEM-MAP.md --go
  python tools/lens_review.py --all --go        # four lenses, four artifacts below

Discipline inherited from the pipeline: fail-closed, receipt verbatim, key never printed
or logged, no receipt means only "dispatched" (never PASS).
"""

import base64
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_SCRIPTS = os.path.expandvars(
    r"%USERPROFILE%\.workbuddy\skills\intl-participation-pipeline\scripts")
sys.path.insert(0, SKILL_SCRIPTS)
sys.path.insert(0, os.path.dirname(HERE))

import external_review as bus  # noqa: E402  (peer registry, ledger helpers, bridge)

PEER = "siliconflow-deepseek"

# Each lens asks its own questions. No shared template.
LENSES = {
    "expert": {
        "artifact": "docs/ECOSYSTEM-MAP.md",
        "role": "You are a standards and regulatory expert (ISO/IEC JTC 1/SC 42, EU AI Act Article 12, DORA Article 17).",
        "asks": """1. Which statements would a standards-committee reader reject as premature because the referenced
   document is an individual draft, not an adopted work item? Quote each.
2. Where does the text use a verdict word ("pass", "verified", "compliant") in a way a regulator would read
   as a legal conclusion? Quote each.
3. Which relevant published standard is simply absent from the comparison? Name it and say what mapping is missing.
Then one line: LENS_EXPERT = CONTINUE or LENS_EXPERT = STOP.""",
    },
    "process": {
        "artifact": "README.md",
        "role": "You are a release-engineering reviewer who judges whether an outsider can reproduce a release.",
        "asks": """1. Walk the README as a first-time visitor: is there a single command that reproduces the headline
   claim, and is its expected output stated? Quote the weakest step.
2. Which number or identifier in this file could conflict with another file a reader might open (for example a
   test count, a log index, a DOI)? Name the risk.
3. Which claim is impossible to check without credentials the reader does not have?
Then one line: LENS_PROCESS = CONTINUE or LENS_PROCESS = STOP.""",
    },
    "adversary": {
        "artifact": "docs/INTEROP-MATRIX.md",
        "role": "You are an attacker looking for a sentence that overstates a defensive capability.",
        "asks": """1. Which sentence would let a hostile reader say "they compared their own synthetic samples and called
   it interoperability"? Quote it.
2. Where is a competitor's weakness stated without the reproduction that would let them rebut it?
3. Which of our own failures is described in a way that could be read as a feature?
Then one line: LENS_ADVERSARY = CONTINUE or LENS_ADVERSARY = STOP.""",
    },
    "outsider": {
        "artifact": "README.md",
        "role": "You are a compliance officer at an unrelated company, deciding in five minutes whether this repo is worth a trial.",
        "asks": """1. What do you still not understand after reading the first screen? Quote the sentence that failed you.
2. Is the name of this project ambiguous in a medical context, and would that stop a trial?
3. What single sentence, if added, would most increase your willingness to run it? Write that sentence.
Then one line: LENS_OUTSIDER = CONTINUE or LENS_OUTSIDER = STOP.""",
    },
}

SYSTEM = (
    "You are an independent external reviewer. You see one artifact and one question set. "
    "You have no background beyond the artifact itself. Do not assume favourable context. "
    "Be terse, quote exact sentences, and never answer beyond the questions asked."
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_artifact(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip()


def ask_peer(lens: str, body: str) -> dict:
    cfg = bus.PEERS[PEER]
    key = bus.load_key(PEER)
    prompt = (
        f"You are acting as: {LENSES[lens]['role']}\n\n"
        "Artifact, verbatim:\n--- BEGIN ---\n" + body + "\n--- END ---\n\n"
        + LENSES[lens]["asks"]
    )
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 900,
    }
    req = urllib.request.Request(
        cfg["endpoint"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        doc = json.loads(resp.read().decode("utf-8", "replace"))
    usage = doc.get("usage", {})
    return {
        "content": doc["choices"][0]["message"]["content"],
        "model_returned": doc.get("model", cfg["model"]),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "key_fingerprint": hashlib.sha256(key.encode()).hexdigest()[:16],
    }


def dispatch_md(lens: str, stem: str, body: str) -> str:
    return f"""# {stem} — S4 four-lens review (external model, custom question set)

- peer: `{PEER}` ({bus.PEERS[PEER]['vendor']} / `{bus.PEERS[PEER]['model']}`), external, non-first-party
- lens: **{lens}** — role: {LENSES[lens]['role']}
- artifact: `{LENSES[lens]['artifact']}`, sent verbatim, no analysis attached
- dispatched: {_now()}

The question set for this lens is generated by `tools/lens_review.py` and is different for each lens;
this is the point of the run.

## artifact under review

```
{body}
```
"""


def receipt_md(lens: str, stem: str, body: str, r: dict) -> str:
    return f"""# S4 回执 · {stem}

| field | value |
|---|---|
| peer | `{PEER}` |
| model | `{r['model_returned']}` |
| lens | `{lens}` |
| tokens | prompt={r['prompt_tokens']} / completion={r['completion_tokens']} |
| key fingerprint | sha256[:16] = `{r['key_fingerprint']}` (no plaintext) |
| received | {_now()} |

## Receipt, verbatim

```
{r['content'].strip()}
```

## Artifact under review

```
{body}
```
"""


def run_lens(lens: str, artifact: str, go: bool) -> int:
    body = read_artifact(artifact)
    token = bus.bridge.get_token(bus.bridge.OWNER)
    today = datetime.now().strftime("%Y%m%d")
    inbox = bus.bridge.list_dir(token, "inbox")
    seq = 1
    for it in inbox:
        if it["name"].startswith(today + "_"):
            try:
                seq = max(seq, int(it["name"].split("_")[1]) + 1)
            except ValueError:
                pass
    topic = "fourlens-" + lens
    stem = f"{today}_{seq:02d}_{topic}_{lens}"
    inbox_path = f"inbox/{stem}.md"
    outbox_path = f"outbox/{stem}_receipt.md"

    print(f"== lens={lens} ==")
    print(f"  artifact : {artifact} ({len(body)} chars)")
    print(f"  inbox    : {inbox_path}")
    print(f"  outbox   : {outbox_path}")
    if not go:
        print("  DRY-RUN — nothing written. add --go")
        return 0

    bus.bridge.put_file(token, inbox_path, dispatch_md(lens, stem, body).encode("utf-8"),
                        f"{lens} | {topic} | dispatch")
    print("[1/4] dispatched to inbox")
    r = ask_peer(lens, body)
    print(f"[2/4] received model={r['model_returned']} tokens={r['prompt_tokens']}/{r['completion_tokens']}")
    bus.bridge.put_file(token, outbox_path, receipt_md(lens, stem, body, r).encode("utf-8"),
                        f"{lens} | receipt | verbatim")
    print("[3/4] receipt written to outbox")

    recs, prev = bus.ledger_tail(token)
    core = {
        "seq": len(recs) + 1,
        "ts": _now(),
        "peer": PEER,
        "model": r["model_returned"],
        "topic": topic,
        "lens": lens,
        "inbox": inbox_path,
        "outbox": outbox_path,
        "input_sha256": bus.sha256_text(body),
        "receipt_sha256": bus.sha256_text(r["content"]),
        "key_fingerprint": r["key_fingerprint"],
    }
    rec = bus.make_ledger_record(prev, core)
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    try:
        cur = bus.bridge.api(f"{bus.bridge.API}/contents/{bus.REGISTRY}", token)
        old = base64.b64decode(cur["content"]).decode("utf-8")
        sha = cur["sha"]
    except Exception:
        old, sha = "", None
    payload = {"message": f"{lens} | ledger | seq {core['seq']}",
               "content": base64.b64encode((old + line + "\n").encode("utf-8")).decode(),
               "branch": "main"}
    if sha:
        payload["sha"] = sha
    bus.bridge.api(f"{bus.bridge.API}/contents/{bus.REGISTRY}", token, payload=payload, method="PUT")
    print(f"[4/4] ledger seq={core['seq']} hash={rec['hash'][:16]} prev={prev[:16] or '-'}")

    print(r["content"].strip())
    return 0


def main(argv) -> int:
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    go = "--go" in argv
    lens = arg("--lens")
    artifact = arg("--artifact")
    if "--all" in argv:
        for name in ("expert", "process", "adversary", "outsider"):
            run_lens(name, LENSES[name]["artifact"], go)
        return 0
    if not lens or lens not in LENSES:
        print(__doc__)
        print("lenses: " + ", ".join(LENSES))
        return 2
    return run_lens(lens, artifact or LENSES[lens]["artifact"], go)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main(sys.argv))
