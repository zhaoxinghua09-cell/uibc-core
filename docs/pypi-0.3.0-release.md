# uibc-core 0.3.0 on PyPI — release record

- Project: <https://pypi.org/project/uibc-core/>
- Version: **0.3.0**
- Uploaded: 2026-11-12T03:58:49.222847Z
- Uploader: account `Steven_Zhao2026` via an API token kept in the local DPAPI vault. That token had
  already published two other projects (`medxpert-reg-hub` 2.0.2, `synomosai-governance-mcp` 1.2.0),
  so it is account-level rather than scoped to this one project. The token is never printed, logged
  or committed; the uploader reads it from the vault straight into the process environment.
- Files (identical bytes to the CI build of release run `43150166821`):

| file | bytes | sha256 |
|---|---|---|
| `uibc_core-0.3.0-py3-none-any.whl` | 43951 | `5166910f11b649f8c9b0f11a149c0f9fc76d1f86b0ff0ce850e770bfff41f834` |
| `uibc_core-0.3.0.tar.gz` | 67620 | `226c0a21cbc95bb8982fbf746d3b76ef51b18f03b2df3e5cef623da7b1ccedd6` |

## Install

```bash
pip install uibc-core==0.3.0
uv run --with uibc-core==0.3.0 -- uibc-core --help
```

Verified 2026-11-12 from a clean environment: `importlib.metadata.version("uibc-core")` -> `0.3.0`.

## Two traps that cost real time here

1. **`https://pypi.org/project/uibc-core/` answers 200 even when the project does not exist.**
   The reliable tests are `https://pypi.org/pypi/uibc-core/json` and `https://pypi.org/simple/uibc-core/`
   (404 = absent). Anyone judging publication by the human-facing page will be misled.
2. **Mirrors lag.** A machine configured with `UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/`
   reported "uibc-core was not found" for the first minutes after upload; forcing
   `--index-url https://pypi.org/simple` resolved it at once. If a fresh user says the package is
   missing, ask for their index URL before believing them.

## Why the release-triggered workflow still shows a failure

`publish-pypi.yml` uses OIDC trusted publishing, which needs a *pending publisher* configured for this
repository on pypi.org. That is still outstanding, so run `43150166821` fails at
`Run pypa/gh-action-pypi-publish@release/v1`. The upload above used the token path instead; once the
pending publisher exists, the workflow becomes the no-secret path and needs no change.
