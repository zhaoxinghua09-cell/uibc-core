# Verify this sample — no AI knowledge needed

You are checking one thing: **is this folder of gateway records exactly
the folder the operator sealed, or was something changed afterwards?**
You do not need to understand anything else on this page.

## The five steps

1. **Open a terminal.** Windows: press the Windows key, type
   `powershell`, press Enter. Mac: press Cmd+Space, type `terminal`,
   press Enter. A plain window opens where you can type.
2. **Get the checking tool once** (needs the internet):
   `git clone https://github.com/zhaoxinghua09-cell/uibc-core.git`
3. **Go into it:** `cd uibc-core`
4. **Run the check** on the folder you were given, for example:
   `python3 -m uibc_core.cli verify ../packages/exported-sealed`
5. **Read the one word in the result:**
   - **PASS** — nothing in this folder was changed since it was sealed.
     What you hold is what the operator sealed.
   - **FAIL** — something was changed, swapped or removed. The check
     names the file. Do not rely on the folder; send it back and ask why.
   - **INCONCLUSIVE** — the check could not be completed. That is not a
     pass. Treat the folder as unknown and ask before relying on it.

## Practice first

- Check `packages/exported-sealed` first: expect **PASS**.
- Then check `packages/exported-edited`: expect **FAIL**, naming
  `files/records-export.json`. In that copy, a blocked tool call was
  quietly rewritten to look like a success. The check catches it
  because the folder no longer matches what was sealed.

## The extra step that proves who sealed it

A seal alone proves a folder was not changed *since sealing*. To prove
it was sealed by the operator (not by someone else with a fresh seal),
compare the seal against the operator's public key you already hold:

`python3 -m uibc_core.cli verify --pubkey ../operator.pub ../packages/exported-sealed`

Try it on `packages/exported-resealed`: the check open-verifies as
PASS, but with the operator's key pinned it is **FAIL** — wrong key.
That is why the key must come from a channel you trust, not from the
same folder as the records.
